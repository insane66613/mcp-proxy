"""Read-only live MCP transport identity and tool-contract probe."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError


async def probe(url: str, receipt: Path) -> None:
    """Record a read-only service identity and tool-manifest fingerprint."""
    async with (
        streamablehttp_client(url) as (read, write, _),
        ClientSession(read, write) as client,
    ):
        info = await client.initialize()
        assert info.serverInfo.name == "cursor-commander"
        try:
            tools = await client.list_tools()
        except McpError as exc:
            message = exc.error.message
            digest = hashlib.sha256(message.encode()).hexdigest()
            print(  # noqa: T201 - operator diagnostic, without exposing contents
                f"TOOLS_LIST_FAILURE code={exc.error.code} sha256={digest}"
            )
            raise
        names = sorted(tool.name for tool in tools.tools)
        assert names
    digest = hashlib.sha256("\n".join(names).encode()).hexdigest()
    await asyncio.to_thread(
        receipt.write_text,
        json.dumps(
            {
                "server": info.serverInfo.name,
                "count": len(names),
                "sha256": digest,
                "tools": names,
            },
            indent=2,
        ),
    )
    print(f"MCP_PROBE_OK server={info.serverInfo.name} tools={len(names)} sha256={digest}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(probe(sys.argv[1], Path(sys.argv[2])))
