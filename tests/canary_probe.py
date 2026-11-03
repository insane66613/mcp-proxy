"""Probe a loopback MCP proxy and validate an actual tool call."""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def probe() -> None:
    """Assert that the candidate proxy can initialize, list, and call a tool."""
    async with (
        streamablehttp_client("http://127.0.0.1:18766/mcp/") as (read, write, _),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {"echo_canary"}
        result = await client.call_tool("echo_canary", {"value": "proxy-014-verified"})
        assert len(result.content) == 1
        assert result.content[0].text == "proxy-014-verified"
    print("MCP_CANARY_VERIFIED")  # noqa: T201 - explicit CLI test receipt


if __name__ == "__main__":
    asyncio.run(probe())
