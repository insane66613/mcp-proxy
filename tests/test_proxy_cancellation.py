"""Cancellation must cross the proxy's independent upstream SDK session."""

from http import HTTPStatus

import anyio
import httpx
import pytest
from mcp import types
from mcp.server import Server
from mcp.server.lowlevel.server import request_ctx
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session
from starlette.applications import Starlette

from mcp_proxy import mcp_server, proxy_server
from mcp_proxy.mcp_server import create_single_instance_routes
from mcp_proxy.proxy_server import create_proxy_server


def test_pressure_reclaims_idle_sessions_but_preserves_active_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abandoned clients cannot block new ones or expire a running tool."""
    monkeypatch.setattr(mcp_server, "MAX_HTTP_SESSIONS", 2)
    monkeypatch.setattr(mcp_server, "SESSION_PRESSURE_GRACE_SECONDS", 0.02)

    async def scenario() -> None:
        entered, release = anyio.Event(), anyio.Event()
        server = Server("pressure")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [types.Tool(name="hang", inputSchema={"type": "object"})]

        @server.call_tool()
        async def call_tool(_name: str, _arguments: dict) -> list[types.TextContent]:
            entered.set()
            await release.wait()
            return [types.TextContent(type="text", text="finished")]

        routes, manager = create_single_instance_routes(
            server,
            stateless_instance=False,
            session_idle_timeout=0.15,
        )
        headers = {"Accept": "application/json, text/event-stream"}
        initialize = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "pressure-test", "version": "1"},
            },
        }
        with anyio.fail_after(3):
            async with (
                manager.run(),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=Starlette(routes=routes)),
                    base_url="http://localhost",
                ) as client,
            ):
                first = await client.post("/mcp", headers=headers, json=initialize)
                active_id = first.headers["mcp-session-id"]
                active_headers = {**headers, "mcp-session-id": active_id}
                await client.post(
                    "/mcp",
                    headers=active_headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                )

                async def invoke() -> None:
                    result = await client.post(
                        "/mcp",
                        headers=active_headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 7,
                            "method": "tools/call",
                            "params": {"name": "hang", "arguments": {}},
                        },
                    )
                    assert result.json()["result"]["content"][0]["text"] == "finished"

                async with anyio.create_task_group() as group:
                    group.start_soon(invoke)
                    await entered.wait()
                    stream_scope = anyio.CancelScope()

                    async def stream() -> None:
                        with stream_scope:
                            await client.get("/mcp", headers=active_headers)

                    group.start_soon(stream)
                    await anyio.sleep(0.01)
                    stream_scope.cancel()
                    second = await client.post("/mcp", headers=headers, json=initialize)
                    idle_id = second.headers["mcp-session-id"]
                    await anyio.sleep(0.04)
                    third = await client.post("/mcp", headers=headers, json=initialize)
                    assert third.status_code == HTTPStatus.OK
                    assert idle_id not in manager._server_instances  # noqa: SLF001
                    assert active_id in manager._server_instances  # noqa: SLF001
                    await anyio.sleep(0.2)
                    assert active_id in manager._server_instances  # noqa: SLF001
                    assert not release.is_set()
                    release.set()
                await anyio.sleep(0.2)
                assert active_id not in manager._server_instances  # noqa: SLF001

    anyio.run(scenario)


def test_invalid_headerless_requests_do_not_retain_sessions() -> None:
    """Invalid discovery and initialization traffic consumes no persistent capacity."""

    async def scenario() -> None:
        routes, manager = create_single_instance_routes(Server("invalid"), stateless_instance=False)
        headers = {"Accept": "application/json, text/event-stream"}
        with anyio.fail_after(3):
            async with (
                manager.run(),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=Starlette(routes=routes)),
                    base_url="http://localhost",
                ) as client,
            ):
                response = await client.get("/mcp", headers=headers)
                assert response.status_code == HTTPStatus.BAD_REQUEST
                for body in (b"invalid-json", b'{"method":"ping"}', b'{"method":"initialize"}'):
                    response = await client.post("/mcp", headers=headers, content=body)
                    assert response.status_code == HTTPStatus.BAD_REQUEST
                    assert not manager._server_instances  # noqa: SLF001
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    content=b" " * (4 * 1024 * 1024 + 1),
                )
                assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                assert not manager._server_instances  # noqa: SLF001

    anyio.run(scenario)


def test_passive_sse_connection_does_not_pin_an_idle_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listening for events cannot prevent reclamation of an otherwise idle session."""
    monkeypatch.setattr(mcp_server, "MAX_HTTP_SESSIONS", 1)
    monkeypatch.setattr(mcp_server, "SESSION_PRESSURE_GRACE_SECONDS", 0.01)

    async def scenario() -> None:
        routes, manager = create_single_instance_routes(
            Server("passive-stream"),
            stateless_instance=False,
            session_idle_timeout=0.15,
        )
        headers = {"Accept": "application/json, text/event-stream"}
        initialize = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "stream-test", "version": "1"},
            },
        }
        with anyio.fail_after(3):
            async with (
                manager.run(),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=Starlette(routes=routes)),
                    base_url="http://localhost",
                ) as client,
            ):
                response = await client.post("/mcp", headers=headers, json=initialize)
                session_id = response.headers["mcp-session-id"]

                async def stream() -> None:
                    await client.get(
                        "/mcp",
                        headers={
                            **headers,
                            "mcp-session-id": session_id,
                        },
                    )

                async with anyio.create_task_group() as group:
                    group.start_soon(stream)
                    await anyio.sleep(0.04)
                    assert session_id in manager._server_instances  # noqa: SLF001
                    response = await client.post("/mcp", headers=headers, json=initialize)
                    assert response.status_code == HTTPStatus.OK
                    assert session_id not in manager._server_instances  # noqa: SLF001
                    group.cancel_scope.cancel()

    anyio.run(scenario)


