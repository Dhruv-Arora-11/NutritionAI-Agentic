from mcp import client
from agent_state import AgentState
from dotenv import load_dotenv
from groq import Groq
import os
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
async def planner_agent(state: AgentState):
    print("--- LOG: Entering Planner Agent (7-Day Architect) ---")
    
    # 1. Retrieve the validated data from the previous nodes
    meals = state.get("meal_details", [])
    metrics = state.get("total_plan_metrics", {})
    pref = state.get("diet_preference", "Veg")

    # 2. Planning Prompt: We ask the LLM to create variety using the validated foods
    # We provide the specific USDA-verified items so it doesn't hallucinate new ones
    planning_prompt = f"""
    You are a professional Meal Planner. 
    Validated Food Data (USDA Verified): {meals}
    Target Daily Metrics: {metrics}

    TASK:
    Create a 7-day Meal Plan (Monday to Sunday).
    - Use the validated foods provided above as the core ingredients.
    - Rotate the combinations so the user doesn't eat the exact same meal every day.
    - For each day, provide: Breakfast, Lunch, Dinner, and a Snack.
    - Ensure the 'Cooking/Prep Instructions' align with the {pref} preference.
    - STRICT REQUIREMENT: The user's preference is {state['diet_preference']}. 
        If it is 'veg', do NOT include meat or fish or even the eggs

    FORMAT:
    Return a clear Markdown table for the week.
    """

    response =  client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": planning_prompt}]
    )

    print({
        "seven_day_plan": response.choices[0].message.content,
        "final_response": response.choices[0].message.content
    })
    
    return {
        "seven_day_plan": response.choices[0].message.content,
        "final_response": response.choices[0].message.content
    }