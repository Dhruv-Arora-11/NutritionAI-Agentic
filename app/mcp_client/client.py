from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

# Global client (same server as before)
client = MultiServerMCPClient({
    "math": {
        "transport": "sse",
        "url": "http://localhost:8000/sse"
    }
})

# Cache tools (avoid reloading every time)
_tools_cache = None

async def _get_tools():
    tools = await client.get_tools()
    return tools


async def call_mcp_tool(tool_name: str, arguments: dict):
    try:
        tools = await _get_tools()

        # traversing tools
        tool = None
        for t in tools:
            if t.name == tool_name:
                tool = t
                break

        if tool is None:
            raise Exception(f"Tool '{tool_name}' not found")

        print(f"--- LOG: Client calling tool '{tool_name}' with {arguments} ---")

        # Call tool
        result = await tool.ainvoke(arguments)

        print("got result")

        return result

    except Exception as e:
        print(f"--- ERROR: MCP Client failed: {e} ---")
        return {"error": str(e)}