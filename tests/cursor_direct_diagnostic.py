"""Read-only Cursor Commander direct stdio parity diagnostic."""

# ruff: noqa: T201 - CLI-only evidence receipts are printed intentionally.

import asyncio
import hashlib

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

COMMAND = r"X:\Code\cursor-commander\.venv\Scripts\cursor-commander.exe"
ROOT = r"X:\Code\cursor-commander"


async def main() -> None:
    """Print direct-stdio tool-list evidence for operator inspection."""
    params = StdioServerParameters(command=COMMAND, args=["mcp"], cwd=ROOT, env={})
    async with stdio_client(params) as (reader, writer):  # noqa: SIM117
        async with ClientSession(reader, writer) as session:
            info = await session.initialize()
            print("DIRECT_IDENTITY", info.serverInfo.name, info.serverInfo.version)
            try:
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                digest = hashlib.sha256(",".join(names).encode()).hexdigest()
                print("DIRECT_TOOLS", len(names), digest, names)
            except Exception as exc:
                print("DIRECT_ERROR", type(exc).__name__, repr(str(exc))[:100], repr(exc)[:150])
                raise


if __name__ == "__main__":
    asyncio.run(main())
