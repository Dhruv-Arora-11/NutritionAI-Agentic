from typing import Annotated, Any, Dict, List, Optional, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_input: str
    
    # Extractor Data ---
    intent: Optional[str]
    goal: Optional[Literal["weight_loss", "weight_gain", "bulk", "lean"]]
    user_name: Optional[str]
    
    # Physical Metrics ---
    height: Optional[float]
    weight: Optional[float]
    age: Optional[int]
    gender: Optional[Literal["male", "female"]]
    diet_preference: Optional[Literal["veg", "non-veg", "vegan"]]
    
    # Agent Outputs ---
    suggested_meals: List[Dict[str, Any]]
    bmi_result: Optional[float]
    daily_calories: Optional[float]
    meal_plan: Optional[list]
    critic_feedback: Optional[str]
    is_safe: Optional[bool]
    total_plan_metrics: dict
    consumed_today: List[str]
    remaining_budget:List[int]
    consumed_today: List[Dict[str, Any]] # List of food data from USDA
    remaining_budget: Dict[str, float]   # The 'Leftover' calories/macros
    latest_logged_food: Optional[Dict[str, Any]] # Temporary storage for current log