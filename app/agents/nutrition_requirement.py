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
    bmr_resp = await call_mcp_tool("calculate_bmr", {"height": h, "weight": w, "age": 25, "gender": "male"})
    
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
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": planner_prompt}],
        response_format={"type": "json_object"}
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

    total_metrics = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    detailed_plan = []
    print("just before going to loop")
    print(meals)
    print("meals ended")
    for item in meals:
        print("in thte loop")
        print(f"--- LOG: Fetching data for {item['food_name']} ({item['quantity']}g) ---")
        
        # 1. Call the tool
        response = await call_mcp_tool("food_database_tool", {
            "food_name": item["food_name"], 
            "quantity": item["quantity"]
        })
        print("this is hte respnose")
        print(response)
        print("response ended")
        # 2. Extract the actual data! 
        # Your logs show the result is often inside 'structuredContent' or a 'result' key
        # Let's handle the common dictionary format returned by our bridge
        data = response.get("result", response) if isinstance(response, dict) else {}

        # 3. Aggregate using the exact keys from your MCP server (check your server code!)
        # If your server returns 'protein_g', use that here.
        total_metrics["calories"] += data.get("calories", 0)
        total_metrics["protein"] += data.get("protein_g", 0) or data.get("protein", 0)
        total_metrics["carbs"] += data.get("carbs_g", 0) or data.get("carbs", 0)
        total_metrics["fat"] += data.get("fat_g", 0) or data.get("fat", 0)
        
        detailed_plan.append(data)

    print(f"--- LOG: Final Calculated Metrics: {total_metrics} ---")
    
    return {
        "total_plan_metrics": total_metrics,
        "meal_details": detailed_plan
    }
async def medical_critic(state: AgentState):
    print("--- LOG: Entering medical_critic ---")
    
    # Check if we are using 'total_plan_metrics' or if it's nested
    metrics = state.get("total_plan_metrics", {})
    
    # Debug: See what the critic actually sees
    print(f"--- DEBUG: Critic sees metrics: {metrics} ---")

    # If metrics is empty, we have a state saving issue
    calories = metrics.get("calories", 0)
    protein = metrics.get("protein", 0)

    safety_check = await call_mcp_tool("medical_guidelines_tool", {
        "bmi": state.get("bmi_result"),
        "weight": state.get("weight"),
        "daily_calories": calories, # Use the extracted variable
        "protein": protein,         # Use the extracted variable
        "goal": state.get("goal")
    })

    # This is the final message the user will see
    report = safety_check.get("warnings", [])
    status = "SAFE" if safety_check.get("is_safe") else "WARNING"
    
    final_msg = f"--- Nutrition Report [{status}] ---\n"
    final_msg += f"Total Calories: {metrics.get('calories')} kcal\n"
    final_msg += f"Findings: {', '.join(report) if report else 'Plan meets medical guidelines.'}"

    return {"safety_report": safety_check, "final_response": final_msg}


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