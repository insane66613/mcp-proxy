"""Output schema enrichment for proxied MCP tools.

Keeps upstream MCP servers untouched while advertising accurate JSON Schemas and
letting structured_content.py align runtime payloads with those schemas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp import types

ANY_JSON_SCHEMA: dict[str, Any] = {}

DESKTOP_COMMANDER_TOOL_NAMES: set[str] = {
    "create_directory",
    "edit_block",
    "force_terminate",
    "get_config",
    "get_file_info",
    "get_more_search_results",
    "get_prompts",
    "get_recent_tool_calls",
    "get_usage_stats",
    "give_feedback_to_desktop_commander",
    "interact_with_process",
    "kill_process",
    "list_directory",
    "list_processes",
    "list_searches",
    "list_sessions",
    "move_file",
    "read_file",
    "read_multiple_files",
    "read_process_output",
    "set_config_value",
    "start_process",
    "start_search",
    "stop_search",
    "write_file",
    "write_pdf",
}

NOTION_AWKOY_TOOL_NAMES: set[str] = {
    "notion-awkoy_notion_describe",
    "notion-awkoy_notion_execute",
}

PORTAL_TOOL_NAMES: set[str] = {
    "portal_list_servers",
    "portal_toggle_servers",
    "portal_toggle_single_server",
}

JULES_TOOL_NAMES: set[str] = {
    "get_bash_outputs",
    "create_session",
    "list_sessions",
    "query_cache",
    "get_code_review_context",
    "send_reply_to_session",
    "get_session_state",
    "show_code_diff",
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

FILE_PREVIEW_PROPERTIES: dict[str, Any] = {
    "fileName": {"type": ["string", "null"]},
    "filePath": {"type": ["string", "null"]},
    "name": {"type": ["string", "null"]},
    "path": {"type": ["string", "null"]},
    "fileType": {
        "type": ["string", "null"],
        "description": "Preview type such as text, markdown, html, image, directory, unsupported.",
    },
    "content": {"type": ["string", "array", "object", "null"]},
    "imageData": {"type": ["string", "null"]},
    "mimeType": {"type": ["string", "null"]},
}

FILE_PREVIEW_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": FILE_PREVIEW_PROPERTIES,
    "additionalProperties": True,
}

ACTION_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text", "success"],
    "properties": {
        "text": {"type": "string"},
        "message": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
        "detail": {"type": ["string", "null"]},
        "error": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

CONFIG_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["key", "value", "valueType", "editable"],
    "properties": {
        "key": {"type": "string"},
        "value": ANY_JSON_SCHEMA,
        "valueType": {"type": "string"},
        "editable": {"type": "boolean"},
    },
    "additionalProperties": True,
}

GET_CONFIG_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["config", "entries"],
    "properties": {
        "config": {"type": "object", "additionalProperties": True},
        "entries": {"type": "array", "items": CONFIG_ENTRY_SCHEMA},
        "uiHints": {"type": ["object", "null"], "additionalProperties": True},
    },
    "additionalProperties": True,
}

SET_CONFIG_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text", "success"],
    "properties": {
        "text": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": ["string", "null"]},
        "config": {"type": ["object", "null"], "additionalProperties": True},
        "error": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

READ_FILE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["filePath", "fileType"],
    "properties": {
        **FILE_PREVIEW_PROPERTIES,
        "totalLines": {"type": ["integer", "number", "null"]},
        "offset": {"type": ["integer", "number", "null"]},
        "length": {"type": ["integer", "number", "null"]},
    },
    "additionalProperties": True,
}

READ_MULTIPLE_FILES_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "success"],
    "properties": {
        "summary": {"type": "string"},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
        "files": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": ["string", "null"]},
                    "error": {"type": ["string", "null"]},
                    "mimeType": {"type": ["string", "null"]},
                    "isImage": {"type": ["boolean", "null"]},
                    "isPdf": {"type": ["boolean", "null"]},
                    "content": {"type": ["string", "null"]},
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}

FILE_INFO_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["info", "success"],
    "properties": {
        "info": {"type": "object", "additionalProperties": True},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
        "error": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

PROCESS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text", "success"],
    "properties": {
        "pid": {"type": ["integer", "number", "null"]},
        "text": {"type": "string"},
        "output": {"type": ["string", "null"]},
        "isBlocked": {"type": ["boolean", "null"]},
        "isFinished": {"type": ["boolean", "null"]},
        "exitCode": {"type": ["integer", "number", "null"]},
        "state": {
            "type": ["string", "null"],
            "enum": ["running", "blocked", "finished", None],
        },
        "success": {"type": "boolean"},
        "error": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

SEARCH_RESULT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": ["string", "null"], "enum": ["content", "file", None]},
        "file": {"type": ["string", "null"]},
        "line": {"type": ["integer", "number", "null"]},
        "match": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

SEARCH_SESSION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["sessionId", "status", "success"],
    "properties": {
        "sessionId": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": ["RUNNING", "COMPLETED", "IN_PROGRESS", "ERROR"]},
        "pattern": {"type": ["string", "null"]},
        "path": {"type": ["string", "null"]},
        "totalResults": {"type": ["integer", "number", "null"]},
        "isComplete": {"type": ["boolean", "null"]},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
        "results": {"type": ["array", "null"], "items": SEARCH_RESULT_ITEM_SCHEMA},
    },
    "additionalProperties": True,
}

SEARCH_MORE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["sessionId", "status", "success"],
    "properties": {
        "sessionId": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": ["IN_PROGRESS", "COMPLETED", "ERROR"]},
        "totalResults": {"type": ["integer", "number", "null"]},
        "totalMatches": {"type": ["integer", "number", "null"]},
        "returnedCount": {"type": ["integer", "number", "null"]},
        "hasMoreResults": {"type": ["boolean", "null"]},
        "isComplete": {"type": ["boolean", "null"]},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
        "results": {"type": ["array", "null"], "items": SEARCH_RESULT_ITEM_SCHEMA},
    },
    "additionalProperties": True,
}

SEARCH_LIST_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["searches", "count", "success"],
    "properties": {
        "searches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": ["string", "null"]},
                    "pattern": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                    "totalResults": {"type": ["integer", "number", "null"]},
                },
                "additionalProperties": True,
            },
        },
        "count": {"type": "integer"},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

PROCESS_LIST_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pid": {"type": ["integer", "number", "null"]},
        "command": {"type": ["string", "null"]},
        "cpu": {"type": ["string", "null"]},
        "memory": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

LIST_PROCESSES_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["processes", "success"],
    "properties": {
        "processes": {"type": "array", "items": PROCESS_LIST_ITEM_SCHEMA},
        "count": {"type": ["integer", "number", "null"]},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

SESSION_LIST_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pid": {"type": ["integer", "number", "null"]},
        "type": {"type": ["string", "null"], "enum": ["shell", "node:local", None]},
        "isBlocked": {"type": ["boolean", "null"]},
        "runtimeSeconds": {"type": ["integer", "number", "null"]},
    },
    "additionalProperties": True,
}

LIST_SESSIONS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["sessions", "success"],
    "properties": {
        "sessions": {"type": "array", "items": SESSION_LIST_ITEM_SCHEMA},
        "count": {"type": ["integer", "number", "null"]},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

RECENT_TOOL_CALLS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["calls", "success"],
    "properties": {
        "summary": {"type": ["string", "null"]},
        "calls": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "count": {"type": ["integer", "number", "null"]},
        "text": {"type": ["string", "null"]},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

USAGE_STATS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text", "success"],
    "properties": {
        "text": {"type": "string"},
        "success": {"type": "boolean"},
        "stats": {"type": ["object", "null"], "additionalProperties": True},
    },
    "additionalProperties": True,
}

PROMPTS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text", "success"],
    "properties": {
        "text": {"type": "string"},
        "success": {"type": "boolean"},
        "prompt": {"type": ["object", "null"], "additionalProperties": True},
        "prompts": {
            "type": ["array", "null"],
            "items": {"type": "object", "additionalProperties": True},
        },
    },
    "additionalProperties": True,
}

NOTION_DESCRIBE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "operation", "schema", "example", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "operation": {"type": "string"},
        "schema": {"type": "object", "additionalProperties": True},
        "example": {"type": "object", "additionalProperties": True},
        "examples": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
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
        "results": {"type": "array", "items": NOTION_BATCH_ITEM_OUTPUT_SCHEMA},
        "error": NOTION_ERROR_SCHEMA,
        "request_id": {"type": ["string", "null"]},
        "idempotency_key": {"type": ["string", "null"]},
        "notion_response": {"type": ["object", "null"], "additionalProperties": True},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": True,
}

PORTAL_ERROR_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "code": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
        "details": ANY_JSON_SCHEMA,
    },
    "additionalProperties": True,
}

PORTAL_SERVER_SCHEMA: dict[str, Any] = {
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
}

PORTAL_LIST_SERVERS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "servers", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "servers": {"type": "array", "items": PORTAL_SERVER_SCHEMA},
        "error": PORTAL_ERROR_SCHEMA,
        "text": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

PORTAL_TOGGLE_SERVERS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "url", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "url": {"type": ["string", "null"]},
        "selectionUrl": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
        "text": {"type": ["string", "null"]},
        "error": PORTAL_ERROR_SCHEMA,
    },
    "additionalProperties": True,
}

PORTAL_TOGGLE_SINGLE_SERVER_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ok", "server_id", "action", "enabled", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "server_id": {"type": ["string", "null"]},
        "serverId": {"type": ["string", "null"]},
        "action": {"type": ["string", "null"], "enum": ["toggle", "untoggle", None]},
        "enabled": {"type": ["boolean", "null"]},
        "server": PORTAL_SERVER_SCHEMA,
        "message": {"type": ["string", "null"]},
        "text": {"type": ["string", "null"]},
        "error": PORTAL_ERROR_SCHEMA,
    },
    "additionalProperties": True,
}

JULES_GENERIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}

OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_config": GET_CONFIG_OUTPUT_SCHEMA,
    "set_config_value": SET_CONFIG_OUTPUT_SCHEMA,
    "read_multiple_files": READ_MULTIPLE_FILES_OUTPUT_SCHEMA,
    "write_pdf": ACTION_RESULT_SCHEMA,
    "create_directory": ACTION_RESULT_SCHEMA,
    "move_file": ACTION_RESULT_SCHEMA,
    "get_file_info": FILE_INFO_OUTPUT_SCHEMA,
    "start_process": PROCESS_OUTPUT_SCHEMA,
    "read_process_output": PROCESS_OUTPUT_SCHEMA,
    "interact_with_process": PROCESS_OUTPUT_SCHEMA,
    "force_terminate": ACTION_RESULT_SCHEMA,
    "list_sessions": LIST_SESSIONS_OUTPUT_SCHEMA,
    "list_processes": LIST_PROCESSES_OUTPUT_SCHEMA,
    "kill_process": ACTION_RESULT_SCHEMA,
    "start_search": SEARCH_SESSION_OUTPUT_SCHEMA,
    "get_more_search_results": SEARCH_MORE_OUTPUT_SCHEMA,
    "stop_search": ACTION_RESULT_SCHEMA,
    "list_searches": SEARCH_LIST_OUTPUT_SCHEMA,
    "get_usage_stats": USAGE_STATS_OUTPUT_SCHEMA,
    "get_recent_tool_calls": RECENT_TOOL_CALLS_OUTPUT_SCHEMA,
    "get_prompts": PROMPTS_OUTPUT_SCHEMA,
    "give_feedback_to_desktop_commander": ACTION_RESULT_SCHEMA,
    "notion-awkoy_notion_describe": NOTION_DESCRIBE_OUTPUT_SCHEMA,
    "notion-awkoy_notion_execute": NOTION_EXECUTE_OUTPUT_SCHEMA,
    "portal_list_servers": PORTAL_LIST_SERVERS_OUTPUT_SCHEMA,
    "portal_toggle_servers": PORTAL_TOGGLE_SERVERS_OUTPUT_SCHEMA,
    "portal_toggle_single_server": PORTAL_TOGGLE_SINGLE_SERVER_OUTPUT_SCHEMA,
    "get_bash_outputs": JULES_GENERIC_OUTPUT_SCHEMA,
    "create_session": JULES_GENERIC_OUTPUT_SCHEMA,
    "query_cache": JULES_GENERIC_OUTPUT_SCHEMA,
    "get_code_review_context": JULES_GENERIC_OUTPUT_SCHEMA,
    "send_reply_to_session": JULES_GENERIC_OUTPUT_SCHEMA,
    "get_session_state": JULES_GENERIC_OUTPUT_SCHEMA,
    "show_code_diff": JULES_GENERIC_OUTPUT_SCHEMA,
}


def _base_tool_name(name: str) -> str:
    """Return an unprefixed Desktop Commander tool name."""
    if name.startswith("desktop-commander_"):
        return name[len("desktop-commander_") :]
    return name


def _is_managed_tool(name: str) -> bool:
    if name in NOTION_AWKOY_TOOL_NAMES or name in PORTAL_TOOL_NAMES:
        return True
    base_name = _base_tool_name(name)
    if base_name in JULES_TOOL_NAMES:
        return True
    return base_name in DESKTOP_COMMANDER_TOOL_NAMES


def output_schema_for_tool(name: str) -> dict[str, Any] | None:
    """Return the canonical output schema for a known proxied tool."""
    if name in NOTION_AWKOY_TOOL_NAMES or name in PORTAL_TOOL_NAMES:
        return OUTPUT_SCHEMAS.get(name)

    base_name = _base_tool_name(name)
    if base_name in JULES_TOOL_NAMES:
        return OUTPUT_SCHEMAS.get(base_name)
    if base_name not in DESKTOP_COMMANDER_TOOL_NAMES:
        return None
    return OUTPUT_SCHEMAS.get(base_name)


def apply_output_schemas(list_tools_result: types.ListToolsResult) -> types.ListToolsResult:
    """Ensure known proxied tools advertise the canonical outputSchema."""
    for tool in getattr(list_tools_result, "tools", []) or []:
        name = getattr(tool, "name", "")
        schema = output_schema_for_tool(name)
        if not schema or not _is_managed_tool(name):
            continue
        tool.outputSchema = schema
    return list_tools_result


apply_desktop_commander_output_schemas = apply_output_schemas
