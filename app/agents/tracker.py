
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp_client.client import call_mcp_tool
from postgre.identity import (
    get_user_profile,
    save_food_log,
    get_food_logs_for_date,
)
from agent_state import AgentState


TIMEZONE = "Asia/Kolkata"


def get_nutrient_totals(food_logs):
    """Sum known nutrient values across persisted food entries."""
    totals = {}

    for entry in food_logs:
        nutrients = entry.get("nutrients") or {}

        for nutrient, value in nutrients.items():
            if isinstance(value, (int, float)):
                totals[nutrient] = totals.get(nutrient, 0.0) + value

    return {
        key: round(value, 2)
        for key, value in totals.items()
    }


def calculate_remaining(targets, consumed):
    """Calculate remaining amounts only for nutrients with known targets."""
    remaining = {}

    for nutrient, target in (targets or {}).items():
        if not isinstance(target, (int, float)):
            continue

        if nutrient not in consumed:
            # Do not assume an unknown consumption value is zero.
            remaining[nutrient] = None
            continue

        remaining[nutrient] = round(
            target - consumed[nutrient], 2
        )

    return remaining


async def tracker_agent(state: AgentState):
    print("--- LOG: Entering Persistent Food Tracker ---")

    user_name = state.get("user_name")
    logged_item = state.get("logged_food")

    # 1. Validate the user and food entry.
    if not user_name:
        return {
            "final_response": (
                "I need your user profile before saving this food. "
                "Please provide your profile name first."
            )
        }

    if not isinstance(logged_item, dict) or not logged_item.get("name"):
        return {
            "final_response": (
                "I couldn't identify the food you ate. "
                "Please provide the food name and quantity."
            )
        }

    quantity = logged_item.get("quantity")

    if quantity is None:
        return {
            "final_response": (
                "What quantity did you eat? Please provide it in grams "
                "so I can calculate the nutrients accurately."
            )
        }

    try:
        quantity = float(quantity)

        if not 0 < quantity <= 10000:
            raise ValueError("Quantity must be between 0 and 10000 grams.")

    except (ValueError, TypeError):
        return {
            "final_response": (
                "Please provide a valid food quantity in grams."
            )
        }

    # 2. Resolve the persistent profile and user_id.
    try:
        profile = get_user_profile(user_name)

        if not profile:
            return {
                "final_response": (
                    "I couldn't find your saved profile. "
                    "Please create your profile before logging food."
                )
            }

        user_id = profile["user_id"]

        # 3. Look up the nutrition for the consumed quantity.
        food_stats = await call_mcp_tool(
            "food_database_tool",
            {
                "food_name": logged_item["name"],
                "quantity": quantity,
            },
        )

        if not isinstance(food_stats, dict) or food_stats.get("error"):
            return {
                "final_response": (
                    f"I couldn't retrieve reliable nutrition data for "
                    f"'{logged_item['name']}'. The food was not saved."
                )
            }

        # Some MCP clients wrap tool results in a result field.
        if isinstance(food_stats.get("result"), dict):
            food_stats = food_stats["result"]

        if food_stats.get("error"):
            return {
                "final_response": (
                    f"I couldn't retrieve nutrition data for "
                    f"'{logged_item['name']}'. The food was not saved."
                )
            }

        # 4. Preserve every nutrient the tool actually returned.
        # Normalize the existing USDA tool's nutrient keys.
        nutrients = {
            key: value
            for key, value in food_stats.items()
            if key not in {"food", "quantity_g", "source"}
            and isinstance(value, (int, float))
        }

        if not nutrients:
            return {
                "final_response": (
                    "The food lookup returned no usable nutrient values. "
                    "The food was not saved."
                )
            }

        food_name = food_stats.get("food", logged_item["name"])
        source = food_stats.get("source", "USDA")

        # 5. Persist the food before reporting it as logged.
        save_food_log(
            user_id=user_id,
            food_name=food_name,
            quantity_g=quantity,
            nutrients=nutrients,
            source=source,
        )

        # 6. Read all of today's persisted food logs.
        today = datetime.now(ZoneInfo(TIMEZONE)).date()

        food_logs = get_food_logs_for_date(
            user_id=user_id,
            target_date=today,
            timezone=TIMEZONE,
        )

        consumed = get_nutrient_totals(food_logs)

        # 7. Compare against targets stored in the profile.
        targets = profile.get("daily_nutrition_targets") or {}

        remaining = calculate_remaining(targets, consumed)

        # Keep a compact representation in LangGraph state.
        consumed_today = [
            {
                "food_name": entry["food_name"],
                "quantity_g": float(entry["quantity_g"]),
                "nutrients": entry.get("nutrients") or {},
                "logged_at": entry["logged_at"].isoformat(),
            }
            for entry in food_logs
        ]

        # 8. Build the response.
        lines = [
            f"Food logged successfully: {food_name} ({quantity:g} g).",
            "",
            "Today's nutrition totals:",
        ]

        for nutrient, amount in consumed.items():
            lines.append(f"- {nutrient}: {amount}")

        if targets:
            lines.extend(["", "Remaining daily targets:"])

            for nutrient, amount in remaining.items():
                if amount is None:
                    lines.append(
                        f"- {nutrient}: unknown; consumption data is incomplete."
                    )
                elif amount < 0:
                    lines.append(
                        f"- {nutrient}: target exceeded by {abs(amount):.2f}"
                    )
                else:
                    lines.append(f"- {nutrient}: {amount:.2f} remaining")
        else:
            lines.extend([
                "",
                "Your profile does not have daily nutrition targets yet. "
                "Your food has been saved, but remaining budgets cannot "
                "be calculated until targets are configured.",
            ])

        return {
            "consumed_today": consumed_today,
            "remaining_budget": remaining,
            "total_plan_metrics": targets,
            "latest_logged_food": {
                "food_name": food_name,
                "quantity_g": quantity,
                "nutrients": nutrients,
            },
            "final_response": "\n".join(lines),
        }

    except Exception as e:
        print(f"--- Tracker database/tool error: {e} ---")

        return {
            "final_response": (
                "I couldn't complete food logging because a database "
                "or nutrition lookup operation failed. Please try again."
            )
        }
