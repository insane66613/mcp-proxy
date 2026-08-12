"""Tests for Desktop Commander output schema enrichment."""

from mcp import types

from mcp_proxy.output_schemas import (
    OUTPUT_SCHEMAS,
    apply_output_schemas,
    output_schema_for_tool,
)
from mcp_proxy.structured_content import enrich_call_tool_result


def test_widget_only_file_tools_do_not_get_model_facing_output_schemas() -> None:
    for name in ("read_file", "write_file", "edit_block", "list_directory"):
        assert output_schema_for_tool(f"desktop-commander_{name}") is None


def test_apply_output_schemas_overwrites_existing_schema() -> None:
    weak = {"type": "object", "properties": {"text": {"type": "string"}}}
    tools = types.ListToolsResult(
        tools=[
            types.Tool(
                name="desktop-commander_start_process",
                description="start process",
                inputSchema={"type": "object"},
                outputSchema=weak,
            )
        ]
    )
    apply_output_schemas(tools)
    assert tools.tools[0].outputSchema == OUTPUT_SCHEMAS["start_process"]
    assert "pid" in tools.tools[0].outputSchema["properties"]


def test_enrich_start_process_structured_content() -> None:
    result = types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text="Process started with PID 4242 (shell: pwsh)\nInitial output:\nhello",
            )
        ]
    )
    enrich_call_tool_result("desktop-commander_start_process", result)
    assert result.structuredContent is not None
    assert result.structuredContent["pid"] == 4242
    assert result.structuredContent["success"] is True


def test_enrich_preserves_existing_file_preview() -> None:
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="file body")],
        structuredContent={
            "fileName": "demo.txt",
            "filePath": "X:\\demo.txt",
            "fileType": "text",
        },
    )
    enrich_call_tool_result("read_file", result)
    assert result.structuredContent["path"] == "X:\\demo.txt"
    assert result.structuredContent["name"] == "demo.txt"


def test_enrich_recent_tool_calls_parses_json() -> None:
    payload = [{"tool": "read_file", "timestamp": "now"}]
    result = types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"Tool Call History (1 results, 1 total in memory)\n\n{payload}".replace("'", '"'),
            )
        ]
    )
    enrich_call_tool_result("get_recent_tool_calls", result)
    assert result.structuredContent is not None
    assert result.structuredContent["count"] == 1
