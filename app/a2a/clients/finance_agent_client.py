"""Finance Approval Agent client.

Wraps the A2A provider's finance routing as a callable for the RetailOps agent.

Status: runnable-now (mock mode)
         preview-scaffold (real Finance agent endpoint)
"""

from __future__ import annotations

import uuid
from typing import Any

from app.a2a.models import A2ATaskRequest
from app.a2a.provider import A2AProvider

_provider: A2AProvider | None = None


def _get_provider() -> A2AProvider:
    global _provider
    if _provider is None:
        _provider = A2AProvider.from_env()
    return _provider


def request_finance_approval(
    order_id: str,
    total_cost_usd: float,
    requester: str = "agent",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Ask the Finance Approval Agent to review a purchase order.

    In local/demo mode this delegates to MockFinanceApprovalAgent.
    In preview mode this would call the registered Gemini Enterprise A2A endpoint.

    Args:
        order_id: The order ID to review.
        total_cost_usd: Total order value in USD.
        requester: Who is requesting approval.
        correlation_id: Optional correlation ID for tracing.

    Returns:
        dict with decision, rationale, and agent metadata.
    """
    task = A2ATaskRequest(
        intent="finance.order.review",
        payload={
            "order_id": order_id,
            "total_cost_usd": total_cost_usd,
            "requester": requester,
        },
        requesting_agent_id="retailops-copilot-v1",
        correlation_id=correlation_id or uuid.uuid4().hex,
    )
    response = _get_provider().route(task)
    return {
        "task_id": response.task_id,
        "status": response.status.value,
        "result": response.result,
        "error": response.error,
        "correlation_id": response.correlation_id,
    }
