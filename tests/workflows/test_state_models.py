"""Tests for workflow state models and domain logic."""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.workflows.state_models import (
    ApprovalStatus,
    EscalationPolicy,
    ReplenishmentWorkflowState,
    WorkflowEventType,
    WorkflowStatus,
)


class TestEscalationPolicy(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = EscalationPolicy()
        self.assertEqual(policy.approval_timeout_hours, 24.0)
        self.assertEqual(policy.max_escalations, 2)
        self.assertTrue(policy.auto_reject_after_escalations)

    def test_custom_timeout(self) -> None:
        policy = EscalationPolicy(approval_timeout_hours=1.0, max_escalations=1)
        self.assertEqual(policy.approval_timeout_hours, 1.0)


class TestReplenishmentWorkflowState(unittest.TestCase):
    def _make_state(self) -> ReplenishmentWorkflowState:
        return ReplenishmentWorkflowState(product_id="prod-001", requester="test")

    def test_default_status(self) -> None:
        state = self._make_state()
        self.assertEqual(state.status, WorkflowStatus.CREATED)
        self.assertEqual(state.approval_status, ApprovalStatus.PENDING)

    def test_workflow_id_generated(self) -> None:
        state = self._make_state()
        self.assertTrue(state.workflow_id.startswith("wf-"))

    def test_record_event(self) -> None:
        state = self._make_state()
        evt = state.record_event(WorkflowEventType.CREATED, actor="test_actor", product_id="prod-001")
        self.assertEqual(len(state.events), 1)
        self.assertEqual(evt.event_type, WorkflowEventType.CREATED)
        self.assertEqual(evt.actor, "test_actor")
        self.assertEqual(evt.payload["product_id"], "prod-001")

    def test_capture_checkpoint(self) -> None:
        state = self._make_state()
        ckpt = state.capture_checkpoint(label="test_label")
        self.assertEqual(len(state.checkpoints), 1)
        self.assertEqual(ckpt.label, "test_label")
        self.assertEqual(ckpt.status, WorkflowStatus.CREATED)

    def test_approval_deadline_none_when_not_requested(self) -> None:
        state = self._make_state()
        self.assertIsNone(state.approval_deadline())
        self.assertFalse(state.is_approval_overdue())

    def test_approval_deadline_future(self) -> None:
        state = self._make_state()
        state.approval_requested_at = datetime.now(UTC)
        deadline = state.approval_deadline()
        self.assertIsNotNone(deadline)
        assert deadline is not None
        self.assertGreater(deadline, datetime.now(UTC))
        self.assertFalse(state.is_approval_overdue())

    def test_approval_overdue(self) -> None:
        state = self._make_state()
        state.approval_requested_at = datetime.now(UTC) - timedelta(hours=25)
        self.assertTrue(state.is_approval_overdue())

    def test_human_readable_timeline(self) -> None:
        state = self._make_state()
        state.record_event(WorkflowEventType.CREATED, actor="alice")
        state.record_event(WorkflowEventType.ORDER_PROPOSED, actor="system", proposed_units=100)
        timeline = state.human_readable_timeline()
        self.assertEqual(len(timeline), 2)
        self.assertIn("CREATED", timeline[0])
        self.assertIn("ORDER_PROPOSED", timeline[1])

    def test_serialization_roundtrip(self) -> None:
        state = self._make_state()
        state.record_event(WorkflowEventType.CREATED, actor="test")
        json_str = state.model_dump_json()
        restored = ReplenishmentWorkflowState.model_validate_json(json_str)
        self.assertEqual(restored.workflow_id, state.workflow_id)
        self.assertEqual(len(restored.events), 1)


if __name__ == "__main__":
    unittest.main()
