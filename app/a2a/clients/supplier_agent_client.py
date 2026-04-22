"""Supplier Negotiation Agent client.

Wraps the A2A provider's supplier routing as a callable for the RetailOps agent.

Status: runnable-now (mock mode)
         preview-scaffold (real Supplier agent endpoint)
"""

from __future__ import annotations

from typing import Any

from app.a2a.models import A2ATaskRequest
from app.a2a.provider import A2AProvider

_provider: A2AProvider | None = None


def _get_provider() -> A2AProvider:
    global _provider
    if _provider is None:
        _provider = A2AProvider.from_env()
    return _provider


def get_supplier_quote(
    product_id: str,
    quantity: int,
    correlation_id: str = "",
) -> dict[str, Any]:
    """Request a supplier pricing quote for a product and quantity.

    In local/demo mode this delegates to MockSupplierNegotiationAgent.
    In preview mode this would call the registered Gemini Enterprise A2A endpoint.

    Args:
        product_id: Internal product identifier.
        quantity: Units to order (affects bulk discount).
        correlation_id: Optional correlation ID for tracing.

    Returns:
        dict with unit_price_usd, total_price_usd, discount_pct, and agent metadata.
    """
    task = A2ATaskRequest(
        intent="supplier.quote.request",
        payload={
            "product_id": product_id,
            "quantity": quantity,
        },
        requesting_agent_id="retailops-copilot-v1",
        **({"correlation_id": correlation_id} if correlation_id else {}),
    )
    response = _get_provider().route(task)
    return {
        "task_id": response.task_id,
        "status": response.status.value,
        "result": response.result,
        "error": response.error,
        "correlation_id": response.correlation_id,
    }
