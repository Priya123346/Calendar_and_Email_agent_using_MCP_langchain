from contextlib import AsyncExitStack
from langchain_core.tools import StructuredTool
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession


async def load_mcp_tools(server_urls, stack: AsyncExitStack):
    tools = []

    for url in server_urls:
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(url)
        )
        session = ClientSession(read_stream, write_stream)
        await stack.enter_async_context(session)
        await session.initialize()
        mcp_tools = await session.list_tools()
        for t in mcp_tools.tools:
            session_ref = session
            tool_name = t.name
            ArgsModel = t.inputSchema
            async def call_tool(_session=session_ref, _name=tool_name, **kwargs):
                result = await _session.call_tool(_name, kwargs)
                return result.content
            tools.append(
                StructuredTool.from_function(
                    name=t.name,
                    description=t.description,
                    coroutine=call_tool,
                    args_schema=ArgsModel,
                )
            )

    return tools
