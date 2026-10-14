"""Opt-in HTTP lifecycle tracing without recording MCP arguments or session tokens.

These records classify ASGI observations, not Cloudflare stream-cancellation causes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import anyio
from starlette.types import Message, Receive, Scope, Send

LOGGER = logging.getLogger(__name__)
_SALT = secrets.token_bytes(32)
_MAX_CAPTURE_BYTES = 16 * 1024
ASGIEndpoint = Callable[[Scope, Receive, Send], Awaitable[None]]


@dataclass
class _TraceState:
    """Per-request state, discarded after logging the bounded summary."""

    body: bytearray | None = field(default_factory=bytearray)
    disconnected: bool = False
    response_complete: bool = False
    response_status: int | None = None
    response_session_tag: str = "-"
    exception_type: str = "-"
    outcome: str = "response_incomplete"


def _tag(value: str | None) -> str:
    """Correlate within one process without emitting raw identifiers."""
    if not value:
        return "-"
    return hmac.new(_SALT, value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _identifier(value: object) -> str:
    """Limit logged MCP method/tool labels to a safe, short alphabet."""
    if not isinstance(value, str):
        return "-"
    return (
        "".join(
            character
            if character.isascii() and (character.isalnum() or character in "_/-.:")
            else "_"
            for character in value[:80]
        )
        or "-"
    )


def _request_labels(body: bytes) -> tuple[str, str]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return "-", "-"
    if not isinstance(payload, dict):
        return "-", "-"
    method = _identifier(payload.get("method"))
    params = payload.get("params")
    tool = (
        _identifier(params.get("name"))
        if method == "tools/call" and isinstance(params, dict)
        else "-"
    )
    return method, tool


def instrument_http_endpoint(  # noqa: C901, PLR0915
    endpoint: ASGIEndpoint, *, enabled: bool | None = None
) -> ASGIEndpoint:
    """Observe HTTP lifecycle without modifying requests or responses.

    Enable with MCP_HTTP_LIFECYCLE_LOGGING=1 before starting the proxy.
    Task cancellations do not prove client disconnection. Unconsumed ASGI
    disconnects are invisible; HTTP 200 does not prove a tool succeeded.
    """
    if enabled is None:
        enabled = os.getenv("MCP_HTTP_LIFECYCLE_LOGGING", "").lower() in {
            "1",
            "true",
            "yes",
        }
    if not enabled:
        return endpoint

    async def observe(scope: Scope, receive: Receive, send: Send) -> None:  # noqa: C901
        if scope.get("type") != "http":
            await endpoint(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        session = headers.get(b"mcp-session-id", b"").decode("utf-8", errors="replace")
        user_agent = headers.get(b"user-agent", b"").decode("utf-8", errors="replace")
        peer = str(scope["client"][0]) if scope.get("client") else ""
        request_id = secrets.token_hex(8)
        started = anyio.current_time()
        state = _TraceState()

        async def observe_receive() -> Message:
            message = await receive()
            if message["type"] == "http.disconnect":
                state.disconnected = True
            elif message["type"] == "http.request":
                chunk = message.get("body", b"")
                if state.body is not None:
                    available = max(0, _MAX_CAPTURE_BYTES - len(state.body))
                    if len(chunk) > available:
                        state.body = None
                    else:
                        state.body.extend(chunk)
            return message

        async def observe_send(message: Message) -> None:
            await send(message)
            if message["type"] == "http.response.start":
                state.response_status = int(message["status"])
                if not session:
                    response_headers = {
                        key.lower(): value for key, value in message.get("headers", [])
                    }
                    raw_session = response_headers.get(b"mcp-session-id", b"")
                    state.response_session_tag = _tag(raw_session.decode("utf-8", errors="replace"))
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                state.response_complete = True

        try:
            await endpoint(scope, observe_receive, observe_send)
            if state.disconnected:
                state.outcome = "client_disconnect_observed"
            elif state.response_complete:
                state.outcome = "http_response_complete"
        except BaseException as error:
            state.exception_type = type(error).__name__
            if isinstance(error, anyio.get_cancelled_exc_class()):
                state.outcome = "task_cancelled_origin_unknown"
            else:
                state.outcome = "application_exception"
            raise
        finally:
            method, tool = _request_labels(state.body) if state.body is not None else ("-", "-")
            LOGGER.info(
                "mcp_http_lifecycle request_id=%s edge_ray=%s verb=%s session_tag=%s peer_tag=%s "
                "agent_tag=%s mcp_method=%s tool=%s status=%s outcome=%s "
                "response_complete=%s disconnect_observed=%s body_truncated=%s "
                "elapsed_ms=%.1f exception_type=%s",
                request_id,
                _identifier(headers.get(b"cf-ray", b"").decode("ascii", errors="replace")[:32]),
                _identifier(scope.get("method")),
                _tag(session) if session else state.response_session_tag,
                _tag(peer),
                _tag(user_agent),
                method,
                tool,
                state.response_status,
                state.outcome,
                state.response_complete,
                state.disconnected,
                state.body is None,
                (anyio.current_time() - started) * 1000,
                state.exception_type,
            )

    return observe
