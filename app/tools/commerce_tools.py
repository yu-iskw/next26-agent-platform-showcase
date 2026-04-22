from __future__ import annotations

from typing import Any, Literal

import httpx

from .cloudrun_auth import (
    authorization_headers_for_tool_api,
    correlation_headers_for_tool_api,
)
from .config import settings


def _url(path: str) -> str:
    return f"{settings.cloudrun_tool_api_base_url.rstrip('/')}{path}"


def _headers() -> dict[str, str]:
    merged = correlation_headers_for_tool_api()
    merged.update(
        authorization_headers_for_tool_api(
            base_url=settings.cloudrun_tool_api_base_url,
            skip_id_token=settings.cloudrun_tool_api_skip_id_token,
        )
    )
    return merged


def _json_request(
    method: Literal["GET", "POST"],
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            _url(path),
            json=json_body,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


def create_purchase_order(product_id: str, units: int, requester: str = "agent") -> dict[str, Any]:
    """Create a replenishment purchase order through the Cloud Run tool API."""
    payload = {"product_id": product_id, "units": units, "requester": requester}
    return _json_request("POST", "/purchase-orders", json_body=payload)


def submit_approval_request(order_id: str, reason: str) -> dict[str, Any]:
    """Submit an approval request for a high-value order."""
    payload = {"order_id": order_id, "reason": reason}
    return _json_request("POST", "/approvals", json_body=payload)


def get_order_status(order_id: str) -> dict[str, Any]:
    """Fetch the status of an existing order."""
    return _json_request("GET", f"/purchase-orders/{order_id}")


def get_tool_api_health() -> dict[str, Any]:
    """GET /healthz on the configured tool API (includes Cloud Run ID token when required)."""
    return _json_request("GET", "/healthz", timeout=10.0)
