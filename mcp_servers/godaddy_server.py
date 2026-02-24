import os
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP

GODADDY_MCP_URL = os.getenv("GODADDY_MCP_URL", "https://api.godaddy.com/v1/domains/mcp")

mcp = FastMCP("godaddy-tools", host="0.0.0.0", port=9003)


async def _call_godaddy_tool(tool_name: str, args: dict):
    async with streamable_http_client(GODADDY_MCP_URL, terminate_on_close=False) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            content = result.content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                    elif isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            return str(content)


@mcp.tool()
async def godaddy_tool(tool_name: str, args: dict) -> str:
    """Call a GoDaddy MCP tool by name with arguments."""
    result = await _call_godaddy_tool(tool_name, args)
    return f"[godaddy_tool:{tool_name}]\n{result}"

if __name__ == "__main__":
    print("Starting godaddy-tools MCP server...")
    mcp.run(transport="streamable-http")
