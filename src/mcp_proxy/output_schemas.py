"""Output schema enrichment for proxied MCP tools.

This module keeps upstream MCP servers untouched. It only adds permissive JSON
Schemas to tool descriptors returned by mcp-proxy when a known proxied tool does
not already declare an outputSchema.
"""

from __future__ import annotations

from typing import Any

GENERIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}

ANY_JSON_SCHEMA: dict[str, Any] = {}

TEXT_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "content": {"type": ["string", "array", "object", "null"]},
        "message": {"type": ["string", "null"]},
        "success": {"type": ["boolean", "null"]},
    },
    "additionalProperties": True,
}

DESKTOP_COMMANDER_TOOL_NAMES: set[str] = {
    "create_directory", "edit_block", "force_terminate", "get_config",
    "get_file_info", "get_more_search_results", "get_prompts",
    "get_recent_tool_calls", "get_usage_stats",
    "give_feedback_to_desktop_commander", "interact_with_process",
    "kill_process", "list_directory", "list_processes", "list_searches",
    "list_sessions", "move_file", "read_file", "read_multiple_files",
    "read_process_output", "set_config_value", "start_process",
    "start_search", "stop_search", "write_file", "write_pdf",
}

NOTION_AWKOY_TOOL_NAMES: set[str] = {
    "notion-awkoy_notion_describe",
    "notion-awkoy_notion_execute",
}

PORTAL_TOOL_NAMES: set[str] = {
    "portal_list_servers",
}

NOTION_ERROR_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "code": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
        "details": ANY_JSON_SCHEMA,
        "schema": {"type": ["object", "null"], "additionalProperties": True},
        "example": {"type": ["object", "null"], "additionalProperties": True},
    },
    "additionalProperties": True,
}

NOTION_DESCRIBE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "operation", "schema", "example", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "operation": {
            "type": "string",
            "description": "The Notion operation being described.",
        },
        "schema": {
            "type": "object",
            "description": "JSON Schema for the payload accepted by notion_execute.",
            "additionalProperties": True,
        },
        "example": {
            "type": "object",
            "description": "Working example payload for this operation.",
            "additionalProperties": True,
        },
        "examples": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        },
        "notes": {"type": "array", "items": {"type": "string"}},
        "error": NOTION_ERROR_SCHEMA,
    },
    "additionalProperties": True,
}

NOTION_BATCH_ITEM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "index", "result", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "index": {"type": "integer"},
        "id": {"type": ["string", "null"]},
        "operation": {"type": ["string", "null"]},
        "result": ANY_JSON_SCHEMA,
        "error": NOTION_ERROR_SCHEMA,
    },
    "additionalProperties": True,
}

NOTION_EXECUTE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "operation", "mode", "result", "results", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "operation": {"type": "string"},
        "mode": {"type": "string", "enum": ["single", "batch"]},
        "result": ANY_JSON_SCHEMA,
        "results": {
            "type": "array",
            "items": NOTION_BATCH_ITEM_OUTPUT_SCHEMA,
        },
        "error": NOTION_ERROR_SCHEMA,
        "request_id": {"type": ["string", "null"]},
        "idempotency_key": {"type": ["string", "null"]},
        "notion_response": {
            "type": ["object", "null"],
            "description": "Raw Notion SDK response, only returned when verbose=true.",
            "additionalProperties": True,
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": True,
}

