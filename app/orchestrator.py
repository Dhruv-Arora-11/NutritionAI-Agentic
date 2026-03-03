import asyncio
from agents.extractor import extractor_agent
from agents.nutrition_requirement import nutrition_agent
from agents.critic import critic
from agents.diet_planner import diet_planner
from agents.tracker import tracker
from agent_state import AgentState

async def which_agent_to_run():
    
    user_input = input("Please enter what you want to ask to multi agent system: ")
    
    extracted = await extractor_agent({"user_input": user_input})
    
    intent = extracted.intent
    height = extracted.height
    weight = extracted.weight
    if intent == "bmi":
        result = await nutrition_agent(extracted)
    elif intent == "calorie":
        result = await diet_planner(extracted)
    elif intent == "critic":
        result = await critic(extracted)
    elif intent == "tracker":
        result = await tracker(extracted)
    elif intent == "unclear":
        await which_agent_to_run()
    elif intent == "full_filled":
        print("state")
    else:
        result = "This system handles BMI and calorie queries."
    print("\n--- Extracted Data ---")
    print(extracted)

if __name__ == "__main__":
    asyncio.run(which_agent_to_run())
    
    
    
    
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

workflow = StateGraph(AgentState)

workflow.add_node("extractor", extractor_agent)
workflow.add_node("nutrition_agent", nutrition_agent) # This calls your MCP
workflow.add_node("tracker" , tracker)
workflow.add_node("critic_agent", critic)

workflow.add_edge(START, "extractor")

workflow.add_edge("critic" , END)

workflow.add_conditional_edges(
    "extractor",
    router,
    {
        "calculate": "nutrition_agent",
        "ask_more": END,    # Stops and waits for user input
        "general": END      # Just answers the question
    }
)

workflow.add_edge("nutrition_agent", "critic_agent")
workflow.add_edge("critic_agent", END)

app = workflow.compile(checkpointer=memory)