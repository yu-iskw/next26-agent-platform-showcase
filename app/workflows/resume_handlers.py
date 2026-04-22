"""Workflow resume and replay helpers.

Status: runnable-now
"""
from __future__ import annotations

import logging
from typing import Any

from app.workflows.audit_log import AuditLogger, reconstruct_state_from_events
from app.workflows.state_models import ReplenishmentWorkflowState, WorkflowEventType, WorkflowStatus
from app.workflows.state_store import WorkflowStateStore

_log = logging.getLogger("retailops.workflow.resume")


def resume_after_approval(
    workflow_id: str,
    store: WorkflowStateStore,
    audit: AuditLogger | None = None,
) -> ReplenishmentWorkflowState:
    """Continue a workflow that has just been approved.

    Transitions APPROVED → RUNNING and records a RESUMED event.
    The caller (workflow engine) is responsible for executing the next step.
    """
    state = store.load(workflow_id)
    if state is None:
        raise KeyError(f"Workflow {workflow_id} not found in state store")

    if state.status != WorkflowStatus.APPROVED:
        raise ValueError(f"Workflow {workflow_id} cannot be resumed from status={state.status}")

    state.status = WorkflowStatus.RUNNING
    evt = state.record_event(WorkflowEventType.RESUMED, actor="system", trigger="approval")
    state.capture_checkpoint(label="resumed_after_approval")
    store.save(state)
    if audit:
        audit.append(evt)
    _log.info("Workflow %s resumed after approval", workflow_id)
    return state


def replay_workflow_timeline(
    workflow_id: str,
    audit: AuditLogger | None = None,
    state_dir: str | None = None,
) -> dict[str, Any]:
    """Reconstruct workflow summary from audit log for debugging or display.

    Uses the audit log (append-only events) — not the mutable state file —
    so it reflects the true history even if the state file was corrupted.
    """
    logger = audit or AuditLogger(state_dir)
    events = logger.read_all(workflow_id)
    if not events:
        return {"error": f"No audit events found for workflow_id={workflow_id}"}
    return reconstruct_state_from_events(events)


def get_workflow_explanation(state: ReplenishmentWorkflowState) -> str:
    """Return a human-readable explanation of why the workflow is in its current state."""
    explanations: dict[WorkflowStatus, str] = {
        WorkflowStatus.CREATED: "The workflow has been created but not yet started.",
        WorkflowStatus.RUNNING: "The workflow is actively processing.",
        WorkflowStatus.PAUSED_FOR_APPROVAL: (
            f"The proposed order (${state.proposed_total_cost_usd:,.2f}) exceeds the approval threshold "
            f"and is awaiting sign-off from an authorized approver. "
            f"Deadline: {state.approval_deadline().strftime('%Y-%m-%d %H:%M UTC') if state.approval_deadline() else 'N/A'}."
        ),
        WorkflowStatus.APPROVED: "The order has been approved and is ready to be finalized.",
        WorkflowStatus.REJECTED: f"The order was rejected. Reason: {state.approval_notes or 'Not specified'}.",
        WorkflowStatus.REVISION_REQUIRED: f"The order requires revision before re-submission. Notes: {state.revision_notes}.",
        WorkflowStatus.ESCALATED: (
            f"The approval deadline passed without a decision. "
            f"The request has been escalated (count={state.escalation_count}) "
            f"to {state.escalation_policy.escalation_contact}."
        ),
        WorkflowStatus.TIMED_OUT: (
            "The workflow timed out after exceeding the maximum number of escalations. "
            "The order was auto-rejected."
        ),
        WorkflowStatus.COMPLETED: "The order was finalized and submitted successfully.",
        WorkflowStatus.FAILED: f"The workflow failed. Reason: {state.failure_reason or 'Unknown'}.",
    }
    return explanations.get(state.status, f"Unknown status: {state.status}")