@pytest.mark.parametrize("stall_forward", [False, True])
def test_downstream_cancel_targets_actual_upstream_request_and_releases_handler(
    monkeypatch: pytest.MonkeyPatch,
    stall_forward: bool,
) -> None:
    """Use two real SDK sessions and protocol notifications, without replaying work."""

    async def scenario() -> None:
        entered, cancelled, invocation_done = anyio.Event(), anyio.Event(), anyio.Event()
        forwarding_finished = anyio.Event()
        calls = []
        original = Server("cancellation-fixture")

        @original.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [types.Tool(name="hang", inputSchema={"type": "object"})]

        @original.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            assert name == "hang"
            assert arguments == {}
            calls.append(request_ctx.get().request_id)
            entered.set()
            try:
                await anyio.sleep_forever()
            finally:
                cancelled.set()

        with anyio.fail_after(3):
            async with create_connected_server_and_client_session(original) as upstream:
                proxied = await create_proxy_server(upstream)
                async with create_connected_server_and_client_session(proxied) as downstream:
                    upstream_id = upstream._request_id  # noqa: SLF001
                    downstream_id = downstream._request_id  # noqa: SLF001
                    if stall_forward:
                        monkeypatch.setattr(
                            proxy_server,
                            "CANCELLATION_FORWARD_TIMEOUT_SECONDS",
                            0.03,
                        )

                        async def stalled_notification(
                            _notification: types.ClientNotification,
                        ) -> None:
                            try:
                                await anyio.sleep_forever()
                            finally:
                                forwarding_finished.set()

                        monkeypatch.setattr(upstream, "send_notification", stalled_notification)

                    async def invoke() -> None:
                        with pytest.raises(McpError, match="Request cancelled"):
                            await downstream.call_tool("hang", {})
                        invocation_done.set()

                    async with anyio.create_task_group() as group:
                        group.start_soon(invoke)
                        await entered.wait()
                        await downstream.send_notification(
                            types.ClientNotification(
                                types.CancelledNotification(
                                    params=types.CancelledNotificationParams(
                                        requestId=downstream_id
                                    ),
                                ),
                            ),
                        )
                        if stall_forward:
                            await forwarding_finished.wait()
                            assert not cancelled.is_set()
                        else:
                            await cancelled.wait()
                        await invocation_done.wait()
                    assert calls == [upstream_id]
                    assert upstream_id != downstream_id

    anyio.run(scenario)


