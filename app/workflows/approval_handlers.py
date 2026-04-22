"""Approval request and decision handlers.

Status: runnable-now
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.workflows.audit_log import AuditLogger
from app.workflows.state_models import (
    ApprovalDecision,
    ApprovalStatus,
    EscalationPolicy,
    ReplenishmentWorkflowState,
    WorkflowEventType,
    WorkflowStatus,
)
from app.workflows.state_store import WorkflowStateStore

_log = logging.getLogger("retailops.workflow.approval")

APPROVAL_THRESHOLD_USD = 25_000.0


def needs_approval(total_cost_usd: float, risk_tolerance: str = "medium") -> bool:
    """Determine whether a proposed order amount requires human approval.

    Risk tolerance adjusts the threshold:
      low    — 80% of the standard threshold
      medium — standard threshold ($25 000)
      high   — 150% of the standard threshold
    """
    multipliers = {"low": 0.80, "medium": 1.0, "high": 1.5}
    multiplier = multipliers.get(risk_tolerance.lower(), 1.0)
    effective_threshold = APPROVAL_THRESHOLD_USD * multiplier
    return total_cost_usd >= effective_threshold


def request_approval(
    state: ReplenishmentWorkflowState,
    store: WorkflowStateStore,
    audit: AuditLogger | None = None,
    reason: str = "",
) -> ReplenishmentWorkflowState:
    """Transition workflow to PAUSED_FOR_APPROVAL and persist."""
    state.status = WorkflowStatus.PAUSED_FOR_APPROVAL
    state.approval_status = ApprovalStatus.PENDING
    state.approval_requested_at = datetime.now(UTC)

    _deadline = state.approval_deadline()
    evt = state.record_event(
        WorkflowEventType.APPROVAL_REQUESTED,
        actor="system",
        proposed_units=state.proposed_units,
        proposed_total_cost_usd=state.proposed_total_cost_usd,
        reason=reason or f"Order total ${state.proposed_total_cost_usd:,.2f} exceeds approval threshold",
        deadline=_deadline.isoformat() if _deadline is not None else None,
    )
    state.capture_checkpoint(label="approval_requested")
    store.save(state)
    if audit:
        audit.append(evt)
    _log.info("Workflow %s paused for approval (total=$%.2f)", state.workflow_id, state.proposed_total_cost_usd)
    return state


def process_approval_decision(
    state: ReplenishmentWorkflowState,
    decision: ApprovalDecision,
    store: WorkflowStateStore,
    audit: AuditLogger | None = None,
) -> ReplenishmentWorkflowState:
    """Apply an approve/reject decision to a paused workflow."""
    if state.status not in (WorkflowStatus.PAUSED_FOR_APPROVAL, WorkflowStatus.ESCALATED):
        raise ValueError(f"Workflow {state.workflow_id} is not awaiting approval (status={state.status})")

    state.approval_decided_at = decision.decided_at
    state.approver = decision.approver
    state.approval_notes = decision.notes

    if decision.decision == ApprovalStatus.APPROVED:
        state.status = WorkflowStatus.APPROVED
        state.approval_status = ApprovalStatus.APPROVED
        evt = state.record_event(
            WorkflowEventType.APPROVED,
            actor=decision.approver,
            notes=decision.notes,
        )
        _log.info("Workflow %s approved by %s", state.workflow_id, decision.approver)
    elif decision.decision == ApprovalStatus.REJECTED:
        state.status = WorkflowStatus.REJECTED
        state.approval_status = ApprovalStatus.REJECTED
        evt = state.record_event(
            WorkflowEventType.REJECTED,
            actor=decision.approver,
            notes=decision.notes,
        )
        _log.info("Workflow %s rejected by %s: %s", state.workflow_id, decision.approver, decision.notes)
    else:
        raise ValueError(f"Decision must be APPROVED or REJECTED, got {decision.decision}")

    state.capture_checkpoint(label=f"decision_{decision.decision.value.lower()}")
    store.save(state)
    if audit:
        audit.append(evt)
    return state


def request_revision(
    state: ReplenishmentWorkflowState,
    store: WorkflowStateStore,
    revision_notes: str,
    audit: AuditLogger | None = None,
) -> ReplenishmentWorkflowState:
    """Ask the agent/system to revise the proposed order before re-submitting."""
    state.status = WorkflowStatus.REVISION_REQUIRED
    state.revision_notes = revision_notes
    evt = state.record_event(
        WorkflowEventType.REVISION_REQUESTED,
        actor="approver",
        notes=revision_notes,
    )
    state.capture_checkpoint(label="revision_requested")
    store.save(state)
    if audit:
        audit.append(evt)
    _log.info("Workflow %s requires revision: %s", state.workflow_id, revision_notes)
    return state


def check_and_escalate(
    state: ReplenishmentWorkflowState,
    store: WorkflowStateStore,
    audit: AuditLogger | None = None,
    now: datetime | None = None,
) -> ReplenishmentWorkflowState:
    """Escalate the workflow if the approval deadline has passed.

    Returns the (possibly updated) state. Callers should check state.status
    to determine whether escalation occurred.
    """
    if state.status != WorkflowStatus.PAUSED_FOR_APPROVAL:
        return state

    if not state.is_approval_overdue(now):
        return state

    policy: EscalationPolicy = state.escalation_policy
    state.escalation_count += 1

    if state.escalation_count > policy.max_escalations and policy.auto_reject_after_escalations:
        state.status = WorkflowStatus.TIMED_OUT
        state.approval_status = ApprovalStatus.EXPIRED
        evt = state.record_event(
            WorkflowEventType.TIMED_OUT,
            actor="system",
            escalation_count=state.escalation_count,
            reason="Maximum escalations exceeded; auto-rejected",
        )
        _log.warning("Workflow %s timed out after %d escalations", state.workflow_id, state.escalation_count)
    else:
        state.status = WorkflowStatus.ESCALATED
        state.approval_status = ApprovalStatus.ESCALATED
        evt = state.record_event(
            WorkflowEventType.ESCALATED,
            actor="system",
            escalation_count=state.escalation_count,
            escalation_contact=policy.escalation_contact,
        )
        _log.warning(
            "Workflow %s escalated (count=%d) to %s",
            state.workflow_id,
            state.escalation_count,
            policy.escalation_contact,
        )

    state.capture_checkpoint(label=f"escalated_{state.escalation_count}")
    store.save(state)
    if audit:
        audit.append(evt)
    return state
