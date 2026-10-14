"""Create a local SSE server that proxies requests to a stdio MCP server."""

import contextlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Final, Literal

import anyio
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server import Server as MCPServerSDK  # Renamed to avoid conflict
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.types import Message, Receive, Scope, Send

from .http_lifecycle import instrument_http_endpoint
from .proxy_server import create_proxy_server

logger = logging.getLogger(__name__)

DEFAULT_EXPOSE_HEADERS: Final[tuple[str, ...]] = ("mcp-session-id",)
MAX_HTTP_SESSIONS: Final[int] = 128
SESSION_PRESSURE_GRACE_SECONDS: Final[float] = 30.0


def _default_expose_headers() -> list[str]:
    return list(DEFAULT_EXPOSE_HEADERS)


@dataclass
class MCPServerSettings:
    """Settings for the MCP server."""

    bind_host: str
    port: int
    stateless: bool = False
    session_idle_timeout: float = 1800.0
    allow_origins: list[str] | None = None
    expose_headers: list[str] = field(default_factory=_default_expose_headers)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


# To store last activity for multiple servers if needed, though status endpoint is global for now.
_global_status: dict[str, Any] = {
    "api_last_activity": datetime.now(timezone.utc).isoformat(),
    "active_sse_connections": 0,
    "server_instances": {},  # Could be used to store per-instance status later
}


def _update_global_activity() -> None:
    _global_status["api_last_activity"] = datetime.now(timezone.utc).isoformat()


