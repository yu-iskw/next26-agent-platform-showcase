"""Correlation ID propagation across service boundaries.

Provides a consistent correlation_id and traceparent for all requests
across the agent runtime, Cloud Run tool API, remote MCP, and A2A calls.

Status: runnable-now
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

_log = logging.getLogger("retailops.observability.correlation")

# Thread-/async-safe context variables
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_span_id_var: ContextVar[str] = ContextVar("span_id", default="")


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(cid: str) -> None:
    _correlation_id_var.set(cid)


def get_correlation_id() -> str:
    cid = _correlation_id_var.get()
    if not cid:
        cid = new_correlation_id()
        set_correlation_id(cid)
    return cid


def new_traceparent() -> str:
    """Generate a W3C traceparent header value for a new trace."""
    version = "00"
    trace_id = uuid.uuid4().hex.zfill(32)
    span_id = uuid.uuid4().hex[:16]
    flags = "01"
    traceparent = f"{version}-{trace_id}-{span_id}-{flags}"
    _trace_id_var.set(trace_id)
    _span_id_var.set(span_id)
    return traceparent


def get_current_traceparent() -> str:
    """Return the current traceparent or generate one if none exists."""
    trace_id = _trace_id_var.get()
    span_id = _span_id_var.get()
    if not trace_id or not span_id:
        return new_traceparent()
    return f"00-{trace_id}-{span_id}-01"


def correlation_headers() -> dict[str, str]:
    """Return HTTP headers for correlation propagation."""
    return {
        "X-Request-ID": get_correlation_id(),
        "traceparent": get_current_traceparent(),
        "X-Correlation-ID": get_correlation_id(),
    }


def extract_from_headers(headers: dict[str, str]) -> str:
    """Extract or generate a correlation ID from incoming HTTP headers."""
    cid = (
        headers.get("x-request-id")
        or headers.get("x-correlation-id")
        or headers.get("X-Request-ID")
        or headers.get("X-Correlation-ID")
        or new_correlation_id()
    )
    set_correlation_id(cid)

    traceparent = headers.get("traceparent") or headers.get("Traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) == 4:
            _trace_id_var.set(parts[1])
            _span_id_var.set(parts[2])

    return cid


def structured_log_fields(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return common structured log fields including correlation IDs."""
    fields: dict[str, Any] = {
        "correlation_id": get_correlation_id(),
        "trace_id": _trace_id_var.get() or "",
        "span_id": _span_id_var.get() or "",
    }
    if extra:
        fields.update(extra)
    return fields
