from dotenv import load_dotenv
from agent_state import AgentState
from langgraph.graph import StateGraph , START , END
import asyncio
from agents.extractor import extractor_node
from agents.nutrition_requirement import nutrition_agent as nutritionist
from agents.extractor import extractor_node
from agents.nutrition_requirement import nutritionist_team

load_dotenv()
async def start_node(state:AgentState):
    print(f"--- LOG: Received Input: {state.user_input} ---")
    return state

workflow_graph = StateGraph(AgentState)   # initialize the graph


async def run_interaction():
    current_state = {"messages": [], "height": None, "weight": None, "goal": None}
    
    while True:
        user_msg = input("\nUser: ")
        current_state["user_input"] = user_msg

        async for event in app.astream(current_state):
            for node, state_update in event.items():
                if not isinstance(state_update, dict):
                    print("Invalid state update:", state_update)
                    continue
                
                # 1. Filter out Nones
                filtered_update = {k: v for k, v in state_update.items() if v is not None}
                
                # 2. CRITICAL: Actually update the state!
                current_state.update(filtered_update)
                print(f"--- Node {node} updated state with: {filtered_update.keys()} ---")

        # THE RE-ASKING LOGIC
        if not current_state.get("height") or not current_state.get("weight"):
            print("Agent: I've got some of your info, but I still need your height and weight to calculate your BMI!")
            # The loop continues, user types info, and it goes back to the Extractor!   
            
def if_valid_input(state: AgentState):
    missing = []
    if not state.get("height"): missing.append("height")
    if not state.get("weight"): missing.append("weight")
    if not state.get("goal"): missing.append("goal")
    if not state.get("diet_preference"): missing.append("diet_preference")

    if missing:
        # We store the missing fields in the state so the UI can see them
        print(f"--- LOG: Missing {', '.join(missing)} ---")
        return "ask_more_info"
    else:
        print("got all the inputs that were necessary")
    
    return "proceed_to_nutritionist"


workflow_graph = StateGraph(AgentState)

# Nodes
workflow_graph.add_node("extractor", extractor_node)
# Add the compiled sub-graph as a regular node
workflow_graph.add_node("nutritionist", nutritionist_team)

# Flow
workflow_graph.add_edge(START, "extractor")

workflow_graph.add_conditional_edges(
    "extractor",
    if_valid_input,
    {
        "proceed_to_nutritionist": "nutritionist",
        "ask_more_info": END
    }
)

workflow_graph.add_edge("nutritionist", END)

app = workflow_graph.compile()

if __name__ == "__main__":
    asyncio.run(run_interaction())
    
    