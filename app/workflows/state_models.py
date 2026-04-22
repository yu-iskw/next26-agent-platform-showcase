"""Typed domain models for the ReplenishmentWorkflow state machine.

Status: runnable-now
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED_FOR_APPROVAL = "PAUSED_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class WorkflowEventType(str, Enum):
    CREATED = "CREATED"
    RECOMMENDATION_COMPUTED = "RECOMMENDATION_COMPUTED"
    ORDER_PROPOSED = "ORDER_PROPOSED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    ESCALATED = "ESCALATED"
    TIMED_OUT = "TIMED_OUT"
    RESUMED = "RESUMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CHECKPOINT = "CHECKPOINT"


class EscalationPolicy(BaseModel):
    """Policy governing when and how to escalate a stalled approval."""

    approval_timeout_hours: float = Field(default=24.0, ge=0.1)
    escalation_contact: str = Field(default="manager@retailops.example")
    max_escalations: int = Field(default=2, ge=1)
    auto_reject_after_escalations: bool = Field(default=True)


class ApprovalDecision(BaseModel):
    """A decision (approve / reject) made by a human approver."""

    workflow_id: str
    approver: str
    decision: ApprovalStatus  # APPROVED or REJECTED
    notes: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowEvent(BaseModel):
    """Immutable event record for event-sourcing and audit replay."""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    workflow_id: str
    event_type: WorkflowEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = "system"
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowCheckpoint(BaseModel):
    """Point-in-time snapshot of workflow state used for replay and debugging."""

    checkpoint_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    workflow_id: str
    status: WorkflowStatus
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    label: str = ""


class ReplenishmentWorkflowState(BaseModel):
    """Complete mutable state for a single replenishment workflow instance."""

    # Identity
    workflow_id: str = Field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:10]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Inputs
    product_id: str = ""
    product_name: str = ""
    requester: str = "agent"
    risk_tolerance: str = "medium"  # low / medium / high

    # Recommendation
    recommended_units: int = 0
    estimated_unit_cost_usd: float = 0.0
    estimated_total_cost_usd: float = 0.0
    reorder_point: int = 0
    current_stock: int = 0

    # Proposed order
    order_id: str = ""
    proposed_units: int = 0
    proposed_total_cost_usd: float = 0.0

    # Approval
    approval_required: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_requested_at: datetime | None = None
    approval_decided_at: datetime | None = None
    approver: str = ""
    approval_notes: str = ""
    escalation_count: int = 0
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)

    # Workflow control
    status: WorkflowStatus = WorkflowStatus.CREATED
    failure_reason: str = ""
    revision_notes: str = ""

    # History
    events: list[WorkflowEvent] = Field(default_factory=list)
    checkpoints: list[WorkflowCheckpoint] = Field(default_factory=list)

    def record_event(self, event_type: WorkflowEventType, actor: str = "system", **payload: Any) -> WorkflowEvent:
        """Append an immutable event to the event log."""
        evt = WorkflowEvent(
            workflow_id=self.workflow_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
        )
        self.events.append(evt)
        self.updated_at = datetime.now(UTC)
        return evt

    def capture_checkpoint(self, label: str = "") -> WorkflowCheckpoint:
        """Snapshot current state for replay / audit."""
        ckpt = WorkflowCheckpoint(
            workflow_id=self.workflow_id,
            status=self.status,
            label=label,
            state_snapshot={
                "status": self.status.value,
                "approval_status": self.approval_status.value,
                "proposed_units": self.proposed_units,
                "proposed_total_cost_usd": self.proposed_total_cost_usd,
                "escalation_count": self.escalation_count,
            },
        )
        self.checkpoints.append(ckpt)
        return ckpt

    def approval_deadline(self) -> datetime | None:
        if self.approval_requested_at is None:
            return None
        return self.approval_requested_at + timedelta(hours=self.escalation_policy.approval_timeout_hours)

    def is_approval_overdue(self, now: datetime | None = None) -> bool:
        deadline = self.approval_deadline()
        if deadline is None:
            return False
        now = now or datetime.now(UTC)
        return now >= deadline

    def human_readable_timeline(self) -> list[str]:
        """Render events as a human-readable timeline for debugging."""
        lines: list[str] = []
        for evt in self.events:
            ts = evt.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            payload_str = ", ".join(f"{k}={v}" for k, v in evt.payload.items()) if evt.payload else ""
            line = f"[{ts}] {evt.event_type.value} actor={evt.actor}"
            if payload_str:
                line += f" ({payload_str})"
            lines.append(line)
        return lines
