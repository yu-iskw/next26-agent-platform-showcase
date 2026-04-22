"""OpenTelemetry trace helpers for RetailOps.

Provides lightweight wrappers around the existing OTel SDK usage in the repo.
Adds structured log emission alongside span creation.

Status: runnable-now (no-op when OTel SDK not configured)
"""
from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

_log = logging.getLogger("retailops.observability.trace")

F = TypeVar("F", bound=Callable[..., Any])


def _otel_available() -> bool:
    try:
        from opentelemetry import trace  # noqa: F401

        return True
    except ImportError:
        return False


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Generator[None, None, None]:
    """Context manager that creates an OTel span if OTel is configured, else is a no-op.

    Usage::

        with span("workflow.finalize", {"workflow_id": wf_id}):
            engine.finalize(wf_id)
    """
    if not _otel_available():
        yield
        return

    from opentelemetry import trace as otel_trace

    tracer = otel_trace.get_tracer("retailops")
    with tracer.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                s.set_attribute(k, str(v))
        yield


def timed(fn: F) -> F:
    """Decorator that logs execution duration for any function."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            _log.info("timed fn=%s elapsed_ms=%s", fn.__qualname__, elapsed_ms)

    return wrapper  # type: ignore[return-value]


def record_metric(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Emit a gauge metric.  Uses OTel metrics when available, else logs.

    This is intentionally lightweight — in production hook up a real meter
    via the OTel SDK configured in your Cloud Run / Agent Runtime environment.
    """
    label_str = " ".join(f"{k}={v}" for k, v in (labels or {}).items())
    _log.info("metric name=%s value=%s %s", name, value, label_str)

    if not _otel_available():
        return

    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("retailops")
        gauge = meter.create_gauge(name)
        gauge.set(value, labels or {})
    except Exception:
        pass


def latency_histogram(name: str, elapsed_ms: float, labels: dict[str, str] | None = None) -> None:
    """Record a latency measurement as a histogram."""
    record_metric(f"{name}.latency_ms", elapsed_ms, labels)
