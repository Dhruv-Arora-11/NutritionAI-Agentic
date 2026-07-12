
from dotenv import load_dotenv
from agent_state import AgentState
from langgraph.graph import StateGraph, START, END
import asyncio

from agents.extractor import extractor_node
from agents.nutrition_requirement import nutritionist_team
from agents.diet_planner import planner_agent
from agents.tracker import tracker_agent
from agents.kb_responsder import kb_responder_node
from postgre.identity import get_db_connection, init_db


load_dotenv()


workflow_graph = StateGraph(AgentState)


def unified_router(state: AgentState):
    """Route each request according to its extracted intent."""
    intent = state.get("intent")

    if intent == "general_query":
        return "kb_responder"

    if intent == "log_food":
        return "tracker"

    if intent == "plan_new_diet":
        if state.get("height") is not None and state.get("weight") is not None:
            return "save_profile"
        return "ask_more_info"

    return "ask_more_info"


async def save_profile_node(state: AgentState):
    print("\n========== SAVE PROFILE: START ==========")
    print(f"[PROFILE DEBUG] Intent: {state.get('intent')!r}")
    print(f"[PROFILE DEBUG] User name: {state.get('user_name')!r}")
    print(f"[PROFILE DEBUG] Height: {state.get('height')!r}")
    print(f"[PROFILE DEBUG] Weight: {state.get('weight')!r}")
    print(f"[PROFILE DEBUG] Goal: {state.get('goal')!r}")
    print(
        f"[PROFILE DEBUG] Diet preference: "
        f"{state.get('diet_preference')!r}"
    )

    if state.get("intent") == "log_food":
        print("[PROFILE DEBUG] Skipping profile save: food-logging intent")
        result = {}
        print(f"[PROFILE DEBUG] Returning {result!r}, type={type(result).__name__}")
        print("========== SAVE PROFILE: END ==========\n")
        return result

    user_name = state.get("user_name")

    if not user_name:
        print("[PROFILE DEBUG] Skipping: user_name is missing")
        result = {}
        print(f"[PROFILE DEBUG] Returning {result!r}, type={type(result).__name__}")
        print("========== SAVE PROFILE: END ==========\n")
        return result

    if state.get("height") is None and state.get("weight") is None:
        print("[PROFILE DEBUG] Skipping: both height and weight are missing")
        result = {}
        print(f"[PROFILE DEBUG] Returning {result!r}, type={type(result).__name__}")
        print("========== SAVE PROFILE: END ==========\n")
        return result

    conn = None

    try:
        print("[PROFILE DEBUG] Opening PostgreSQL connection...")
        conn = get_db_connection()

        if conn is None:
            print("[PROFILE ERROR] get_db_connection() returned None")
            result = {}
            print(f"[PROFILE DEBUG] Returning {result!r}")
            print("========== SAVE PROFILE: END ==========\n")
            return result

        print("[PROFILE DEBUG] PostgreSQL connection acquired")

        with conn.cursor() as cur:
            print("[PROFILE DEBUG] Executing profile INSERT/UPDATE...")

            cur.execute(
                """
                INSERT INTO user_profiles
                    (user_name, height, weight, goal, diet_preference)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_name)
                DO UPDATE SET
                    height = COALESCE(
                        EXCLUDED.height, user_profiles.height
                    ),
                    weight = COALESCE(
                        EXCLUDED.weight, user_profiles.weight
                    ),
                    goal = COALESCE(
                        EXCLUDED.goal, user_profiles.goal
                    ),
                    diet_preference = COALESCE(
                        EXCLUDED.diet_preference,
                        user_profiles.diet_preference
                    ),
                    last_updated = CURRENT_TIMESTAMP;
                """,
                (
                    user_name,
                    state.get("height"),
                    state.get("weight"),
                    state.get("goal"),
                    state.get("diet_preference"),
                ),
            )

            print(f"[PROFILE DEBUG] Rows affected: {cur.rowcount}")

        print("[PROFILE DEBUG] Committing transaction...")
        conn.commit()
        print("[PROFILE DEBUG] COMMIT completed")

        # Verify that the profile is readable after the commit.
        with conn.cursor() as cur:
            print("[PROFILE DEBUG] Reading profile back from database...")

            cur.execute(
                """
                SELECT user_name, height, weight, goal,
                       diet_preference, last_updated
                FROM user_profiles
                WHERE user_name = %s;
                """,
                (user_name,),
            )

            saved_profile = cur.fetchone()

        if saved_profile:
            print("[PROFILE VERIFY] Profile found after commit:")
            print(f"[PROFILE VERIFY] User: {saved_profile[0]}")
            print(f"[PROFILE VERIFY] Height: {saved_profile[1]}")
            print(f"[PROFILE VERIFY] Weight: {saved_profile[2]}")
            print(f"[PROFILE VERIFY] Goal: {saved_profile[3]}")
            print(f"[PROFILE VERIFY] Diet: {saved_profile[4]}")
            print(f"[PROFILE VERIFY] Updated at: {saved_profile[5]}")
        else:
            print(
                "[PROFILE ERROR] INSERT/UPDATE completed, "
                "but the profile could not be read back"
            )

    except Exception as e:
        if conn is not None:
            conn.rollback()

        print(f"[PROFILE ERROR] {type(e).__name__}: {e}")
        result = {}
        print(f"[PROFILE DEBUG] Returning {result!r}, type={type(result).__name__}")
        print("========== SAVE PROFILE: END ==========\n")
        return result

    finally:
        if conn is not None:
            conn.close()
            print("[PROFILE DEBUG] PostgreSQL connection closed")

    result = {}
    print(f"[PROFILE DEBUG] Final return value: {result!r}")
    print(f"[PROFILE DEBUG] Return type: {type(result).__name__}")
    print("========== SAVE PROFILE: END ==========\n")

    return result

