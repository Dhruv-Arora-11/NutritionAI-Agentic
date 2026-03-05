import os
import asyncio
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
import json

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 1. Update the Schema to include ALL fields the LLM might return
class ExtractionSchema(BaseModel):
    user_name: Optional[str] = None
    intent: Optional[Literal["plan_new_diet", "log_food"]] = None 
    goal: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    diet_preference: Optional[str] = None
    # Add this to capture the food logging data!
    logged_food: Optional[Dict[str, Any]] = None 

async def extractor_node(state: dict):
    user_input = state.get("user_input", "")
    system_prompt = """
    You are a Precise Health Data Extractor.
    Extract the following from the user input into a JSON object:
    1. "user_name": The user's name (e.g., "Amit" from "I am Amit"). If not mentioned, return null.
    2. "intent": MUST be "plan_new_diet" or "log_food". 
    3. "height", "weight", "goal", "diet_preference": Extract values if present.
    4. "logged_food": If intent is "log_food", extract {"name": str, "quantity": float}.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        response_format={"type": "json_object"}
    )
    
    raw_content = response.choices[0].message.content
    
    try:
        # 1. Load as a standard dict first to clean it
        data_dict = json.loads(raw_content)
        
        # 2. SANITIZE: Fix the "null" string issue or missing intent
        valid_intents = ["plan_new_diet", "log_food"]
        if data_dict.get("intent") not in valid_intents:
            # If it's "null", "Unknown", or None, default to plan_new_diet
            data_dict["intent"] = "plan_new_diet"

        # 3. Validate the cleaned dict with Pydantic
        data = ExtractionSchema(**data_dict)
        return data.model_dump() 
        
    except Exception as e:
        print(f"--- LOG: Extraction cleaning failed: {e} ---")
        # Return a safe fallback so the Graph continues
        return {"intent": "plan_new_diet", "height": None, "weight": None}
    
    
if __name__ == "__main__":
    # Test 1: Planning
    print("Test 1 (Planning):")
    print(asyncio.run(extractor_node({"user_input": "I am 1.75m and 70kg, help me lose weight"})))
    
    # Test 2: Logging
    print("\nTest 2 (Logging):")
    print(asyncio.run(extractor_node({"user_input": "I just ate a 200g chicken breast"})))