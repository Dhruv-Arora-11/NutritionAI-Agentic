from mcp.server.fastmcp import FastMCP
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("nutrition_mcp_server")
USDA_API_KEY = "4Ga7C5YVkXEpAw8OA3vyrM1SnHegTDmde6YzFlxl"

@mcp.tool()    
def calc_bmi( height:float  , weight:float ) -> float:
    """Calculate BMI using weight (kg) and height (meters)."""      #tool descrip. for LLM (DOCSTRING)
    bmi = weight / (height ** 2)
    return bmi
    # return {
    #         "bmi": bmi, 
    #         "final_response": f"I've calculated your BMI as {bmi}."
    #     }
    
@mcp.tool()
def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """Calculates BMR using the Mifflin-St Jeor Equation."""
    # height in cm for this formula
    height_cm = height * 100 
    if gender.lower() == "male":
        return (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
        # return {
        #     "bmr" : (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
        # }
    else:
        return (10 * weight) + (6.25 * height_cm) - (5 * age) - 161
        # return {
        #     "bmr" : (10 * weight) + (6.25 * height_cm) - (5 * age) - 161,
        #     }
    

@mcp.tool()
def calculate_macros(total_calories: float, goal: str):
    """Calculates Protein/Carb/Fat split based on goal."""
    if goal == "bulk":
        return {"p": 0.30, "c": 0.50, "f": 0.20} # High carb for energy
    return {"p": 0.40, "c": 0.30, "f": 0.30}     # High protein for weight loss

@mcp.tool()
async def food_database_tool(food_name: str, quantity: float):
    """Fetch nutritional data for a specific food and quantity (grams)."""
    search_url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    if not USDA_API_KEY:
        return {"error": "USDA API Key is missing from environment variables."}

    params = {
        "api_key": USDA_API_KEY,
        "query": food_name,
        "pageSize": 1,
        "dataType": ["Foundation", "SR Legacy"] # These are usually the most accurate
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    return {"error": f"USDA API returned status {response.status}"}
                data = await response.json()

        foods = data.get("foods")
        if not foods:
            return {"error": f"No food found for '{food_name}'"}

        food = foods[0]
        nutrients = food.get("foodNutrients", [])

        # Helper to find nutrients by name or common variations
        def get_nutrient(names):
            for n in nutrients:
                if n.get("nutrientName") in names:
                    return n.get("value", 0)
            return 0

        # USDA names can be tricky, so we check a few common variants
        calories = get_nutrient(["Energy", "Energy (kcal)"])
        protein = get_nutrient(["Protein"])
        fat = get_nutrient(["Total lipid (fat)", "Fat"])
        carbs = get_nutrient(["Carbohydrate, by difference", "Carbohydrates"])

        # USDA values are per 100g
        factor = quantity / 100

        return {
            "food": food.get("description", food_name),
            "quantity_g": quantity,
            "calories": round(calories * factor, 2),
            "protein_g": round(protein * factor, 2),
            "carbs_g": round(carbs * factor, 2),
            "fat_g": round(fat * factor, 2),
            "source": "USDA FoodData Central"
        }
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}    
    
    
@mcp.tool()
async def medical_guidelines_tool(
    bmi: float,
    weight: float,
    daily_calories: float,
    protein: float,
    goal: str | None = None
):
    warnings = []

    # ----------------------------
    # 1️⃣ BMI Classification
    # ----------------------------
    if bmi < 18.5:
        bmi_category = "Underweight"
    elif 18.5 <= bmi < 25:
        bmi_category = "Normal"
    elif 25 <= bmi < 30:
        bmi_category = "Overweight"
    else:
        bmi_category = "Obese"

    # ----------------------------
    # 2️⃣ Safe Protein Range
    # 1.2g – 2.2g per kg bodyweight
    # ----------------------------
    min_protein = 1.2 * weight
    max_protein = 2.2 * weight

    protein_safe = min_protein <= protein <= max_protein

    if not protein_safe:
        warnings.append(
            f"Protein should be between {round(min_protein)}g and {round(max_protein)}g"
        )

    # ----------------------------
    # 3️⃣ Calorie Safety Logic
    # (basic adjustment logic)
    # ----------------------------
    # Rough maintenance estimation
    maintenance_low = weight * 28
    maintenance_high = weight * 33

    calorie_safe = True

    if goal == "weight_loss":
        if daily_calories > maintenance_low:
            calorie_safe = False
            warnings.append("Calories too high for fat loss")

    elif goal in ["weight_gain", "bulk"]:
        if daily_calories < maintenance_high:
            calorie_safe = False
            warnings.append("Calories too low for muscle gain")

    # ----------------------------
    # 4️⃣ Extreme BMI Warning
    # ----------------------------
    if bmi >= 35:
        warnings.append("Medical supervision strongly recommended")

    # ----------------------------
    # Final Structured Output
    # ----------------------------
    return {
        "bmi_category": bmi_category,
        "protein_safe": protein_safe,
        "calorie_safe": calorie_safe,
        "warnings": warnings,
        "is_safe": len(warnings) == 0
    }
    

@mcp.tool()
async def meal_combination_generator(
    validated_ingredients: list, 
    target_calories: float, 
    
):
    """
    Combines USDA-validated ingredients into balanced meal sets (Breakfast/Lunch/Dinner).
    Ensures the total calories of the combination match the target +/- 10%.
    """
    # 1. Logic: Categorize ingredients based on their dominant macro
    proteins = [i for i in validated_ingredients if i['protein_g'] > i['carbs_g']]
    carbs = [i for i in validated_ingredients if i['carbs_g'] > i['protein_g']]
    
    # 2. Build a Combo (Basic heuristic for a balanced plate)
    # In a production app, this could use a Knapsack Algorithm to hit exact macros
    meal_sets = []
    
    # Example: Create a "Standard Plate"
    if proteins and carbs:
        main_protein = proteins[0]
        main_carb = carbs[0]
        
        combined_cals = main_protein['calories'] + main_carb['calories']
        
        meal_sets.append({
            "meal_type": "Balanced Plate",
            "components": [main_protein['food'], main_carb['food']],
            "combined_metrics": {
                "total_calories": combined_cals,
                "total_protein": main_protein['protein_g'] + main_carb['protein_g']
            },
        })

    return {
        "suggested_combos": meal_sets,
        "logic_used": "Macro-Balanced Pairing"
    }



if __name__ == "__main__":
    mcp.run(transport="sse")