async def run_interaction():
    """Run the interactive NutritionAI application."""

    current_state = {
        "messages": [],
        "user_name": None,
        "height": None,
        "weight": None,
    }

    while True:
        try:
            user_msg = input("\nUser: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting NutritionAI.")
            break

        if not user_msg:
            continue

        if user_msg.lower() in {"exit", "quit", "bye"}:
            print("Exiting NutritionAI.")
            break

        current_state["user_input"] = user_msg

        try:
            async for event in app.astream(
                current_state,
                stream_mode="updates",
            ):
                print(f"\n[GRAPH DEBUG] Raw stream event: {event!r}")
                print(f"[GRAPH DEBUG] Event type: {type(event).__name__}")

                for node, state_update in event.items():
                    print(f"[GRAPH DEBUG] Node completed: {node}")
                    print(f"[GRAPH DEBUG] Raw update: {state_update!r}")
                
                    # An empty/no-op update is not necessarily an error.
                    if state_update is None:
                        print(
                            f"[GRAPH DEBUG] Node '{node}' produced no state updates. "
                            "This is acceptable for a side-effect-only node."
                        )
                        continue
                    
                    if not isinstance(state_update, dict):
                        print(
                            f"[GRAPH ERROR] Unexpected update from '{node}': "
                            f"{state_update!r} "
                            f"(type: {type(state_update).__name__})"
                        )
                        continue
                    
                    filtered_update = {
                        key: value
                        for key, value in state_update.items()
                        if value is not None
                    }
                
                    if (
                        node == "extractor"
                        and not filtered_update.get("user_name")
                        and current_state.get("user_name")
                    ):
                        filtered_update["user_name"] = current_state["user_name"]
                
                    current_state.update(filtered_update)
                
                    print(
                        f"[GRAPH DEBUG] Applied keys from {node}: "
                        f"{list(filtered_update.keys())}"
                    )

            # Ask for missing measurements only for diet-planning requests.
            if current_state.get("intent") == "plan_new_diet":
                if (
                    current_state.get("height") is None
                    or current_state.get("weight") is None
                ):
                    print(
                        "Agent: I still need your height and weight "
                        "to calculate your BMI. Please include them "
                        "in your next message."
                    )

            # Display the most recent response, if one was produced.
            response = current_state.get("final_response")
            if response:
                print(f"\nAgent: {response}")

        except Exception as e:
            print(f"An error occurred while processing your request: {e}")


# Register graph nodes.
workflow_graph.add_node("extractor", extractor_node)
workflow_graph.add_node("save_profile", save_profile_node)
workflow_graph.add_node("nutritionist", nutritionist_team)
workflow_graph.add_node("diet_architect", planner_agent)
workflow_graph.add_node("tracker", tracker_agent)
workflow_graph.add_node("kb_responder", kb_responder_node)


# Entry point.
workflow_graph.add_edge(START, "extractor")


# Route requests based on the extracted intent.
workflow_graph.add_conditional_edges(
    "extractor",
    unified_router,
    {
        "tracker": "tracker",
        "save_profile": "save_profile",
        "kb_responder": "kb_responder",
        "ask_more_info": END,
    },
)


# Profile persistence happens before diet generation.
workflow_graph.add_edge("save_profile", "nutritionist")
workflow_graph.add_edge("nutritionist", "diet_architect")


# Terminal edges.
workflow_graph.add_edge("diet_architect", END)
workflow_graph.add_edge("tracker", END)
workflow_graph.add_edge("kb_responder", END)


# Compile the application graph.
app = workflow_graph.compile()


if __name__ == "__main__":
    init_db()
    asyncio.run(run_interaction())
