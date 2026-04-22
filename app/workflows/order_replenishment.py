"""ReplenishmentWorkflowEngine — durable, resumable order replenishment workflow.

Orchestrates the full lifecycle:
  create → recommend → propose → [approval?] → finalize

Status: runnable-now (local JSON state store)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.workflows.approval_handlers import check_and_escalate, needs_approval, request_approval
from app.workflows.audit_log import AuditLogger
from app.workflows.state_models import (
    ApprovalDecision,
    EscalationPolicy,
    ReplenishmentWorkflowState,
    WorkflowEventType,
    WorkflowStatus,
)
from app.workflows.state_store import WorkflowStateStore, get_default_state_store

_log = logging.getLogger("retailops.workflow.engine")

_DEFAULT_UNIT_COST_USD = 120.0  # Fallback when product cost is not yet known


class ReplenishmentWorkflowEngine:
    """Drives a replenishment workflow through its state machine.

    Usage::

        engine = ReplenishmentWorkflowEngine()
        state = engine.create_workflow("product-001", requester="alice")
        state = engine.compute_recommendation(state.workflow_id, current_stock=42, reorder_point=80)
        state = engine.propose_order(state.workflow_id)
        state = engine.advance(state.workflow_id)   # pauses if approval needed
        # ... later, after human approves:
        state = engine.apply_approval(state.workflow_id, decision)
        state = engine.finalize(state.workflow_id)
    """

    def __init__(
        self,
        store: WorkflowStateStore | None = None,
        audit: AuditLogger | None = None,
    ) -> None:
        self._store = store or get_default_state_store()
        self._audit = audit or AuditLogger()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_workflow(
        self,
        product_id: str,
        product_name: str = "",
        requester: str = "agent",
        risk_tolerance: str = "medium",
        escalation_policy: EscalationPolicy | None = None,
    ) -> ReplenishmentWorkflowState:
        """Create and persist a new replenishment workflow."""
        state = ReplenishmentWorkflowState(
            product_id=product_id,
            product_name=product_name,
            requester=requester,
            risk_tolerance=risk_tolerance,
            escalation_policy=escalation_policy or EscalationPolicy(),
        )
        evt = state.record_event(
            WorkflowEventType.CREATED,
            actor=requester,
            product_id=product_id,
            product_name=product_name,
            risk_tolerance=risk_tolerance,
        )
        state.capture_checkpoint(label="created")
        self._store.save(state)
        self._audit.append(evt)
        _log.info("Created workflow %s for product %s", state.workflow_id, product_id)
        return state

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    def compute_recommendation(
        self,
        workflow_id: str,
        current_stock: int,
        reorder_point: int,
        estimated_unit_cost_usd: float = _DEFAULT_UNIT_COST_USD,
        multiplier: float = 1.25,
    ) -> ReplenishmentWorkflowState:
        """Compute and persist a reorder recommendation."""
        state = self._load_or_raise(workflow_id)
        if state.status not in (WorkflowStatus.CREATED, WorkflowStatus.RUNNING):
            raise ValueError(f"Cannot compute recommendation for workflow in status={state.status}")

        shortfall = max(0, reorder_point - current_stock)
        recommended = round(shortfall * multiplier) if shortfall > 0 else 0

        state.current_stock = current_stock
        state.reorder_point = reorder_point
        state.recommended_units = recommended
        state.estimated_unit_cost_usd = estimated_unit_cost_usd
        state.estimated_total_cost_usd = round(recommended * estimated_unit_cost_usd, 2)
        state.status = WorkflowStatus.RUNNING

        evt = state.record_event(
            WorkflowEventType.RECOMMENDATION_COMPUTED,
            actor="system",
            current_stock=current_stock,
            reorder_point=reorder_point,
            recommended_units=recommended,
            estimated_total_cost_usd=state.estimated_total_cost_usd,
        )
        self._store.save(state)
        self._audit.append(evt)
        return state

    # ------------------------------------------------------------------
    # Propose order
    # ------------------------------------------------------------------

    def propose_order(
        self,
        workflow_id: str,
        override_units: int | None = None,
        unit_cost_override: float | None = None,
    ) -> ReplenishmentWorkflowState:
        """Create a proposed order (can override recommended units)."""
        state = self._load_or_raise(workflow_id)
        if state.status != WorkflowStatus.RUNNING:
            raise ValueError(f"Cannot propose order for workflow in status={state.status}")

        units = override_units if override_units is not None else state.recommended_units
        unit_cost = unit_cost_override or state.estimated_unit_cost_usd or _DEFAULT_UNIT_COST_USD

        state.proposed_units = units
        state.proposed_total_cost_usd = round(units * unit_cost, 2)
        state.approval_required = needs_approval(state.proposed_total_cost_usd, state.risk_tolerance)

        evt = state.record_event(
            WorkflowEventType.ORDER_PROPOSED,
            actor=state.requester,
            proposed_units=units,
            proposed_total_cost_usd=state.proposed_total_cost_usd,
            approval_required=state.approval_required,
        )
        self._store.save(state)
        self._audit.append(evt)
        return state

    # ------------------------------------------------------------------
    # Advance (auto-route to approval or finalize)
    # ------------------------------------------------------------------

    def advance(self, workflow_id: str) -> ReplenishmentWorkflowState:
        """Advance the workflow to the next logical state.

        If the proposed order requires approval: transition to PAUSED_FOR_APPROVAL.
        Otherwise: finalize directly.
        """
        state = self._load_or_raise(workflow_id)
        if state.approval_required:
            return request_approval(state, self._store, self._audit)
        return self.finalize(workflow_id)

    # ------------------------------------------------------------------
    # Approval lifecycle
    # ------------------------------------------------------------------

    def apply_approval(
        self,
        workflow_id: str,
        decision: ApprovalDecision,
    ) -> ReplenishmentWorkflowState:
        """Apply a human approval decision to a paused workflow.

        After approving, the caller must call ``finalize()`` to complete the order.
        """
        from app.workflows.approval_handlers import process_approval_decision

        state = self._load_or_raise(workflow_id)
        return process_approval_decision(state, decision, self._store, self._audit)

    def check_escalation(
        self,
        workflow_id: str,
        now: datetime | None = None,
    ) -> ReplenishmentWorkflowState:
        """Check and apply escalation if the approval deadline has passed."""
        state = self._load_or_raise(workflow_id)
        return check_and_escalate(state, self._store, self._audit, now)

    def request_revision(self, workflow_id: str, revision_notes: str) -> ReplenishmentWorkflowState:
        """Ask for a revised order proposal (sets status=REVISION_REQUIRED)."""
        from app.workflows.approval_handlers import request_revision as _request_revision

        state = self._load_or_raise(workflow_id)
        return _request_revision(state, self._store, revision_notes, self._audit)

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(self, workflow_id: str) -> ReplenishmentWorkflowState:
        """Finalize the order (submit to backend) and mark COMPLETED."""
        state = self._load_or_raise(workflow_id)
        allowed = {WorkflowStatus.RUNNING, WorkflowStatus.APPROVED}
        if state.status not in allowed:
            raise ValueError(f"Cannot finalize workflow in status={state.status}")

        # In a real integration this would call commerce_tools.create_purchase_order.
        # We generate a synthetic order_id here to keep the engine decoupled.
        import uuid

        state.order_id = f"po-{uuid.uuid4().hex[:10]}"
        state.status = WorkflowStatus.COMPLETED

        evt = state.record_event(
            WorkflowEventType.COMPLETED,
            actor="system",
            order_id=state.order_id,
            finalized_units=state.proposed_units,
            finalized_total_usd=state.proposed_total_cost_usd,
        )
        state.capture_checkpoint(label="completed")
        self._store.save(state)
        self._audit.append(evt)
        _log.info("Workflow %s completed; order_id=%s", workflow_id, state.order_id)
        return state

    def mark_failed(self, workflow_id: str, reason: str) -> ReplenishmentWorkflowState:
        """Mark a workflow as failed with an explanatory reason."""
        state = self._load_or_raise(workflow_id)
        state.status = WorkflowStatus.FAILED
        state.failure_reason = reason
        evt = state.record_event(WorkflowEventType.FAILED, actor="system", reason=reason)
        state.capture_checkpoint(label="failed")
        self._store.save(state)
        self._audit.append(evt)
        _log.error("Workflow %s failed: %s", workflow_id, reason)
        return state

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_status(self, workflow_id: str) -> dict[str, Any]:
        """Return a summary dict for agent consumption."""
        state = self._load_or_raise(workflow_id)
        from app.workflows.resume_handlers import get_workflow_explanation

        return {
            "workflow_id": state.workflow_id,
            "status": state.status.value,
            "product_id": state.product_id,
            "product_name": state.product_name,
            "proposed_units": state.proposed_units,
            "proposed_total_cost_usd": state.proposed_total_cost_usd,
            "approval_required": state.approval_required,
            "approval_status": state.approval_status.value,
            "order_id": state.order_id,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "explanation": get_workflow_explanation(state),
            "timeline": state.human_readable_timeline(),
        }

    def list_pending(self) -> list[dict[str, Any]]:
        """List all workflows awaiting approval."""
        return [
            {
                "workflow_id": s.workflow_id,
                "status": s.status.value,
                "product_id": s.product_id,
                "proposed_total_cost_usd": s.proposed_total_cost_usd,
                "approval_requested_at": s.approval_requested_at.isoformat() if s.approval_requested_at else None,
                "overdue": s.is_approval_overdue(),
            }
            for s in self._store.list_pending()
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_or_raise(self, workflow_id: str) -> ReplenishmentWorkflowState:
        state = self._store.load(workflow_id)
        if state is None:
            raise KeyError(f"Workflow {workflow_id} not found")
        return state
