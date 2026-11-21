"""Bounded reverse-client EOF shutdown without sacrificing transport disposal."""

# ruff: noqa: SLF001

import asyncio

import anyio
import pytest

import mcp_proxy.streamablehttp_client as reverse_client


@pytest.mark.asyncio
async def test_eof_cancels_blocked_application_but_allows_outer_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-start EOF cancels stuck request work before upstream cleanup."""
    monkeypatch.setattr(reverse_client, "_EOF_DRAIN_GRACE_SECONDS", 0.03)
    eof = anyio.Event()
    started = anyio.Event()
    exited = anyio.Event()
    disposed = anyio.Event()

    async def stuck() -> None:
        started.set()
        try:
            await anyio.sleep_forever()
        finally:
            exited.set()

    async def run_with_disposal() -> None:
        try:
            await reverse_client._run_with_bounded_eof(stuck, eof)
        finally:
            # This runs outside the application's cancelled scope.
            with anyio.fail_after(1):
                await anyio.lowlevel.checkpoint()
                disposed.set()

    with anyio.fail_after(2):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(run_with_disposal)
            await started.wait()
            eof.set()
    assert exited.is_set()
    assert disposed.is_set()


@pytest.mark.asyncio
async def test_eof_drain_finishes_without_forcing_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cooperative in-flight tool gets its regular EOF shutdown."""
    monkeypatch.setattr(reverse_client, "_EOF_DRAIN_GRACE_SECONDS", 0.05)
    eof = anyio.Event()
    started = anyio.Event()
    finish = anyio.Event()
    completed = anyio.Event()

    async def run() -> None:
        started.set()
        await finish.wait()
        completed.set()

    with anyio.fail_after(2):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(reverse_client._run_with_bounded_eof, run, eof)
            await started.wait()
            eof.set()
            finish.set()
    assert completed.is_set()


@pytest.mark.asyncio
async def test_no_eof_does_not_limit_long_running_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal requests remain unlimited by the shutdown-only deadline."""
    monkeypatch.setattr(reverse_client, "_EOF_DRAIN_GRACE_SECONDS", 0.02)
    eof = anyio.Event()
    started = anyio.Event()
    finish = anyio.Event()

    async def run() -> None:
        started.set()
        await finish.wait()

    with anyio.fail_after(2):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(reverse_client._run_with_bounded_eof, run, eof)
            await started.wait()
            await anyio.sleep(0.08)
            assert not finish.is_set()
            finish.set()


@pytest.mark.asyncio
async def test_eof_before_application_consumes_stream_is_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The race after readiness still exposes memory-stream EOF to the app."""
    monkeypatch.setattr(reverse_client, "_EOF_DRAIN_GRACE_SECONDS", 0.05)
    eof = anyio.Event()
    eof.set()
    sender, receiver = anyio.create_memory_object_stream[bytes](1)
    await sender.aclose()
    observed = anyio.Event()

    async def run() -> None:
        await anyio.lowlevel.checkpoint()
        with pytest.raises(anyio.EndOfStream):
            await receiver.receive()
        observed.set()

    with anyio.fail_after(2):
        await reverse_client._run_with_bounded_eof(run, eof)
    assert observed.is_set()
    await receiver.aclose()


@pytest.mark.asyncio
async def test_non_cancelled_application_error_is_preserved() -> None:
    """A real run failure must not be mistaken for an EOF timeout."""
    eof = anyio.Event()
    original = ValueError("synthetic run failure")

    async def fail() -> None:
        raise original

    with pytest.raises(ValueError, match="synthetic run failure") as failure:
        await reverse_client._run_with_bounded_eof(fail, eof)
    assert failure.value is original


@pytest.mark.asyncio
async def test_external_cancellation_is_not_swallowed() -> None:
    """Ctrl+C-driven cancellation remains externally observable."""
    eof = anyio.Event()
    started = anyio.Event()
    propagated = anyio.Event()

    async def run() -> None:
        started.set()
        await anyio.sleep_forever()

    async def worker() -> None:
        try:
            await reverse_client._run_with_bounded_eof(run, eof)
        except asyncio.CancelledError:
            propagated.set()
            raise

    with anyio.fail_after(2):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(worker)
            await started.wait()
            tasks.cancel_scope.cancel()
    assert propagated.is_set()
