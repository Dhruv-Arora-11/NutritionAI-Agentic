from mcp_client.client import call_mcp_tool
from agent_state import AgentState

async def tracker_agent(state: AgentState):
    print("--- LOG: Entering Tracker Agent ---")
    
    # 1. Get the food the Extractor found in the user's message
    logged_item = state.get("logged_food") # e.g., {"name": "Pizza", "quantity": 150}
    
    if not logged_item or not logged_item.get("name"):
        return {"final_response": "I couldn't identify the food you ate. Could you be more specific?"}

    # 2. Call your MCP USDA Tool
    food_stats = await call_mcp_tool("food_database_tool", {
        "food_name": logged_item["name"],
        "quantity": logged_item["quantity"] or 100
    })
    
    if "error" in food_stats:
        return {"final_response": f"Sorry, I couldn't find '{logged_item['name']}' in the database."}

    # 3. Calculate the new totals
    # We retrieve total_plan_metrics (Targets) and consumed_today (History)
    targets = state.get("total_plan_metrics") or {"calories": 2000, "protein": 100}
    history = state.get("consumed_today") or []
    
    # Add new food to history
    history.append(food_stats)
    
    # Sum up everything eaten today
    total_eaten_cal = sum(item.get("calories", 0) for item in history)
    total_eaten_prot = sum(item.get("protein_g", 0) for item in history)

    # 4. Update the Remaining Budget
    remaining = {
        "calories": round(targets.get("calories", 2000) - total_eaten_cal, 1),
        "protein": round(targets.get("protein", 100) - total_eaten_prot, 1)
    }

    status_update = (
        f"✅ Logged {food_stats['food']}!\n"
        f"🔥 Calories eaten: {total_eaten_cal} | 📉 Remaining: {remaining['calories']} kcal\n"
        f"💪 Protein eaten: {total_eaten_prot}g | 📉 Remaining: {remaining['protein']}g"
    )

    return {
        "consumed_today": history,
        "remaining_budget": remaining,
        "final_response": status_update
    }