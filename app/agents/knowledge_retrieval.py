import json

async def knowledge_retriever(state: AgentState):
    print("--- LOG: Consulting Knowledge Base ---")
    goal = state.get("goal", "lean")
    
    with open("knowledge_base/constraints.json", "r") as f:
        kb_data = json.load(f)
    
    # Get the specific rules for the user's goal
    expert_rules = kb_data.get(f"{goal}_goal", {})
    
    return {"kb_advice": expert_rules}