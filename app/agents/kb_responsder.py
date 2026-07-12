import json
from agent_state import AgentState

async def kb_responder_node(state: AgentState):
    print("--- LOG: Consulting Knowledge Base ---")
    user_query = state.get("user_input", "").lower()
    
    with open("data/nutrition_kb.json", "r") as f:
        kb = json.load(f)
    
    # Simple keyword matching for a file-based KB
    response = "I couldn't find specific info on that in my guidelines, but generally, consistency is key!"
    for key in kb:
        if key in user_query:
            response = kb[key]
            break
            
    return {"final_response": response}