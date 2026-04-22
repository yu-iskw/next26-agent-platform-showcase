"""Agent-callable workflow tools for the ReplenishmentWorkflowEngine.

These functions wrap the workflow engine so the ADK agent can initiate, inspect,
approve, reject, and resume workflows through natural-language requests.

Status: runnable-now
"""
from __future__ import annotations

import logging
from typing import Any

from app.workflows.order_replenishment import ReplenishmentWorkflowEngine
from app.workflows.state_models import ApprovalDecision, ApprovalStatus, EscalationPolicy

_log = logging.getLogger("retailops.tools.workflow")
_engine: ReplenishmentWorkflowEngine | None = None


def _get_engine() -> ReplenishmentWorkflowEngine:
    global _engine
    if _engine is None:
        _engine = ReplenishmentWorkflowEngine()
    return _engine


def start_replenishment_workflow(
    product_id: str,
    product_name: str = "",
    requester: str = "agent",
    risk_tolerance: str = "medium",
    current_stock: int = 0,
    reorder_point: int = 0,
    estimated_unit_cost_usd: float = 120.0,
) -> dict[str, Any]:
    """Start a durable replenishment workflow and return the workflow ID.

    The workflow is persisted locally and will survive agent session restarts.
    If the proposed order exceeds the approval threshold it will be paused
    and the caller must later call approve_workflow or reject_workflow.

    Args:
        product_id: Internal product identifier (e.g. "prod-001").
        product_name: Human-readable product name (optional, for display).
        requester: Who is initiating the workflow (defaults to "agent").
        risk_tolerance: "low", "medium" (default), or "high" — adjusts approval threshold.
        current_stock: Current units in warehouse.
        reorder_point: Threshold below which reorder is triggered.
        estimated_unit_cost_usd: Unit cost for order value estimation.

    Returns:
        dict with workflow_id, status, proposed_units, approval_required, explanation.
    """
    engine = _get_engine()
    state = engine.create_workflow(
        product_id=product_id,
        product_name=product_name,
        requester=requester,
        risk_tolerance=risk_tolerance,
    )
    state = engine.compute_recommendation(
        state.workflow_id,
        current_stock=current_stock,
        reorder_point=reorder_point,
        estimated_unit_cost_usd=estimated_unit_cost_usd,
    )
    state = engine.propose_order(state.workflow_id)
    state = engine.advance(state.workflow_id)
    return engine.get_status(state.workflow_id)


def get_workflow_status(workflow_id: str) -> dict[str, Any]:
    """Fetch current status and timeline for a replenishment workflow.

    Args:
        workflow_id: The workflow_id returned when the workflow was created.

    Returns:
        dict with status, explanation, timeline, and order details.
    """
    try:
        return _get_engine().get_status(workflow_id)
    except KeyError:
        return {"error": f"Workflow {workflow_id!r} not found"}


def list_pending_approvals() -> dict[str, Any]:
    """Return all replenishment workflows currently awaiting human approval.

    Returns:
        dict with ``pending`` list and ``count``.
    """
    pending = _get_engine().list_pending()
    return {"count": len(pending), "pending": pending}


def approve_workflow(workflow_id: str, approver: str = "human", notes: str = "") -> dict[str, Any]:
    """Approve a paused replenishment workflow and finalize the order.

    Args:
        workflow_id: The workflow to approve.
        approver: Name/email of the approving user.
        notes: Optional approval notes.

    Returns:
        Updated workflow status dict.
    """
    engine = _get_engine()
    decision = ApprovalDecision(
        workflow_id=workflow_id,
        approver=approver,
        decision=ApprovalStatus.APPROVED,
        notes=notes,
    )
    try:
        engine.apply_approval(workflow_id, decision)
        engine.finalize(workflow_id)
        return engine.get_status(workflow_id)
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


def reject_workflow(workflow_id: str, approver: str = "human", notes: str = "") -> dict[str, Any]:
    """Reject a paused replenishment workflow.

    Args:
        workflow_id: The workflow to reject.
        approver: Name/email of the rejecting user.
        notes: Reason for rejection (required for audit trail).

    Returns:
        Updated workflow status dict.
    """
    engine = _get_engine()
    decision = ApprovalDecision(
        workflow_id=workflow_id,
        approver=approver,
        decision=ApprovalStatus.REJECTED,
        notes=notes,
    )
    try:
        engine.apply_approval(workflow_id, decision)
        return engine.get_status(workflow_id)
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


def resume_workflow_after_approval(workflow_id: str) -> dict[str, Any]:
    """Resume a workflow that is in APPROVED state (re-enters RUNNING for finalization).

    Args:
        workflow_id: The workflow to resume.

    Returns:
        Updated workflow status dict.
    """
    from app.workflows.resume_handlers import resume_after_approval
    from app.workflows.state_store import get_default_state_store

    try:
        store = get_default_state_store()
        resume_after_approval(workflow_id, store)
        return _get_engine().get_status(workflow_id)
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


def get_workflow_explanation(workflow_id: str) -> dict[str, Any]:
    """Explain why a workflow is in its current state in plain language.

    Args:
        workflow_id: The workflow to explain.

    Returns:
        dict with explanation string and current status.
    """
    try:
        status = _get_engine().get_status(workflow_id)
        return {
            "workflow_id": workflow_id,
            "status": status["status"],
            "explanation": status["explanation"],
        }
    except KeyError:
        return {"error": f"Workflow {workflow_id!r} not found"}
