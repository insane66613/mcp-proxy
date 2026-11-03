"""Temporary local MCP echo backend for release-canary validation."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sanitycloud-mcp-proxy-canary")


@mcp.tool()
def echo_canary(value: str) -> str:
    """Return the provided string unchanged."""
    return value


if __name__ == "__main__":
    mcp.run(transport="stdio")
