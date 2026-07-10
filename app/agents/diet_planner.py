from mcp import client
from agent_state import AgentState
from dotenv import load_dotenv
from groq import Groq
import os
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def planner_agent(state: AgentState):
    print("--- LOG: Entering Planner Agent (7-Day Architect) ---")

    meals = state.get("meal_details", [])
    suggested_meals = state.get("suggested_meals", [])
    metrics = state.get("total_plan_metrics", {})
    pref = state.get("diet_preference", "vegetarian")
    safety_report = state.get("safety_report", {})

    # Keep going even when all nutrition lookups fail.
    if not meals or not any(
        meal.get("nutrition_available", True) for meal in meals
    ):
        meal_input = suggested_meals or meals
        nutrition_note = (
            "USDA nutrition data was unavailable. Do not invent verified "
            "nutritional values; provide the meal plan without claiming "
            "that its nutrition values have been verified."
        )
    else:
        meal_input = meals
        nutrition_note = (
            "Use available nutrition data where relevant. If values are "
            "incomplete, clearly label them as partial estimates."
        )

    print("--- DEBUG: Planner meal input:", meal_input)
    print("--- DEBUG: Planner metrics:", metrics)

    planning_prompt = f"""
You are a meal-planning assistant.

User request: {state.get("user_input", "")}
Diet preference: {pref}
Available meal suggestions and lookup results: {meal_input}
Available nutrition metrics: {metrics}
Safety review: {safety_report}

Create a practical 7-day meal plan, Monday through Sunday.

Requirements:
- Include breakfast, lunch, a snack, and dinner every day.
- Respect the user's diet preference. For vegetarian requests, do not include
  meat, fish, or eggs.
- Use the available meal suggestions as a starting point.
- You may vary the meals to complete the week.
- Include quantities when available.
- Do not claim that unverified nutrition data is USDA-verified.
- {nutrition_note}
- If nutrition data is incomplete, still produce the meal plan.
- Return a readable Markdown table and a brief note about data limitations.
"""

    
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a meal-planning assistant. "
                    "Respond directly with the requested plan. "
                    "Keep reasoning brief and prioritize the final answer."
                ),
            },
            {"role": "user", "content": planning_prompt},
        ],
        max_tokens=8192,
        reasoning_effort="low",
    )
    

    print("--- PLANNER DIAGNOSTICS ---")
    print("Finish reason:", response.choices[0].finish_reason)
    print("Message role:", response.choices[0].message.role)
    print("Message content:", repr(response.choices[0].message.content))
    print("Usage:", response.usage)
    print("---------------------------")

    plan = response.choices[0].message.content

    if not plan or not plan.strip():
        plan = (
            "The planner model returned an empty response. "
            "Please retry the request."
        )


    print("--- DEBUG: Planner response received ---")
    
    print("\n--- FINAL 7-DAY PLAN ---\n")
    print(plan)

    return {
        "seven_day_plan": plan,
        "final_response": plan,
    }