class _ASGIEndpointAdapter:
    """Wrap a coroutine function into an ASGI application."""

    def __init__(self, endpoint: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self._endpoint = endpoint

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._endpoint(scope, receive, send)


HTTP_METHODS = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"]


async def _handle_status(_: Request) -> Response:
    """Global service usage monitoring endpoint."""
    return JSONResponse(_global_status)


async def _handle_healthz(_: Request) -> Response:
    """Transport-only liveness probe that never allocates an MCP session."""
    return Response(status_code=204)


def create_single_instance_routes(  # noqa: C901, PLR0915
    mcp_server_instance: MCPServerSDK[object],
    *,
    stateless_instance: bool,
    session_idle_timeout: float = 1800.0,
) -> tuple[list[BaseRoute], StreamableHTTPSessionManager]:  # Return the manager itself
    """Create Starlette routes and the HTTP session manager for a single MCP server instance."""
    logger.debug(
        "Creating routes for a single MCP server instance (stateless: %s)",
        stateless_instance,
    )

    sse_transport = SseServerTransport("/messages/")
    http_session_manager = StreamableHTTPSessionManager(
        app=mcp_server_instance,
        event_store=None,
        json_response=True,
        stateless=stateless_instance,
        # SDK inactivity counts HTTP arrivals and can cancel long active calls;
        # retain its recommended 30-minute bound rather than a short probe timeout.
        session_idle_timeout=None if stateless_instance else session_idle_timeout,
    )
    session_admission_lock = anyio.Lock()
    active_requests: dict[str, int] = {}
    last_completed: dict[str, float] = {}

    async def retire_session(session_id: str) -> bool:
        transport = http_session_manager._server_instances.get(session_id)  # noqa: SLF001
        if transport is None:
            return True
        # Remove admission before yielding so a new request cannot attach mid-retirement.
        http_session_manager._server_instances.pop(session_id, None)  # noqa: SLF001
        with anyio.move_on_after(5, shield=True):
            await transport.terminate()
        if not transport.is_terminated:
            http_session_manager._server_instances.setdefault(session_id, transport)  # noqa: SLF001
            return False
        if http_session_manager._server_instances.get(session_id) is transport:  # noqa: SLF001
            http_session_manager._server_instances.pop(session_id, None)  # noqa: SLF001
        active_requests.pop(session_id, None)
        last_completed.pop(session_id, None)
        return True

    async def handle_sse_instance(request: Request) -> Response:
        try:
            async with sse_transport.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
            ) as (read_stream, write_stream):
                _update_global_activity()
                _global_status["active_sse_connections"] += 1
                try:
                    await mcp_server_instance.run(
                        read_stream,
                        write_stream,
                        mcp_server_instance.create_initialization_options(),
                        stateless=stateless_instance,
                    )
                finally:
                    _global_status["active_sse_connections"] -= 1
        except Exception:  # noqa: BLE001
            # SSE response already started — cannot send HTTP error response.
            # Log and let the connection close gracefully.
            logger.warning(
                "SSE connection for '%s' terminated with error (upstream disconnect?)",
                mcp_server_instance.name,
                exc_info=True,
            )
        return Response()

    async def handle_streamable_http_instance(  # noqa: C901, PLR0912, PLR0915
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") == "http":
            request = Request(scope)
            if request.method == "HEAD":
                await Response(status_code=405, headers={"Allow": "GET, POST, DELETE"})(
                    scope,
                    receive,
                    send,
                )
                return
            if (
                request.method == "GET"
                and "mcp-session-id" not in request.headers
                and not any(
                    media_type.strip().startswith("text/event-stream")
                    for media_type in request.headers.get("accept", "").split(",")
                )
            ):
                await Response(
                    "Not Acceptable: Client must accept text/event-stream",
                    status_code=406,
                )(
                    scope,
                    receive,
                    send,
                )
                return
        _update_global_activity()
        updated_scope = scope
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path and path.rstrip("/") == "/mcp" and not path.endswith("/"):
                updated_scope = dict(scope)
                normalized_path = path + "/"
                logger.debug(
                    "Normalized request path from '%s' to '%s' without redirect",
                    path,
                    normalized_path,
                )
                updated_scope["path"] = normalized_path

                raw_path = scope.get("raw_path")
                if raw_path:
                    if b"?" in raw_path:
                        path_part, query_part = raw_path.split(b"?", 1)
                        updated_scope["raw_path"] = path_part.rstrip(b"/") + b"/?" + query_part
                    else:
                        updated_scope["raw_path"] = raw_path.rstrip(b"/") + b"/"

        session_id = Request(scope).headers.get("mcp-session-id")
        if not stateless_instance and session_id is None:
            request = Request(scope, receive)
            if request.method != "POST":
                await Response("MCP session ID required", status_code=400)(
                    updated_scope,
                    receive,
                    send,
                )
                return
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4 * 1024 * 1024:
                    await Response("Initialization body too large", status_code=413)(
                        updated_scope,
                        receive,
                        send,
                    )
                    return
                body.extend(chunk)
            try:
                message = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                message = None
            if not isinstance(message, dict) or message.get("method") != "initialize":
                await Response("Initialize a session first", status_code=400)(
                    updated_scope,
                    receive,
                    send,
                )
                return

            body_sent = False

            async def replay_receive() -> Message:
                nonlocal body_sent
                if body_sent:
                    return await receive()
                body_sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            # Serialize allocation checks so simultaneous initializations respect the bound.
            async with session_admission_lock:
                instances = http_session_manager._server_instances  # noqa: SLF001
                for stale_id in last_completed.keys() - instances.keys():
                    last_completed.pop(stale_id, None)
                if len(http_session_manager._server_instances) >= MAX_HTTP_SESSIONS:  # noqa: SLF001
                    candidates = [
                        key
                        for key in instances
                        if not active_requests.get(key, 0)
                        and anyio.current_time() - last_completed.get(key, anyio.current_time())
                        >= SESSION_PRESSURE_GRACE_SECONDS
                    ]
                    if candidates:
                        oldest = min(candidates, key=lambda key: last_completed[key])
                        if await retire_session(oldest):
                            logger.info("Reclaimed idle MCP session at capacity")
                if len(instances) >= MAX_HTTP_SESSIONS:
                    logger.warning(
                        "MCP session capacity reached: sessions=%s active=%s",
                        len(instances),
                        sum(bool(active_requests.get(key, 0)) for key in instances),
                    )
                    await Response(
                        "MCP session capacity reached",
                        status_code=429,
                        headers={"Retry-After": "30"},
                    )(updated_scope, receive, send)
                    return
                previous_ids = set(instances)
                response_status = 500

                async def capture_send(message: Message) -> None:
                    nonlocal response_status
                    if message["type"] == "http.response.start":
                        response_status = message["status"]
                    await send(message)

                try:
                    await http_session_manager.handle_request(
                        updated_scope,
                        replay_receive,
                        capture_send,
                    )
                finally:
                    for new_id in set(instances) - previous_ids:
                        last_completed[new_id] = anyio.current_time()
                        if response_status >= HTTPStatus.BAD_REQUEST:
                            await retire_session(new_id)
        else:
            transport = (
                http_session_manager._server_instances.get(session_id)  # noqa: SLF001
                if session_id is not None
                else None
            )
            active = Request(scope).method != "GET"
            if active and transport is not None and session_id is not None:
                active_requests[session_id] = active_requests.get(session_id, 0) + 1
                if transport.idle_scope is not None:
                    transport.idle_scope.deadline = float("inf")
            elif (
                transport is not None
                and session_id is not None
                and transport.idle_scope is not None
                and session_idle_timeout is not None
                and not active_requests.get(session_id, 0)
            ):
                # A passive event stream refreshes arrival time but cannot pin a session.
                transport.idle_scope.deadline = anyio.current_time() + session_idle_timeout
            try:
                if transport is not None:
                    # SDK resets the deadline on arrival, even for a long active call.
                    await transport.handle_request(updated_scope, receive, send)
                else:
                    await http_session_manager.handle_request(updated_scope, receive, send)
            finally:
                if active and transport is not None and session_id is not None:
                    remaining = active_requests[session_id] - 1
                    if remaining:
                        active_requests[session_id] = remaining
                    else:
                        active_requests.pop(session_id, None)
                        last_completed[session_id] = anyio.current_time()
                        if transport.idle_scope is not None and session_idle_timeout is not None:
                            transport.idle_scope.deadline = (
                                anyio.current_time() + session_idle_timeout
                            )
                # SDK v1 retains explicitly terminated transports after DELETE.
                if (
                    transport is not None
                    and transport.is_terminated
                    and session_id is not None
                    and http_session_manager._server_instances.get(session_id) is transport  # noqa: SLF001
                ):
                    http_session_manager._server_instances.pop(session_id, None)  # noqa: SLF001
                    last_completed.pop(session_id, None)

    http_endpoint = _ASGIEndpointAdapter(instrument_http_endpoint(handle_streamable_http_instance))
    routes = [
        Route("/healthz", endpoint=_handle_healthz, methods=["GET", "HEAD"]),
        Route(
            "/mcp",
            endpoint=http_endpoint,
            methods=HTTP_METHODS,
            include_in_schema=False,
        ),
        Route(
            "/mcp/",
            endpoint=http_endpoint,
            methods=HTTP_METHODS,
            include_in_schema=False,
        ),
        Route("/sse", endpoint=handle_sse_instance),
        Mount("/messages/", app=sse_transport.handle_post_message),
    ]
    return routes, http_session_manager


async def run_mcp_server(
    mcp_settings: MCPServerSettings,
    default_server_params: StdioServerParameters | None = None,
    named_server_params: dict[str, StdioServerParameters] | None = None,
) -> None:
    """Run stdio client(s) and expose an MCP server with multiple possible backends."""
    if named_server_params is None:
        named_server_params = {}

    all_routes: list[BaseRoute] = [
        Route("/status", endpoint=_handle_status),  # Global status endpoint
    ]
    # Use AsyncExitStack to manage lifecycles of multiple components
    async with contextlib.AsyncExitStack() as stack:
        # Manage lifespans of all StreamableHTTPSessionManagers
        @contextlib.asynccontextmanager
        async def combined_lifespan(_app: Starlette) -> AsyncIterator[None]:
            logger.info("Main application lifespan starting...")
            # All http_session_managers' .run() are already entered into the stack
            yield
            logger.info("Main application lifespan shutting down...")

        # Setup default server if configured
        if default_server_params:
            logger.info(
                "Setting up default server: %s %s",
                default_server_params.command,
                " ".join(default_server_params.args),
            )
            stdio_streams = await stack.enter_async_context(stdio_client(default_server_params))
            session = await stack.enter_async_context(ClientSession(*stdio_streams))
            proxy = await create_proxy_server(session)

            instance_routes, http_manager = create_single_instance_routes(
                proxy,
                stateless_instance=mcp_settings.stateless,
                session_idle_timeout=mcp_settings.session_idle_timeout,
            )
            await stack.enter_async_context(http_manager.run())  # Manage lifespan by calling run()
            all_routes.extend(instance_routes)
            _global_status["server_instances"]["default"] = "configured"

        # Setup named servers
        for name, params in named_server_params.items():
            logger.info(
                "Setting up named server '%s': %s %s",
                name,
                params.command,
                " ".join(params.args),
            )
            stdio_streams_named = await stack.enter_async_context(stdio_client(params))
            session_named = await stack.enter_async_context(ClientSession(*stdio_streams_named))
            proxy_named = await create_proxy_server(session_named)

            instance_routes_named, http_manager_named = create_single_instance_routes(
                proxy_named,
                stateless_instance=mcp_settings.stateless,
                session_idle_timeout=mcp_settings.session_idle_timeout,
            )
            await stack.enter_async_context(
                http_manager_named.run(),
            )  # Manage lifespan by calling run()

            # Mount these routes under /servers/<name>/
            server_mount = Mount(f"/servers/{name}", routes=instance_routes_named)
            all_routes.append(server_mount)
            _global_status["server_instances"][name] = "configured"

        if not default_server_params and not named_server_params:
            logger.error("No servers configured to run.")
            return

        middleware: list[Middleware] = []
        if mcp_settings.allow_origins:
            middleware.append(
                Middleware(
                    CORSMiddleware,
                    allow_origins=mcp_settings.allow_origins,
                    allow_methods=["*"],
                    allow_headers=["*"],
                    expose_headers=mcp_settings.expose_headers,
                ),
            )

        starlette_app = Starlette(
            debug=(mcp_settings.log_level == "DEBUG"),
            routes=all_routes,
            middleware=middleware,
            lifespan=combined_lifespan,
        )

        starlette_app.router.redirect_slashes = False

        config = uvicorn.Config(
            starlette_app,
            host=mcp_settings.bind_host,
            port=mcp_settings.port,
            log_level=mcp_settings.log_level.lower(),
        )
        http_server = uvicorn.Server(config)

        # Print out the SSE URLs for all configured servers
        base_url = f"http://{mcp_settings.bind_host}:{mcp_settings.port}"
        sse_urls = []

        # Add default server if configured
        if default_server_params:
            sse_urls.append(f"{base_url}/sse")

        # Add named servers
        sse_urls.extend([f"{base_url}/servers/{name}/sse" for name in named_server_params])

        # Display the SSE URLs prominently
        if sse_urls:
            # Using print directly for user visibility, with noqa to ignore linter warnings
            logger.info("Serving MCP Servers via SSE:")
            for url in sse_urls:
                logger.info("  - %s", url)

        logger.debug(
            "Serving incoming MCP requests on %s:%s",
            mcp_settings.bind_host,
            mcp_settings.port,
        )
        await http_server.serve()
