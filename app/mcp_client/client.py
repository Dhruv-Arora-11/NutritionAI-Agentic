from mcp import ClientSession
from mcp.client.sse import sse_client
import asyncio

async def call_mcp_tool(tool_name: str, arguments: dict):
    """
    The 'Universal Remote' that connects to your MCP Server 
    and executes ANY tool by name.
    """
    url = "http://localhost:8000/sse"
    
    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                # 1. Initialize the connection
                await session.initialize()
                print("server initialized")
                
                print(f"--- LOG: Client calling tool '{tool_name}' with {arguments} ---")
                result = await session.call_tool(tool_name, arguments)
                print(result)
                print("got result")
                
                # 3. FastMCP tools usually return a list of content blocks
                # We extract the 'text' which is our JSON/Dict result
                if result.content and len(result.content) > 0:
                    import json
                    # Convert the string output from the tool back into a Python Dict
                    return json.loads(result.content[0].text)
                
                return None
                
    except Exception as e:
        print(f"--- ERROR: MCP Client failed: {e} ---")
        return {"error": str(e)}