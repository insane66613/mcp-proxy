"""Synthesize structuredContent for proxied tools when upstream omits it."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp import types

from .output_schemas import _base_tool_name

_PID_RE = re.compile(r"\bPID[:\s]+(-?\d+)", re.IGNORECASE)
_SESSION_ID_RE = re.compile(r"session[:\s]+(\S+)", re.IGNORECASE)
_TOTAL_RESULTS_RE = re.compile(r"Total results(?: found)?[:\s]+(\d+)", re.IGNORECASE)
_SUCCESSFULLY_RE = re.compile(r"^Successfully\s+(.+)$", re.IGNORECASE | re.MULTILINE)


def _text_from_content(content: list[types.Content] | None) -> str:
    if not content:
        return ""
    parts: list[str] = []
    for item in content:
        item_type = getattr(item, "type", None)
        if item_type == "text":
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        elif item_type == "image":
            mime = getattr(item, "mimeType", "image")
            parts.append(f"[image:{mime}]")
    return "\n".join(parts)


def _action_result(text: str, *, is_error: bool) -> dict[str, Any]:
    success = not is_error and not text.lower().startswith("error")
    message = text.strip()
    payload: dict[str, Any] = {
        "text": message,
        "success": success,
        "message": message,
    }
    if success:
        match = _SUCCESSFULLY_RE.search(message)
        if match:
            payload["detail"] = match.group(1).strip()
    else:
        payload["error"] = message
    return payload


def _process_fields(text: str) -> dict[str, Any]:
    pid_match = _PID_RE.search(text)
    pid = int(pid_match.group(1)) if pid_match else None
    is_blocked = "Process is running" in text or "read_process_output" in text
    is_finished = any(
        token in text
        for token in (
            "Process exited",
            "exited with code",
            "No active session",
            "terminated",
            "Cleared virtual",
        )
    )
    exit_match = re.search(r"(?:exit(?:ed)?|code)[:\s]+(-?\d+)", text, re.IGNORECASE)
    return {
        "pid": pid,
        "text": text,
        "output": text,
        "isBlocked": is_blocked if not is_finished else False,
        "isFinished": is_finished,
        "exitCode": int(exit_match.group(1)) if exit_match else None,
        "state": "finished" if is_finished else ("blocked" if is_blocked else "running"),
    }


def _search_start_fields(text: str) -> dict[str, Any]:
    session_match = _SESSION_ID_RE.search(text)
    total_match = _TOTAL_RESULTS_RE.search(text)
    return {
        "sessionId": session_match.group(1) if session_match else None,
        "status": "COMPLETED" if "COMPLETED" in text else "RUNNING",
        "text": text,
        "totalResults": int(total_match.group(1)) if total_match else 0,
        "isComplete": "COMPLETED" in text,
    }


def _search_more_fields(text: str) -> dict[str, Any]:
    session_match = _SESSION_ID_RE.search(text)
    total_match = _TOTAL_RESULTS_RE.search(text)
    matches_match = re.search(r"\((\d+)\s+matches\)", text, re.IGNORECASE)
    return {
        "sessionId": session_match.group(1) if session_match else None,
        "status": "COMPLETED" if "COMPLETED" in text else "IN_PROGRESS",
        "text": text,
        "totalResults": int(total_match.group(1)) if total_match else 0,
        "totalMatches": int(matches_match.group(1)) if matches_match else None,
        "isComplete": "COMPLETED" in text,
        "hasMoreResults": "More results available" in text,
    }


def _search_list_fields(text: str) -> dict[str, Any]:
    if "No active searches" in text:
        return {"searches": [], "text": text, "count": 0}
    sessions = []
    for block in re.split(r"\n(?=Session:\s)", text):
        if not block.strip().startswith("Session:"):
            continue
        session_id = re.search(r"Session:\s+(\S+)", block)
        pattern = re.search(r'Pattern:\s+"([^"]*)"', block)
        status = re.search(r"Status:\s+(\S+)", block)
        results = re.search(r"Results:\s+(\d+)", block)
        sessions.append(
            {
                "id": session_id.group(1) if session_id else None,
                "pattern": pattern.group(1) if pattern else None,
                "status": status.group(1) if status else None,
                "totalResults": int(results.group(1)) if results else 0,
            }
        )
    return {"searches": sessions, "text": text, "count": len(sessions)}


def _list_processes_fields(text: str) -> dict[str, Any]:
    processes: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = re.match(
            r"PID:\s*(-?\d+),\s*Command:\s*(.+?),\s*CPU:\s*(\S+),\s*Memory:\s*(\S+)",
            line.strip(),
        )
        if match:
            processes.append(
                {
                    "pid": int(match.group(1)),
                    "command": match.group(2),
                    "cpu": match.group(3),
                    "memory": match.group(4),
                }
            )
    return {"processes": processes, "text": text, "count": len(processes)}


def _list_sessions_fields(text: str) -> dict[str, Any]:
    if "No active sessions" in text:
        return {"sessions": [], "text": text, "count": 0}
    sessions: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("PID:"):
            continue
        pid_match = re.search(r"PID:\s*(-?\d+)", line)
        blocked_match = re.search(r"Blocked:\s*(true|false)", line, re.IGNORECASE)
        runtime_match = re.search(r"Runtime:\s*(\d+)s", line)
        node_local = "node:local" in line
        sessions.append(
            {
                "pid": int(pid_match.group(1)) if pid_match else None,
                "isBlocked": blocked_match.group(1).lower() == "true" if blocked_match else None,
                "runtimeSeconds": int(runtime_match.group(1)) if runtime_match else None,
                "type": "node:local" if node_local else "shell",
            }
        )
    return {"sessions": sessions, "text": text, "count": len(sessions)}


def _recent_tool_calls_fields(text: str) -> dict[str, Any]:
    summary, _, remainder = text.partition("\n\n")
    calls: list[Any] = []
    if remainder.strip():
        try:
            calls = json.loads(remainder)
        except json.JSONDecodeError:
            calls = []
    return {
        "text": text,
        "summary": summary.strip(),
        "calls": calls if isinstance(calls, list) else [],
        "count": len(calls) if isinstance(calls, list) else 0,
    }


def _normalize_file_preview(structured: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(structured)
    if "filePath" in normalized and "path" not in normalized:
        normalized["path"] = normalized["filePath"]
    if "fileName" in normalized and "name" not in normalized:
        normalized["name"] = normalized["fileName"]
    return normalized


def _build_structured_content(  # noqa: C901, PLR0911, PLR0912
    base_name: str, text: str, *, is_error: bool
) -> dict[str, Any] | None:
    if base_name in {
        "create_directory",
        "move_file",
        "kill_process",
        "force_terminate",
        "stop_search",
        "write_pdf",
        "give_feedback_to_desktop_commander",
        "set_config_value",
    }:
        return _action_result(text, is_error=is_error)

    if base_name in {"start_process", "read_process_output", "interact_with_process"}:
        fields = _process_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "start_search":
        fields = _search_start_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "get_more_search_results":
        fields = _search_more_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "list_searches":
        fields = _search_list_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "list_processes":
        fields = _list_processes_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "list_sessions":
        fields = _list_sessions_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name == "get_recent_tool_calls":
        fields = _recent_tool_calls_fields(text)
        fields["success"] = not is_error
        return fields

    if base_name in {"get_usage_stats", "get_prompts", "get_file_info"}:
        payload: dict[str, Any] = {"text": text, "success": not is_error}
        if base_name == "get_file_info":
            info: dict[str, Any] = {}
            for line in text.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
            payload["info"] = info
        return payload

    if base_name == "read_multiple_files":
        return {"text": text, "success": not is_error, "summary": text.split("\n", 1)[0]}

    return None


def enrich_call_tool_result(tool_name: str, result: types.CallToolResult) -> types.CallToolResult:
    """Attach or normalize structuredContent so it aligns with advertised outputSchema."""
    existing = getattr(result, "structuredContent", None)
    base_name = _base_tool_name(tool_name)
    if base_name in {"read_file", "write_file", "edit_block", "list_directory"}:
        # Keep file/image payloads in content once; only explicit widget metadata is retained.
        preview = _normalize_file_preview(existing) if isinstance(existing, dict) else {}
        preview["success"] = not bool(result.isError)
        result.structuredContent = preview
        return result
    if isinstance(existing, dict):
        if base_name == "get_config":
            result.structuredContent = _normalize_file_preview(existing)
        return result

    text = _text_from_content(getattr(result, "content", None))
    if not text:
        return result

    structured = _build_structured_content(
        base_name,
        text,
        is_error=bool(getattr(result, "isError", False)),
    )
    if structured is not None:
        result.structuredContent = structured
    return result
