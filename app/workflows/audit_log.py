"""Append-only audit log for workflow events.

Writes structured JSONL to a per-workflow file under WORKFLOW_STATE_DIR/audit/.
Supports replay: ``reconstruct_state_from_events`` rebuilds a state dict from the log.

Status: runnable-now
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.workflows.state_models import WorkflowEvent, WorkflowEventType

_log = logging.getLogger("retailops.workflow.audit")

_LOCAL_STATE_DIR = Path(os.getenv("WORKFLOW_STATE_DIR", ".local/state"))


class AuditLogger:
    """Writes append-only JSONL audit entries for a workflow."""

    def __init__(self, state_dir: Path | str | None = None) -> None:
        base = Path(state_dir) if state_dir else _LOCAL_STATE_DIR
        self._audit_dir = base / "audit"
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, workflow_id: str) -> Path:
        safe = workflow_id.replace("/", "_").replace("..", "_")
        return self._audit_dir / f"{safe}.jsonl"

    def append(self, event: WorkflowEvent) -> None:
        """Append a single event to the workflow's audit log."""
        path = self._path(event.workflow_id)
        entry = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(entry + "\n")
        except OSError as exc:
            _log.error("Failed to write audit entry for %s: %s", event.workflow_id, exc)
            raise

    def read_all(self, workflow_id: str) -> list[WorkflowEvent]:
        """Read all audit events for a workflow in chronological order."""
        path = self._path(workflow_id)
        if not path.exists():
            return []
        events: list[WorkflowEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data: dict[str, Any] = json.loads(line)
                events.append(WorkflowEvent.model_validate(data))
            except (json.JSONDecodeError, ValueError) as exc:
                _log.warning("Skipping corrupted audit line: %s", exc)
        return events

    def render_timeline(self, workflow_id: str) -> list[str]:
        """Return human-readable timeline strings for display or debugging."""
        lines: list[str] = []
        for evt in self.read_all(workflow_id):
            ts = evt.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            payload_str = ", ".join(f"{k}={v}" for k, v in evt.payload.items()) if evt.payload else ""
            line = f"[{ts}] {evt.event_type.value} actor={evt.actor}"
            if payload_str:
                line += f" | {payload_str}"
            lines.append(line)
        return lines


def reconstruct_state_from_events(events: list[WorkflowEvent]) -> dict[str, Any]:
    """Rebuild a lightweight state summary by replaying audit events.

    This is not a full state reconstruction — it produces a summary dict
    useful for debugging and timeline rendering.  The authoritative state
    lives in the state store.
    """
    summary: dict[str, Any] = {
        "workflow_id": events[0].workflow_id if events else "",
        "status": "UNKNOWN",
        "approval_status": "UNKNOWN",
        "events_replayed": len(events),
        "timeline": [],
    }
    for evt in events:
        ts = evt.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        summary["timeline"].append(f"[{ts}] {evt.event_type.value} by {evt.actor}")

        if evt.event_type == WorkflowEventType.CREATED:
            summary["status"] = "CREATED"
            summary.update(evt.payload)
        elif evt.event_type == WorkflowEventType.ORDER_PROPOSED:
            summary["status"] = "RUNNING"
            summary["proposed_units"] = evt.payload.get("proposed_units")
            summary["proposed_total_cost_usd"] = evt.payload.get("proposed_total_cost_usd")
        elif evt.event_type == WorkflowEventType.APPROVAL_REQUESTED:
            summary["status"] = "PAUSED_FOR_APPROVAL"
            summary["approval_status"] = "PENDING"
            summary["approval_requested_at"] = evt.timestamp.isoformat()
        elif evt.event_type == WorkflowEventType.APPROVED:
            summary["status"] = "APPROVED"
            summary["approval_status"] = "APPROVED"
            summary["approver"] = evt.actor
        elif evt.event_type == WorkflowEventType.REJECTED:
            summary["status"] = "REJECTED"
            summary["approval_status"] = "REJECTED"
            summary["approver"] = evt.actor
            summary["rejection_notes"] = evt.payload.get("notes", "")
        elif evt.event_type == WorkflowEventType.ESCALATED:
            summary["status"] = "ESCALATED"
            summary["approval_status"] = "ESCALATED"
        elif evt.event_type == WorkflowEventType.COMPLETED:
            summary["status"] = "COMPLETED"
        elif evt.event_type == WorkflowEventType.FAILED:
            summary["status"] = "FAILED"
            summary["failure_reason"] = evt.payload.get("reason", "")

    summary["last_event_at"] = events[-1].timestamp.isoformat() if events else None
    return summary


def log_event(workflow_id: str, event_type: WorkflowEventType, actor: str = "system", **payload: Any) -> None:
    """Convenience function: create and append one audit event."""
    evt = WorkflowEvent(
        workflow_id=workflow_id,
        event_type=event_type,
        actor=actor,
        timestamp=datetime.now(UTC),
        payload=payload,
    )
    AuditLogger().append(evt)
