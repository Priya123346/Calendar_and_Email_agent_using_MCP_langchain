from contextlib import AsyncExitStack
import json
from pathlib import Path

from langchain_core.tools import StructuredTool
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession
import httpx


async def load_mcp_tools(server_urls, stack: AsyncExitStack):
    tools = []
    for url in server_urls:
        try:
            # Preflight connectivity to avoid noisy task group errors on connect failure.
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    await client.post(
                        url,
                        headers={
                            "Accept": "application/json, text/event-stream",
                            "Content-Type": "application/json",
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "preflight", "version": "0.0.1"},
                            },
                        },
                    )
                except Exception as exc:
                    print(f"Warning: unable to reach MCP server {url}: {exc}")
                    continue
            # Temporary session to validate MCP handshake before keeping a long-lived connection.
            try:
                async with streamable_http_client(url, terminate_on_close=True) as (
                    read_stream,
                    write_stream,
                    _,
                ):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        mcp_tools = await session.list_tools()
            except Exception as exc:
                print(f"Warning: MCP handshake failed for {url}: {exc}")
                continue

            # Open persistent session only after successful handshake.
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamable_http_client(url, terminate_on_close=False)
            )
            session = ClientSession(read_stream, write_stream)
            await stack.enter_async_context(session)
            await session.initialize()
        except Exception as exc:
            print(f"Warning: failed to connect to MCP server {url}: {exc}")
            continue

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


def load_mcp_urls_from_file(path: str = "mcp.json") -> list[str]:
    mcp_config_path = Path(path)
    if not mcp_config_path.is_absolute():
        # Resolve relative to project root (mcp_loader.py is in project root).
        mcp_config_path = (Path(__file__).resolve().parent / mcp_config_path).resolve()
    if not mcp_config_path.exists():
        return []
    try:
        mcp_config = json.loads(mcp_config_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    servers = mcp_config.get("mcpServers", {})
    urls = []
    for _, cfg in servers.items():
        url = cfg.get("url")
        if url:
            urls.append(url)
    return urls