def test_concurrent_session_creation_is_bounded_and_delete_frees_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject new sessions at capacity while existing session traffic continues."""
    capacity = 2
    monkeypatch.setattr(mcp_server, "MAX_HTTP_SESSIONS", capacity)

    async def scenario() -> None:
        routes, manager = create_single_instance_routes(
            Server("capacity"),
            stateless_instance=False,
        )
        app = Starlette(routes=routes)
        responses = []
        headers = {"Accept": "application/json, text/event-stream"}
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "capacity-test", "version": "1"},
            },
        }
        with anyio.fail_after(3):
            async with (
                manager.run(),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://localhost",
                ) as client,
            ):

                async def initialize() -> None:
                    responses.append(
                        await client.post(
                            "/mcp",
                            headers=headers,
                            json=initialize_request,
                        )
                    )

                async with anyio.create_task_group() as group:
                    for _ in range(capacity * 2):
                        group.start_soon(initialize)
                assert sum(r.status_code == HTTPStatus.OK for r in responses) == capacity
                rejected = [r for r in responses if r.status_code == HTTPStatus.TOO_MANY_REQUESTS]
                assert len(rejected) == capacity
                assert all(r.headers["retry-after"] == "30" for r in rejected)
                assert len(manager._server_instances) == capacity  # noqa: SLF001
                session_ids = [
                    r.headers["mcp-session-id"] for r in responses if r.status_code == HTTPStatus.OK
                ]
                known_headers = {**headers, "mcp-session-id": session_ids[0]}
                response = await client.post(
                    "/mcp",
                    headers=known_headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                )
                assert response.status_code == HTTPStatus.ACCEPTED
                response = await client.post(
                    "/mcp",
                    headers=known_headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "ping",
                    },
                )
                assert response.status_code == HTTPStatus.OK
                response = await client.post(
                    "/mcp",
                    headers={
                        **headers,
                        "mcp-session-id": "unknown",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "ping",
                    },
                )
                assert response.status_code == HTTPStatus.NOT_FOUND
                for session_id in session_ids:
                    response = await client.delete(
                        "/mcp",
                        headers={
                            **headers,
                            "mcp-session-id": session_id,
                        },
                    )
                    assert response.status_code == HTTPStatus.OK
                assert not manager._server_instances  # noqa: SLF001
                await initialize()
                assert responses[-1].status_code == HTTPStatus.OK

    anyio.run(scenario)


@pytest.mark.parametrize("stateless", [False, True])
def test_http_cancellation_requires_shared_stateful_session(stateless: bool) -> None:
    """Exercise real HTTP route and SDK session manager across separate POSTs."""

    async def scenario() -> None:
        entered, ended, release = anyio.Event(), anyio.Event(), anyio.Event()
        original = Server("http-cancellation-fixture")

        @original.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [types.Tool(name="hang", inputSchema={"type": "object"})]

        @original.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            assert name == "hang"
            assert arguments == {}
            entered.set()
            try:
                await release.wait()
                return [types.TextContent(type="text", text="released")]
            finally:
                ended.set()

        routes, manager = create_single_instance_routes(original, stateless_instance=stateless)
        app = Starlette(routes=routes)
        headers = {"Accept": "application/json, text/event-stream"}
        with anyio.fail_after(3):
            async with (
                manager.run(),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://localhost",
                ) as client,
            ):
                initialize_request = {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "cancellation-test", "version": "1"},
                    },
                }
                response = await client.post("/mcp", headers=headers, json=initialize_request)
                assert response.status_code == HTTPStatus.OK
                session_id = response.headers.get("mcp-session-id")
                assert bool(session_id) is not stateless
                if session_id:
                    headers["mcp-session-id"] = session_id
                headers["mcp-protocol-version"] = response.json()["result"]["protocolVersion"]
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                )
                assert response.status_code == HTTPStatus.ACCEPTED

                async def invoke() -> None:
                    response = await client.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 7,
                            "method": "tools/call",
                            "params": {"name": "hang", "arguments": {}},
                        },
                    )
                    assert response.status_code == HTTPStatus.OK

                async with anyio.create_task_group() as group:
                    group.start_soon(invoke)
                    await entered.wait()
                    response = await client.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "method": "notifications/cancelled",
                            "params": {"requestId": 7},
                        },
                    )
                    assert response.status_code == HTTPStatus.ACCEPTED
                    with anyio.move_on_after(0.1) as deadline:
                        await ended.wait()
                    assert deadline.cancel_called is stateless
                    release.set()
                if session_id:
                    response = await client.delete("/mcp", headers=headers)
                    assert response.status_code == HTTPStatus.OK
                    assert not manager._server_instances  # noqa: SLF001

    anyio.run(scenario)
