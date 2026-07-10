import json
import os
from groq import Groq
from mcp_client.client import call_mcp_tool
from agent_state import AgentState
from langgraph.graph import StateGraph,START,END

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def nutrition_agent(state: AgentState):
    print("got in nutritional_agent")
    print("calculates bmi,bmr")
    h, w = state.get("height"), state.get("weight")
    goal = state.get("goal")
    diet_preference = state.get("diet_preference")
    

    # 1. Get Baseline Metrics
    bmi_resp = await call_mcp_tool("calc_bmi", {"height": h, "weight": w})
    age = state.get("age")
    gender = state.get("gender")
    
    if age is None or gender is None:
        raise ValueError(
            "Age and gender are required for BMR calculation. "
            "Check that the extractor provides both fields."
        )
    
    bmr_resp = await call_mcp_tool(
        "calculate_bmr",
        {
            "weight": w,
            "height": h,
            "age": age,
            "gender": gender,
        },
    )
    
    # Extract the raw numbers from the MCP response
    bmi_val = bmi_resp
    bmr_val = bmr_resp

    planner_prompt = f"""
    You are a professional Nutritionist.
    Patient Data: BMI {bmi_val}, BMR {bmr_val}. Goal: {goal} , diet_preference: {diet_preference}.
    
    Suggest exactly 3 meals: breakfast, lunch, and dinner.
    
    RETURN ONLY VALID JSON. 
    STRICT RULES:
    1. 'quantity' MUST be a raw number (integer) representing grams. 
    2. DO NOT add 'g' or 'grams' after the number.
    3. Use ONLY these keys: "food_name", "quantity".
    4. Do not cross the diet pref boundary . everything should be according to what we want.
    
    JSON Structure:
    {{
      "meals": [
        {{"food_name": "string", "quantity": number}},
        {{"food_name": "string", "quantity": number}},
        {{"food_name": "string", "quantity": number}}
      ]
    }}
    """
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": planner_prompt}],
        response_format={"type": "json_object"},
        max_tokens=4096,
    )
    
    raw_content = json.loads(response.choices[0].message.content)
    # Ensure we get the list from the 'meals' key
    suggested_meals = raw_content.get("meals", [])

    
    return {
        "suggested_meals": suggested_meals,
        "bmi_result": bmi_val,
        "daily_calories": bmr_val
    }


async def nutritional_executor(state: AgentState):
    print("--- LOG: Entering nutritional_executor ---")

    meals = state.get("suggested_meals", [])
    total_metrics = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }
    detailed_plan = []
    successful_lookups = 0

    for item in meals:
        food_name = item.get("food_name", "Unknown food")
        quantity = item.get("quantity", 0)

        print(f"--- LOG: Fetching data for {food_name} ({quantity}g) ---")

        try:
            response = await call_mcp_tool(
                "food_database_tool",
                {
                    "food_name": food_name,
                    "quantity": quantity,
                },
            )

            data = response

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {"error": f"Invalid tool response: {data}"}

            if isinstance(data, dict) and isinstance(data.get("result"), dict):
                data = data["result"]

            if not isinstance(data, dict) or data.get("error"):
                error = (
                    data.get("error", "Unexpected tool response")
                    if isinstance(data, dict)
                    else "Unexpected tool response format"
                )
                print(f"Nutrition lookup failed for {food_name}: {error}")

                # Preserve the suggested meal so the planner can still proceed.
                detailed_plan.append({
                    "food": food_name,
                    "quantity_g": quantity,
                    "nutrition_available": False,
                    "error": error,
                })
                continue

            total_metrics["calories"] += float(data.get("calories") or 0)
            total_metrics["protein"] += float(
                data.get("protein_g", data.get("protein", 0)) or 0
            )
            total_metrics["carbs"] += float(
                data.get("carbs_g", data.get("carbs", 0)) or 0
            )
            total_metrics["fat"] += float(
                data.get("fat_g", data.get("fat", 0)) or 0
            )

            data["nutrition_available"] = True
            detailed_plan.append(data)
            successful_lookups += 1

        except Exception as exc:
            print(f"Nutrition tool exception for {food_name}: {exc}")
            detailed_plan.append({
                "food": food_name,
                "quantity_g": quantity,
                "nutrition_available": False,
                "error": str(exc),
            })

    print(f"--- LOG: Successful lookups: {successful_lookups}/{len(meals)} ---")
    print(f"--- LOG: Calculated metrics: {total_metrics} ---")

    return {
        "total_plan_metrics": total_metrics,
        "meal_details": detailed_plan,
    }



