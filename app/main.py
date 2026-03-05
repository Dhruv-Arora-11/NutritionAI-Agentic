from dotenv import load_dotenv
from agent_state import AgentState
from langgraph.graph import StateGraph , START , END
import asyncio
from agents.extractor import extractor_node
from agents.nutrition_requirement import nutrition_agent as nutritionist
from agents.extractor import extractor_node
from agents.nutrition_requirement import nutritionist_team
from agents.diet_planner import planner_agent
from agents.tracker import tracker_agent
import psycopg2
from postgre.identity import get_db_connection
from agent_state import AgentState
from agents.kb_responsder import kb_responder_node
from postgre.identity import init_db

load_dotenv()
async def start_node(state:AgentState):
    print(f"--- LOG: Received Input: {state.user_input} ---")
    return state

workflow_graph = StateGraph(AgentState)   # initialize the graph



async def check_history_node(state: AgentState):
    print("--- LOG: Checking User History ---")
    name = state.get("user_name")
    
    # Path 1: No name extracted yet
    if not name:
        print("--- LOG: No name in state, skipping history check ---")
        return {} 

    conn = get_db_connection()
    
    # Path 2: Database Connection Failed
    if not conn:
        print("⚠️ DB Connection failed in check_history_node")
        return {"is_new_user": True} 

    try:
        cur = conn.cursor()
        cur.execute("SELECT height, weight, goal FROM user_profiles WHERE user_name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            # Path 3: Existing User Found (Merge history with current state)
            print(f"--- DB: Found history for {name} ---")
            return {
                "height": state.get("height") or row[0],
                "weight": state.get("weight") or row[1],
                "goal": state.get("goal") or row[2],
                "is_new_user": False
            }
        else:
            # Path 4: New User (Not in DB)
            print(f"--- DB: No history for {name} ---")
            return {"is_new_user": True}
            
    except Exception as e:
        print(f"❌ Error querying history: {e}")
        return {"is_new_user": True}


async def run_interaction():
    # Initialize with None so identity_node knows it needs to ask/extract
    current_state = {
        "messages": [], 
        "user_name": None, 
        "height": None, 
        "weight": None
    }
    
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
            
            # combined the if_valid_input and route_agent in the unified_router()

def route_identity(state: AgentState):
    # Logic: If the user is new, we stop to ask for stats. 
    # If they exist, we proceed to the extractor.
    if state.get("is_new_user"):
        return "ask_initial_stats"
    else:
        return "extractor"


async def identity_node(state: AgentState):
    print("--- LOG: Entering Identity Node ---")
    user_input = state.get("user_input", "").strip()
    
    # Check if we already have the name in state
    if state.get("user_name"):
        return {}

    # Define name early so it's available everywhere in this function
    name = user_input
    conn = get_db_connection()
    
    if not conn:
        print("⚠️ WARNING: Database is offline. Operating in guest mode.")
        return {
            "user_name": name, 
            "is_new_user": True,
            "final_response": f"Database offline. Proceeding as guest, {name}. What are your stats?"
        }

    try:
        cur = conn.cursor()
        # Use 'name' which we defined above
        cur.execute("SELECT height, weight, goal, diet_preference FROM user_profiles WHERE user_name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return {
                "user_name": name,
                "is_new_user": False,
                "height": row[0],
                "weight": row[1],
                "goal": row[2],
                "diet_preference": row[3]
            }
        else:
            return {
                "user_name": name,
                "is_new_user": True
            }
    except Exception as e:
        print(f"Database error: {e}")
        return {"user_name": name, "is_new_user": True}
        
        
def unified_router(state: AgentState):
    intent = state.get("intent")
    
    # Path 1: General Knowledge Questions
    if intent == "general_query":
        return "kb_responder"
        
    # Path 2: Logging Food
    if intent == "log_food":
        return "tracker"
    
    # Path 3: Planning a Diet (Check for stats)
    if state.get("height") and state.get("weight"):
        return "nutritionist"
    
    return "ask_more_info"


async def save_profile_node(state: AgentState):
    user_name = state.get("user_name")
    
    # We only save if we have a name and at least one physical stat
    if user_name and (state.get("height") or state.get("weight")):
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                # UPSERT: Insert new or Update if user_name exists
                cur.execute("""
                    INSERT INTO user_profiles (user_name, height, weight, goal, diet_preference)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_name) 
                    DO UPDATE SET 
                        height = COALESCE(EXCLUDED.height, user_profiles.height),
                        weight = COALESCE(EXCLUDED.weight, user_profiles.weight),
                        goal = COALESCE(EXCLUDED.goal, user_profiles.goal),
                        diet_preference = COALESCE(EXCLUDED.diet_preference, user_profiles.diet_preference),
                        last_updated = CURRENT_TIMESTAMP;
                """, (
                    user_name, 
                    state.get("height"), 
                    state.get("weight"), 
                    state.get("goal"), 
                    state.get("diet_preference")
                ))
                conn.commit()
                cur.close()
                conn.close()
                print(f"--- DB: Saved/Updated data for {user_name} ---")
            except Exception as e:
                print(f"❌ DB Save Error: {e}")
    
    return {} # Crucial: Always return a dict to keep the graph moving



# 1. Register ALL nodes
# --- 1. Register ALL nodes ---
# --- 1. Register ALL nodes ---
workflow_graph.add_node("extractor", extractor_node)
workflow_graph.add_node("check_history", check_history_node)
workflow_graph.add_node("save_profile", save_profile_node)
workflow_graph.add_node("nutritionist", nutritionist_team)
workflow_graph.add_node("diet_architect", planner_agent)
workflow_graph.add_node("tracker", tracker_agent)
workflow_graph.add_node("kb_responder", kb_responder_node)

# --- 2. Define Entry Point ---
workflow_graph.add_edge(START, "extractor")

# --- 3. The Persistence Pipeline ---
# Step 1: LLM extracts Name/Stats -> Step 2: Look up DB for history -> Step 3: Save to DB
workflow_graph.add_edge("extractor", "check_history")
workflow_graph.add_edge("check_history", "save_profile")

# --- 4. Main Intent Routing (The Junction) ---
workflow_graph.add_conditional_edges(
    "save_profile",
    unified_router,
    {
        "tracker": "tracker",
        "nutritionist": "nutritionist",
        "kb_responder": "kb_responder",
        "ask_more_info": END 
    }
)

# --- 5. Define Terminal Edges ---
workflow_graph.add_edge("nutritionist", "diet_architect")
workflow_graph.add_edge("diet_architect", END)
workflow_graph.add_edge("tracker", END)
workflow_graph.add_edge("kb_responder", END)

# --- 6. Compile ---
app = workflow_graph.compile()

if __name__ == "__main__":
    init_db()
    asyncio.run(run_interaction())
    
    