PORTAL_LIST_SERVERS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "servers", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "servers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "enabled"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "description": {"type": ["string", "null"]},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["available", "disabled", "error", "unknown", None],
                    },
                },
                "additionalProperties": True,
            },
        },
        "error": {
            "type": ["object", "null"],
            "properties": {
                "code": {"type": ["string", "null"]},
                "message": {"type": ["string", "null"]},
                "details": ANY_JSON_SCHEMA,
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_directory": {
        "type": "object",
        "properties": {
            "fileName": {"type": ["string", "null"]},
            "filePath": {"type": ["string", "null"]},
            "fileType": {"type": ["string", "null"]},
            "entries": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
        },
        "additionalProperties": True,
    },
    "get_config": {
        "type": "object",
        "properties": {
            "config": {"type": "object", "additionalProperties": True},
            "entries": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "uiHints": {"type": ["object", "null"], "additionalProperties": True},
        },
        "additionalProperties": True,
    },
    "read_file": {
        "type": "object",
        "properties": {
            "fileName": {"type": ["string", "null"]},
            "filePath": {"type": ["string", "null"]},
            "fileType": {"type": ["string", "null"]},
            "content": {"type": ["string", "array", "object", "null"]},
            "totalLines": {"type": ["integer", "number", "null"]},
            "offset": {"type": ["integer", "number", "null"]},
        },
        "additionalProperties": True,
    },
    "read_multiple_files": {
        "type": "object",
        "properties": {
            "files": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "results": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
        },
        "additionalProperties": True,
    },
    "get_file_info": {
        "type": "object",
        "properties": {
            "path": {"type": ["string", "null"]},
            "type": {"type": ["string", "null"]},
            "size": {"type": ["integer", "number", "null"]},
            "created": {"type": ["string", "null"]},
            "modified": {"type": ["string", "null"]},
            "lineCount": {"type": ["integer", "number", "null"]},
            "sheets": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
        },
        "additionalProperties": True,
    },
    "start_process": {
        "type": "object",
        "properties": {
            "pid": {"type": ["integer", "number", "null"]},
            "text": {"type": ["string", "null"]},
            "output": {"type": ["string", "null"]},
            "isBlocked": {"type": ["boolean", "null"]},
            "state": {"type": ["string", "null"]},
            "exitCode": {"type": ["integer", "number", "null"]},
        },
        "additionalProperties": True,
    },
    "read_process_output": {
        "type": "object",
        "properties": {
            "pid": {"type": ["integer", "number", "null"]},
            "text": {"type": ["string", "null"]},
            "output": {"type": ["string", "null"]},
            "isBlocked": {"type": ["boolean", "null"]},
            "isFinished": {"type": ["boolean", "null"]},
            "totalLines": {"type": ["integer", "number", "null"]},
        },
        "additionalProperties": True,
    },
    "list_processes": {
        "type": "object",
        "properties": {
            "processes": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "text": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
    "list_sessions": {
        "type": "object",
        "properties": {
            "sessions": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "text": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
    "start_search": {
        "type": "object",
        "properties": {
            "searchId": {"type": ["string", "integer", "number", "null"]},
            "id": {"type": ["string", "integer", "number", "null"]},
            "status": {"type": ["string", "null"]},
            "text": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
    "get_more_search_results": {
        "type": "object",
        "properties": {
            "results": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "status": {"type": ["string", "null"]},
            "text": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
    "list_searches": {
        "type": "object",
        "properties": {
            "searches": {"type": ["array", "null"], "items": {"type": "object", "additionalProperties": True}},
            "text": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
    "write_file": TEXT_RESULT_SCHEMA,
    "edit_block": TEXT_RESULT_SCHEMA,
    "create_directory": TEXT_RESULT_SCHEMA,
    "move_file": TEXT_RESULT_SCHEMA,
    "kill_process": TEXT_RESULT_SCHEMA,
    "force_terminate": TEXT_RESULT_SCHEMA,
    "set_config_value": TEXT_RESULT_SCHEMA,
    "stop_search": TEXT_RESULT_SCHEMA,
    "write_pdf": TEXT_RESULT_SCHEMA,
    "get_usage_stats": GENERIC_OUTPUT_SCHEMA,
    "get_recent_tool_calls": GENERIC_OUTPUT_SCHEMA,
    "get_prompts": GENERIC_OUTPUT_SCHEMA,
    "give_feedback_to_desktop_commander": TEXT_RESULT_SCHEMA,
    "notion-awkoy_notion_describe": NOTION_DESCRIBE_OUTPUT_SCHEMA,
    "notion-awkoy_notion_execute": NOTION_EXECUTE_OUTPUT_SCHEMA,
    "portal_list_servers": PORTAL_LIST_SERVERS_OUTPUT_SCHEMA,
}


def _base_tool_name(name: str) -> str:
    """Return an unprefixed Desktop Commander tool name."""
    if name.startswith("desktop-commander_"):
        return name[len("desktop-commander_"):]
    return name


def output_schema_for_tool(name: str) -> dict[str, Any] | None:
    """Return a permissive output schema for known proxied tools."""
    if name in NOTION_AWKOY_TOOL_NAMES or name in PORTAL_TOOL_NAMES:
        return OUTPUT_SCHEMAS[name]

    base_name = _base_tool_name(name)
    if base_name not in DESKTOP_COMMANDER_TOOL_NAMES:
        return None
    return OUTPUT_SCHEMAS.get(base_name, GENERIC_OUTPUT_SCHEMA)


def apply_output_schemas(list_tools_result: Any) -> Any:
    """Mutate a ListToolsResult so known proxied tools include outputSchema."""
    for tool in getattr(list_tools_result, "tools", []) or []:
        schema = output_schema_for_tool(getattr(tool, "name", ""))
        if not schema:
            continue
        if getattr(tool, "outputSchema", None) is None:
            tool.outputSchema = schema
    return list_tools_result


# Backward-compatible import for existing proxy_server.py code.
apply_desktop_commander_output_schemas = apply_output_schemas
