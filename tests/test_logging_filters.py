"""Tests for MCP transport logging compatibility filters."""

import logging

import anyio

from mcp_proxy.__main__ import (
    _ExpectedStandaloneSseTeardownFilter,
    _setup_logging,
)


def _record(message: str, exc: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        name="mcp.server.streamable_http",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=(type(exc), exc, None),
    )


def test_expected_standalone_sse_closed_resource_error_is_suppressed() -> None:
    """Expected standalone-SSE teardown noise is filtered."""
    filter_ = _ExpectedStandaloneSseTeardownFilter()

    assert (
        filter_.filter(_record("Error in standalone SSE writer", anyio.ClosedResourceError()))
        is False
    )


def test_unexpected_standalone_sse_error_remains_visible() -> None:
    """Unexpected exceptions on the same code path stay visible."""
    filter_ = _ExpectedStandaloneSseTeardownFilter()

    assert filter_.filter(_record("Error in standalone SSE writer", RuntimeError("boom"))) is True


def test_closed_resource_error_on_other_message_remains_visible() -> None:
    """ClosedResourceError elsewhere is not hidden."""
    filter_ = _ExpectedStandaloneSseTeardownFilter()

    assert (
        filter_.filter(_record("Error handling POST request", anyio.ClosedResourceError())) is True
    )


def test_setup_logging_installs_filter_once() -> None:
    """Repeated logging setup does not stack duplicate filters."""
    transport_logger = logging.getLogger("mcp.server.streamable_http")
    original_filters = list(transport_logger.filters)
    try:
        transport_logger.filters.clear()
        _setup_logging(level="INFO", debug=False)
        _setup_logging(level="INFO", debug=False)

        matching = [
            item
            for item in transport_logger.filters
            if isinstance(item, _ExpectedStandaloneSseTeardownFilter)
        ]
        assert len(matching) == 1
    finally:
        transport_logger.filters[:] = original_filters