async def medical_critic(state: AgentState):
    print("--- LOG: Entering medical_critic ---")

    metrics = state.get("total_plan_metrics", {})
    meals = state.get("meal_details", [])
    successful_meals = [
        meal for meal in meals
        if meal.get("nutrition_available", True)
    ]
    failed_meals = [
        meal for meal in meals
        if not meal.get("nutrition_available", True)
    ]

    if not successful_meals:
        safety_report = {
            "is_safe": False,
            "calorie_safe": False,
            "protein_safe": False,
            "warnings": [
                "Nutrition lookup failed for all suggested meals. "
                "A nutrition safety assessment could not be completed."
            ],
        }

        return {
            "safety_report": safety_report,
            "final_response": (
                "Nutrition safety review could not be completed because "
                "nutrition data was unavailable. The meal suggestions are "
                "still available for the planner."
            ),
            "meal_details": meals,
            "total_plan_metrics": metrics,
        }

    # Normalize the goal to the values expected by the MCP tool.
    raw_goal = str(state.get("goal", "")).lower().replace(" ", "").replace("_", "")

    if raw_goal in {"loseweight", "weightloss", "fatloss"}:
        goal = "weight_loss"
    elif raw_goal in {"weightgain", "gainweight"}:
        goal = "weight_gain"
    elif raw_goal in {"bulk", "bulking"}:
        goal = "bulk"
    else:
        goal = raw_goal

    safety_check = await call_mcp_tool(
        "medical_guidelines_tool",
        {
            "bmi": state.get("bmi_result"),
            "weight": state.get("weight"),
            "daily_calories": metrics.get("calories", 0),
            "protein": metrics.get("protein", 0),
            "goal": goal,
        },
    )

    if isinstance(safety_check, str):
        try:
            safety_check = json.loads(safety_check)
        except json.JSONDecodeError:
            safety_check = {"error": "Invalid medical guidelines response"}

    if not isinstance(safety_check, dict) or safety_check.get("error"):
        safety_check = {
            "is_safe": False,
            "warnings": ["Medical guidelines response could not be processed."],
        }

    warnings = list(safety_check.get("warnings", []))

    if failed_meals:
        warnings.append(
            f"Nutrition data was unavailable for {len(failed_meals)} "
            "suggested meal(s); calculated metrics may be incomplete."
        )
        safety_check["is_safe"] = False
        safety_check["warnings"] = warnings

    status = "SAFE" if safety_check.get("is_safe") is True else "WARNING"

    final_msg = f"--- Nutrition Report [{status}] ---\n"

    if failed_meals:
        final_msg += "Nutrition metrics are partial and may not represent the full plan.\n"
    else:
        final_msg += f"Total Calories: {metrics.get('calories', 0)} kcal\n"

    final_msg += (
        "Findings: "
        + (", ".join(warnings) if warnings else "Plan meets medical guidelines.")
    )

    return {
        "safety_report": safety_check,
        "final_response": final_msg,
        "meal_details": meals,
        "total_plan_metrics": metrics,
    }



nutritionist_builder = StateGraph(AgentState)

# 2. Add the internal nodes
nutritionist_builder.add_node("planner", nutrition_agent)
nutritionist_builder.add_node("analyzer", nutritional_executor)
nutritionist_builder.add_node("critic", medical_critic)

# 3. Define the internal flow
# Logic: Start -> Plan Meals -> Analyze Nutrition -> Medical Review -> End
nutritionist_builder.add_edge(START, "planner")
nutritionist_builder.add_edge("planner", "analyzer")
nutritionist_builder.add_edge("analyzer", "critic")
nutritionist_builder.add_edge("critic", END)

# 4. Compile the sub-graph so it can be used as a single node in main.py
nutritionist_team = nutritionist_builder.compile()