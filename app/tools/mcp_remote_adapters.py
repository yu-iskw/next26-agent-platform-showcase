"""Shared business logic layer for transport-agnostic tool serving.

This module is the single source of truth for all tool operations.
REST, stdio MCP, and remote MCP transports are thin wrappers around these functions.

Architecture:
  commerce_tools / workflow_tools  →  shared service layer (this file)
    ├─ cloudrun/tool_api/main.py   REST transport
    ├─ app/tools/mcp_stdio_retailops.py   stdio MCP transport
    └─ cloudrun/remote_mcp/main.py        remote MCP transport

Status: runnable-now
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger("retailops.mcp.adapters")


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# Commerce operations (thin wrappers — shared with stdio MCP)
# ---------------------------------------------------------------------------


def tool_create_purchase_order(product_id: str, units: int, requester: str = "agent") -> str:
    """Create a purchase order via the Cloud Run REST API and return JSON."""
    from app.tools.commerce_tools import create_purchase_order

    return _json(create_purchase_order(product_id, units, requester))


def tool_submit_approval_request(order_id: str, reason: str) -> str:
    """Submit an approval request for a high-value order."""
    from app.tools.commerce_tools import submit_approval_request

    return _json(submit_approval_request(order_id, reason))


def tool_get_order_status(order_id: str) -> str:
    """Fetch purchase order status by order_id."""
    from app.tools.commerce_tools import get_order_status

    return _json(get_order_status(order_id))


def tool_check_health() -> str:
    """Call GET /healthz on the configured Cloud Run tool API."""
    from app.tools.commerce_tools import get_tool_api_health

    return _json(get_tool_api_health())


# ---------------------------------------------------------------------------
# Workflow operations (new — Workstream A)
# ---------------------------------------------------------------------------


def tool_start_replenishment_workflow(  # noqa: PLR0913
    product_id: str,
    product_name: str = "",
    requester: str = "agent",
    risk_tolerance: str = "medium",
    current_stock: int = 0,
    reorder_point: int = 0,
    estimated_unit_cost_usd: float = 120.0,
) -> str:
    """Start a durable replenishment workflow and return JSON with workflow_id."""
    from app.tools.workflow_tools import start_replenishment_workflow

    return _json(
        start_replenishment_workflow(
            product_id=product_id,
            product_name=product_name,
            requester=requester,
            risk_tolerance=risk_tolerance,
            current_stock=current_stock,
            reorder_point=reorder_point,
            estimated_unit_cost_usd=estimated_unit_cost_usd,
        )
    )


def tool_get_workflow_status(workflow_id: str) -> str:
    """Fetch workflow status by workflow_id."""
    from app.tools.workflow_tools import get_workflow_status

    return _json(get_workflow_status(workflow_id))


def tool_list_pending_approvals() -> str:
    """Return all workflows currently awaiting approval."""
    from app.tools.workflow_tools import list_pending_approvals

    return _json(list_pending_approvals())


def tool_approve_workflow(workflow_id: str, approver: str = "human", notes: str = "") -> str:
    """Approve a paused workflow and finalize the order."""
    from app.tools.workflow_tools import approve_workflow

    return _json(approve_workflow(workflow_id, approver, notes))


def tool_reject_workflow(workflow_id: str, approver: str = "human", notes: str = "") -> str:
    """Reject a paused workflow."""
    from app.tools.workflow_tools import reject_workflow

    return _json(reject_workflow(workflow_id, approver, notes))
