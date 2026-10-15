"""Real-child lifecycle regressions for the PR #248 adaptation."""
# ruff: noqa: PLR2004

import asyncio
import contextlib
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
import uvicorn
from mcp.client.stdio import StdioServerParameters

from mcp_proxy.mcp_server import _StdioExitWatch

SOURCE_ROOT = str(Path(__file__).resolve().parents[1] / "src")

CHILD = r"""
import json, os, pathlib, sys, threading, time
marker = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
if mode == "startup":
    os._exit(0)
def watch():
    while not marker.exists():
        time.sleep(0.01)
    os._exit(0)
threading.Thread(target=watch, daemon=True).start()
for line in sys.stdin:
    req = json.loads(line)
    method = req.get("method")
    if method == "initialize":
        result = {"protocolVersion": req["params"]["protocolVersion"],
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "exit-test", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "wait", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        if mode == "active":
            marker.with_suffix(".active").touch()
            time.sleep(60)
        result = {"content": [{"type": "text", "text": json.dumps(req["params"].get("_meta"))}]}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""

DRIVER = r"""
import asyncio, sys
from mcp.client.stdio import StdioServerParameters
from mcp_proxy.mcp_server import MCPServerSettings, run_mcp_server
port, child, marker, mode = sys.argv[1:]
params = StdioServerParameters(command=sys.executable, args=["-u", child, marker, mode])
named = {"alive": StdioServerParameters(command=sys.executable,
    args=["-u", child, marker + ".alive", "idle"]), "exiting": params} if mode == "named" else {}
asyncio.run(run_mcp_server(MCPServerSettings(bind_host="127.0.0.1", port=int(port)),
    None if named else params, named))
"""


@contextlib.asynccontextmanager
async def proxy_process(tmp_path: Path, mode: str) -> Any:  # noqa: ANN401
    """Run only isolated test processes; never use configured production ports."""
    child = tmp_path / "child.py"
    child.write_text(CHILD, encoding="utf-8")
    marker = tmp_path / "exit"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = SOURCE_ROOT
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", DRIVER, str(port), str(child), str(marker), mode,
        env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield process, marker, f"http://127.0.0.1:{port}"
    finally:
        if process.returncode is None:
            process.kill()
        await process.communicate()


async def ready(client: httpx.AsyncClient, url: str) -> None:
    """Wait for a session-free liveness response, with a bounded startup deadline."""
    with anyio.fail_after(10):
        while True:
            try:
                response = await client.get(url + "/healthz")
                if response.status_code == 204:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.05)


HEADERS = {"Accept": "application/json, text/event-stream"}


async def initialize(client: httpx.AsyncClient, url: str) -> dict[str, str]:
    """Open one real stateful MCP session for lifecycle and metadata checks."""
    response = await client.post(url, headers=HEADERS, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "exit-regression", "version": "1"},
        },
    })
    response.raise_for_status()
    headers = {**HEADERS, "mcp-session-id": response.headers["mcp-session-id"]}
    await client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "method": "notifications/initialized",
    })
    return headers


@pytest.mark.parametrize("mode", ["startup", "idle", "active", "openstream", "sse", "named"])
async def test_real_child_loss_exits_proxy(tmp_path: Path, mode: str) -> None:
    """EOF fails the whole proxy, including active/open HTTP and named backends."""
    async with proxy_process(tmp_path, mode) as (process, marker, base), httpx.AsyncClient(
        trust_env=False, timeout=10,
    ) as client:
        pending = None
        writer = None
        stream = None
        if mode != "startup":
            route = "/servers/exiting" if mode == "named" else ""
            await ready(client, base + route)
            headers = await initialize(client, base + route + "/mcp")
            if mode == "active":
                pending = asyncio.create_task(client.post(base + "/mcp", headers=headers, json={
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "wait", "arguments": {}},
                }))
                with anyio.fail_after(5):
                    while not marker.with_suffix(".active").exists():  # noqa: ASYNC110
                        await asyncio.sleep(0.01)
            if mode == "openstream":
                host, port = "127.0.0.1", int(base.rsplit(":", 1)[1])
                _, writer = await asyncio.open_connection(host, port)
                writer.write(
                    b"POST /mcp HTTP/1.1\r\nHost: localhost\r\nContent-Length: 1000\r\n\r\n{",
                )
                await writer.drain()
                await asyncio.sleep(0.1)
            if mode == "sse":
                stream = client.stream("GET", base + "/sse")
                response = await stream.__aenter__()
                assert response.status_code == 200
            started = time.monotonic()
            marker.touch()
        else:
            started = time.monotonic()
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=12)
        elapsed = time.monotonic() - started
        assert process.returncode != 0, stderr.decode(errors="replace")
        assert elapsed < 7  # Five-second HTTP grace plus process/stdio cleanup overhead.
        if mode != "startup":
            assert b"exited, shutting down" in stderr
        if pending:
            await asyncio.gather(pending, return_exceptions=True)
        if writer:
            writer.close()
            await writer.wait_closed()
        if stream:
            await stream.__aexit__(None, None, None)


async def test_request_meta_survives_real_proxy(tmp_path: Path) -> None:
    """The existing metadata forwarding carries request identity and retry attempt."""
    async with proxy_process(tmp_path, "idle") as (_, _, base), httpx.AsyncClient(
        trust_env=False, timeout=5,
    ) as client:
        await ready(client, base)
        headers = await initialize(client, base + "/mcp")
        for attempt in (0, 1):
            meta = {"sanitycloud_request_id": "a" * 32, "sanitycloud_attempt": attempt}
            response = await client.post(base + "/mcp", headers=headers, json={
                "jsonrpc": "2.0", "id": 2 + attempt, "method": "tools/call",
                "params": {"name": "wait", "arguments": {}, "_meta": meta},
            })
            assert json.loads(response.json()["result"]["content"][0]["text"]) == meta


async def test_normal_shutdown_and_cancellation_do_not_report_child_loss() -> None:
    """Intentional stop/cancellation leaves the supervisor failure signal unset."""
    watch = _StdioExitWatch()
    server = uvicorn.Server(uvicorn.Config("unused:app"))
    server.should_exit = True
    watch.attach(server)
    watch._on_exit("normal")  # noqa: SLF001
    watch.exit_if_exited()
    assert not watch.exited
    assert server.should_exit
    params = StdioServerParameters(
        command=sys.executable, args=["-c", "import time; time.sleep(60)"],
    )
    task = asyncio.create_task(_cancel_watch(watch, params))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not watch.exited


async def _cancel_watch(watch: _StdioExitWatch, params: StdioServerParameters) -> None:
    async with watch.client(params, "cancelled"):
        await asyncio.Event().wait()
