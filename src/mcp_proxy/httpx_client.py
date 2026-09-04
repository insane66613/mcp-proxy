"""HTTP client factory with privacy-preserving connector observability."""

from __future__ import annotations

import ipaddress
import logging
import time
from collections import deque
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_REQUEST_WINDOW_SECONDS = 60.0
_request_timestamps: deque[float] = deque()
_request_rate_lock = Lock()


def _destination_class(request: httpx.Request) -> str:
    """Classify a destination without emitting host, port, path, or query data."""
    host = (request.url.host or "").strip().lower().rstrip(".")
    if host == "localhost":
        return "loopback"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "public-network"
    if address.is_loopback:
        return "loopback"
    if address.is_private or address.is_link_local:
        return "private-network"
    return "public-network"


def _record_request_rate() -> int:
    """Return the per-process request count in the trailing 60-second window."""
    now = time.monotonic()
    cutoff = now - _REQUEST_WINDOW_SECONDS
    with _request_rate_lock:
        while _request_timestamps and _request_timestamps[0] <= cutoff:
            _request_timestamps.popleft()
        _request_timestamps.append(now)
        return len(_request_timestamps)


def _sanitize_retry_after(value: str | None) -> str:
    if not value:
        return "-"
    normalized = " ".join(value.split())[:128]
    return normalized or "-"


def custom_httpx_client(  # noqa: C901
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
    verify_ssl: bool | str | None = None,
) -> httpx.AsyncClient:
    """Create a standardized HTTP client with bounded connector metrics.

    Request observability intentionally excludes URLs, headers, cookies, bodies,
    and conversation content; only coarse destination and rate metadata is logged.

    Args:
        headers: Optional headers to include with all requests.
        timeout: Request timeout as httpx.Timeout object.
        auth: Optional authentication handler.
        verify_ssl: Control SSL verification. Use False to disable
            or a path to a certificate bundle.

    Returns:
        Configured httpx.AsyncClient instance with MCP defaults and logging.
    """
    # Set MCP defaults (copied from original implementation)
    kwargs: dict[str, Any] = {
        "follow_redirects": True,
    }

    # Handle timeout
    if timeout is None:
        kwargs["timeout"] = httpx.Timeout(30.0)
    else:
        kwargs["timeout"] = timeout

    # Handle headers
    if headers is not None:
        kwargs["headers"] = headers

    # Handle authentication
    if auth is not None:
        kwargs["auth"] = auth

    if verify_ssl is not None:
        normalized_verify: bool | str
        if isinstance(verify_ssl, str):
            lowered = verify_ssl.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                normalized_verify = True
            elif lowered in {"0", "false", "no", "off"}:
                normalized_verify = False
            else:
                normalized_verify = verify_ssl
        else:
            normalized_verify = verify_ssl

        kwargs["verify"] = normalized_verify

        if isinstance(normalized_verify, bool):
            logger.debug(
                "Configured httpx.AsyncClient verify=%s (SSL verification %s).",
                normalized_verify,
                "enabled" if normalized_verify else "disabled",
            )
        else:
            logger.debug(
                "Configured httpx.AsyncClient using certificate bundle at %s.",
                normalized_verify,
            )

    # Record only the bounded metadata needed to attribute request-rate incidents.
    async def log_request(request: httpx.Request) -> None:
        request.extensions["sanitycloud_destination_class"] = _destination_class(request)
        request.extensions["sanitycloud_requests_per_minute"] = _record_request_rate()

    async def log_response(response: httpx.Response) -> None:
        request = response.request
        destination_class = str(
            request.extensions.get("sanitycloud_destination_class") or _destination_class(request)
        )
        requests_per_minute = int(
            request.extensions.get("sanitycloud_requests_per_minute") or 0
        )
        retry_after = _sanitize_retry_after(response.headers.get("Retry-After"))
        logger.info(
            "destination_class=%s request_type=%s status=%d retry_after=%s "
            "requests_per_minute=%d",
            destination_class,
            request.method,
            response.status_code,
            retry_after,
            requests_per_minute,
        )

    # Add event hooks
    kwargs["event_hooks"] = {
        "request": [log_request],
        "response": [log_response],
    }

    return httpx.AsyncClient(**kwargs)
