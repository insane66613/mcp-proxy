"""Regression tests for privacy-preserving opt-in MCP HTTP lifecycle logs."""
# ruff: noqa: PLR2004

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server import Server
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

from mcp_proxy.http_lifecycle import instrument_http_endpoint
from mcp_proxy.mcp_server import _ASGIEndpointAdapter, create_single_instance_routes

if TYPE_CHECKING:
    from starlette.types import Message, Receive, Scope, Send


async def _simple_endpoint(scope: Scope, receive: Receive, send: Send) -> None:
    await receive()
    await Response("ok")(scope, receive, send)


async def test_default_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary deployments are not affected by diagnostic code."""
    monkeypatch.delenv("MCP_HTTP_LIFECYCLE_LOGGING", raising=False)
    assert instrument_http_endpoint(_simple_endpoint) is _simple_endpoint


async def test_opt_in_records_method_without_tokens_or_arguments(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Correlation is possible without persisting MCP payloads or session secrets."""
    wrapper = instrument_http_endpoint(_simple_endpoint, enabled=True)
    app = Starlette(routes=[Route("/mcp", _ASGIEndpointAdapter(wrapper), methods=["POST"])])
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            headers={
                "mcp-session-id": "sensitive-session-token",
                "user-agent": "private-agent",
                "CF-Ray": "8f212bee12a2fe90-ORD",
            },
            json={
                "method": "tools/call",
                "params": {"name": "read_file", "arguments": {"path": "sensitive-secret"}},
            },
        )
    assert response.status_code == 200
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "edge_ray=8f212bee12a2fe90-ORD" in message
    assert "mcp_method=tools/call" in message
    assert "tool=read_file" in message
    assert "outcome=http_response_complete" in message
    assert "status=200" in message
    assert "sensitive-session-token" not in message
    assert "sensitive-secret" not in message
    assert "private-agent" not in message


async def test_status_error_is_not_reported_as_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP failures remain distinguishable from Python exceptions."""

    async def rejected(scope: Scope, receive: Receive, send: Send) -> None:
        await Response("Too Many Requests", status_code=429)(scope, receive, send)

    app = Starlette(
        routes=[
            Route(
                "/mcp",
                _ASGIEndpointAdapter(instrument_http_endpoint(rejected, enabled=True)),
                methods=["GET"],
            )
        ]
    )
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/mcp")).status_code == 429
    assert "status=429" in caplog.records[0].getMessage()
    assert "outcome=http_response_complete" in caplog.records[0].getMessage()


async def test_task_cancellation_does_not_get_labeled_client_disconnect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An ASGI cancellation does not itself establish what caused it."""

    async def cancelled(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise asyncio.CancelledError

    wrapper = instrument_http_endpoint(cancelled, enabled=True)
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    scope: Scope = {"type": "http", "method": "GET", "headers": [], "client": ("127.0.0.1", 1234)}

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message: Message) -> None:
        return None

    with pytest.raises(asyncio.CancelledError):
        await wrapper(scope, receive, send)
    message = caplog.records[0].getMessage()
    assert "outcome=task_cancelled_origin_unknown" in message
    assert "disconnect_observed=False" in message


async def test_explicit_disconnect_is_observed_without_claiming_tool_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the actual ASGI http.disconnect message establishes observation."""

    async def saw_disconnect(_scope: Scope, receive: Receive, send: Send) -> None:
        await receive()
        await Response("ok")(_scope, receive, send)

    wrapper = instrument_http_endpoint(saw_disconnect, enabled=True)
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    scope: Scope = {"type": "http", "method": "GET", "headers": [], "client": None}

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(_message: Message) -> None:
        return None

    await wrapper(scope, receive, send)
    message = caplog.records[0].getMessage()
    assert "outcome=client_disconnect_observed" in message
    assert "status=200" in message


async def test_mcp_route_uses_instrumentation_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both URI spellings share lifecycle instrumentation while preserving responses."""
    monkeypatch.setenv("MCP_HTTP_LIFECYCLE_LOGGING", "1")
    routes, _manager = create_single_instance_routes(
        Server("http-lifecycle-test"),
        stateless_instance=False,
    )
    app = Starlette(routes=routes)
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for uri in ("/mcp", "/mcp/"):
            response = await client.get(uri, headers={"Accept": "application/json"})
            assert response.status_code == 406
    records = [
        record.getMessage()
        for record in caplog.records
        if "mcp_http_lifecycle" in record.getMessage()
    ]
    assert len(records) == 2
    assert all("status=406" in record for record in records)


async def test_initialize_response_correlates_with_followup_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An initialize response session ID can be linked to later HTTP calls."""

    async def initialize(scope: Scope, receive: Receive, send: Send) -> None:
        await receive()
        await Response("ok", headers={"mcp-session-id": "opaque-session-value"})(
            scope,
            receive,
            send,
        )

    endpoint = _ASGIEndpointAdapter(instrument_http_endpoint(initialize, enabled=True))
    app = Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])])
    caplog.set_level(logging.INFO, logger="mcp_proxy.http_lifecycle")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/mcp", json={"method": "initialize"})
        await client.post(
            "/mcp",
            headers={"mcp-session-id": "opaque-session-value"},
            json={"method": "tools/list"},
        )
    messages = [r.getMessage() for r in caplog.records if "mcp_http_lifecycle" in r.getMessage()]
    tags = [message.split("session_tag=")[1].split()[0] for message in messages]
    assert len(tags) == 2
    assert tags[0] == tags[1]
    assert tags[0] != "-"
    assert all("opaque-session-value" not in message for message in messages)
