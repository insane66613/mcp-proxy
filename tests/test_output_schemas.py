"""Tests for Desktop Commander output schema enrichment."""

import jsonschema
import pytest
from mcp import types

from mcp_proxy.output_schemas import (
    OUTPUT_SCHEMAS,
    apply_output_schemas,
    output_schema_for_tool,
)
from mcp_proxy.structured_content import enrich_call_tool_result


def test_file_tools_advertise_lean_model_and_optional_widget_output_schemas() -> None:
    """File schemas require a result flag while allowing optional rich preview metadata."""
    for name in ("read_file", "write_file", "edit_block", "list_directory"):
        schema = output_schema_for_tool(f"desktop-commander_{name}")
        assert schema is not None
        assert schema["required"] == ["success"]
        jsonschema.Draft202012Validator.check_schema(schema)
        tools = types.ListToolsResult(tools=[types.Tool(name=name, inputSchema={"type": "object"})])
        apply_output_schemas(tools)
        assert tools.tools[0].outputSchema == schema


@pytest.mark.parametrize("name", ["read_file", "write_file", "edit_block", "list_directory"])
@pytest.mark.parametrize("kind", ["text", "image", "empty"])
@pytest.mark.parametrize("is_error", [False, True])
def test_file_results_do_not_duplicate_payloads(name: str, kind: str, is_error: bool) -> None:
    """Plain/image/empty model results validate without copying their potentially large content."""
    content: list[types.Content] = []
    if kind == "text":
        content = [types.TextContent(type="text", text="large body\n" * 100)]
    elif kind == "image":
        content = [types.ImageContent(type="image", data="AA==", mimeType="image/png")]
    result = types.CallToolResult(content=content, isError=is_error)
    original = result.model_dump()
    enrich_call_tool_result(f"desktop-commander_{name}", result)
    assert result.structuredContent == {"success": not is_error}
    assert result.model_dump()["content"] == original["content"]
    assert result.isError == is_error
    jsonschema.validate(result.structuredContent, output_schema_for_tool(name))


@pytest.mark.parametrize("name", ["read_file", "write_file", "edit_block", "list_directory"])
@pytest.mark.parametrize("is_error", [False, True])
def test_file_widget_metadata_is_preserved(name: str, is_error: bool) -> None:
    """Rich UI results retain their metadata, aliases and accurate failure flag."""
    existing = {
        "filePath": "X:\\demo.png",
        "fileName": "demo.png",
        "fileType": "image",
        "imageData": "AA==",
        "mimeType": "image/png",
        "content": "widget preview",
        "success": is_error,
    }
    result = types.CallToolResult(content=[], structuredContent=existing, isError=is_error)
    enrich_call_tool_result(name, result)
    assert result.structuredContent == {
        **existing,
        "path": existing["filePath"],
        "name": existing["fileName"],
        "success": not is_error,
    }
    jsonschema.validate(result.structuredContent, output_schema_for_tool(name))
    assert existing["success"] == is_error


def test_apply_output_schemas_overwrites_existing_schema() -> None:
    """Managed tools receive the canonical output schema."""
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
    """Validate structured process metadata."""
    expected_pid = 4242
    result = types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=(
                    f"Process started with PID {expected_pid} (shell: pwsh)\nInitial output:\nhello"
                ),
            )
        ]
    )
    enrich_call_tool_result("desktop-commander_start_process", result)
    assert result.structuredContent is not None
    assert result.structuredContent["pid"] == expected_pid
    assert result.structuredContent["success"] is True


def test_enrich_preserves_existing_file_preview() -> None:
    """Explicit file metadata is normalized without losing its content."""
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
    """Recent tool-call entries retain their JSON representation."""
    payload = [{"tool": "read_file", "timestamp": "now"}]
    result = types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=f"Tool Call History (1 results, 1 total in memory)\n\n{payload}".replace(
                    "'", '"'
                ),
            )
        ]
    )
    enrich_call_tool_result("get_recent_tool_calls", result)
    assert result.structuredContent is not None
    assert result.structuredContent["count"] == 1
