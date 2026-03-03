import os
import asyncio
from typing import Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class ExtractionSchema(BaseModel):
    intent: Optional[str] = None 
    goal: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    diet_preference: Optional[str] = None

async def extractor_node(state: dict):
    prompt = f"""
    Extract structured JSON from this input.
    User input: {state["user_input"]}

    IMPORTANT: 
    - Only include keys if you find the value in the text.
    - If a value is missing, DO NOT include the key in the JSON at all.
    - height and weight MUST be numbers.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}  # Important
    )
    print("got in the extractor and called the llm . the response of LLM in extractor is :")
    json_output = response.choices[0].message.content
    print(json_output)
    try:
        # 1. Validate with Pydantic
        data = ExtractionSchema.model_validate_json(json_output)
        # 2. CRITICAL: Convert the Pydantic object to a DICT
        return data.model_dump() 
    except Exception as e:
        print(f"--- LOG: Extraction failed: {e} ---")
        return {} # Return empty dict instead of None


# Example
if __name__ == "__main__":
    result = asyncio.run(
        extractor_node({"user_input": "I am 1.75m tall and weigh 70kg and want weight loss"})
    )
    print(result)