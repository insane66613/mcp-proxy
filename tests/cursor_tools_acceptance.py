"""Read-only production-parity acceptance for Cursor Commander proxy."""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    async with (
        streamablehttp_client(
            sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18766/mcp/"
        ) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert len(names) == 8
        assert {"cursor_dashboard", "cursor_chatgpt_claim", "cursor_chatgpt_reply"} <= names
        dashboard = await session.call_tool("cursor_dashboard", {})
        assert not dashboard.isError
        assert dashboard.structuredContent is not None
        jobs = dashboard.structuredContent.get("jobs", [])
        active = sum(
            1
            for job in jobs
            if job.get("status") in {"queued", "running", "pending", "in_progress"}
        )
        print(f"CURSOR_DASHBOARD_READ_ONLY=PASS jobs_count={len(jobs)} active_count={active}")
        print("CURSOR_HTTP_TOOLS_LIST=PASS count=8")


if __name__ == "__main__":
    asyncio.run(main())
