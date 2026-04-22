"""Integration tests for the ReplenishmentWorkflowEngine.

Tests cover:
  - approval threshold behavior
  - pause/resume flow
  - rejection/revision flow
  - escalation timeout logic
  - corrupted local state handling
  - audit log replay correctness
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.workflows.approval_handlers import needs_approval
from app.workflows.audit_log import AuditLogger, reconstruct_state_from_events
from app.workflows.order_replenishment import ReplenishmentWorkflowEngine
from app.workflows.state_models import (
    ApprovalDecision,
    ApprovalStatus,
    EscalationPolicy,
    WorkflowStatus,
)
from app.workflows.state_store import LocalJsonWorkflowStateStore


class TestApprovalThreshold(unittest.TestCase):
    def test_below_threshold_no_approval(self) -> None:
        self.assertFalse(needs_approval(20_000.0, "medium"))

    def test_at_threshold_requires_approval(self) -> None:
        self.assertTrue(needs_approval(25_000.0, "medium"))

    def test_above_threshold_requires_approval(self) -> None:
        self.assertTrue(needs_approval(30_000.0, "medium"))

    def test_low_risk_tolerance_lower_threshold(self) -> None:
        # low risk: 80% of $25k = $20k threshold
        self.assertFalse(needs_approval(19_999.0, "low"))
        self.assertTrue(needs_approval(20_000.0, "low"))

    def test_high_risk_tolerance_higher_threshold(self) -> None:
        # high risk: 150% of $25k = $37.5k threshold
        self.assertFalse(needs_approval(37_499.0, "high"))
        self.assertTrue(needs_approval(37_500.0, "high"))


class TestWorkflowPauseResume(unittest.TestCase):
    def _make_engine(self, tmp_dir: str) -> ReplenishmentWorkflowEngine:
        store = LocalJsonWorkflowStateStore(state_dir=tmp_dir)
        audit = AuditLogger(state_dir=tmp_dir)
        return ReplenishmentWorkflowEngine(store=store, audit=audit)

    def test_low_value_order_completes_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            state = engine.create_workflow("prod-001", requester="alice", risk_tolerance="medium")
            # $100 total (1 unit × $100) — well below $25k threshold
            state = engine.compute_recommendation(state.workflow_id, current_stock=90, reorder_point=100, estimated_unit_cost_usd=100.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)
            self.assertEqual(state.status, WorkflowStatus.COMPLETED)
            self.assertFalse(state.approval_required)
            self.assertNotEqual(state.order_id, "")

    def test_high_value_order_pauses_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            state = engine.create_workflow("prod-002", requester="bob", risk_tolerance="medium")
            # 300 units × $200 = $60k — above $25k threshold
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)
            self.assertEqual(state.status, WorkflowStatus.PAUSED_FOR_APPROVAL)
            self.assertTrue(state.approval_required)
            self.assertIsNotNone(state.approval_requested_at)

    def test_approve_and_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            state = engine.create_workflow("prod-003", requester="carol", risk_tolerance="medium")
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)
            self.assertEqual(state.status, WorkflowStatus.PAUSED_FOR_APPROVAL)

            decision = ApprovalDecision(
                workflow_id=state.workflow_id,
                approver="manager",
                decision=ApprovalStatus.APPROVED,
                notes="Approved for Q2",
            )
            engine.apply_approval(state.workflow_id, decision)
            final = engine.finalize(state.workflow_id)
            self.assertEqual(final.status, WorkflowStatus.COMPLETED)
            self.assertEqual(final.approver, "manager")
            self.assertTrue(final.order_id.startswith("po-"))

    def test_rejection_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            state = engine.create_workflow("prod-004", requester="dave", risk_tolerance="medium")
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)

            decision = ApprovalDecision(
                workflow_id=state.workflow_id,
                approver="manager",
                decision=ApprovalStatus.REJECTED,
                notes="Budget frozen",
            )
            final = engine.apply_approval(state.workflow_id, decision)
            self.assertEqual(final.status, WorkflowStatus.REJECTED)
            self.assertEqual(final.approval_notes, "Budget frozen")

    def test_revision_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            state = engine.create_workflow("prod-005", requester="eve", risk_tolerance="medium")
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)

            revised = engine.request_revision(state.workflow_id, "Reduce quantity to 100 units max")
            self.assertEqual(revised.status, WorkflowStatus.REVISION_REQUIRED)
            self.assertIn("100 units", revised.revision_notes)


class TestEscalationLogic(unittest.TestCase):
    def _make_engine(self, tmp_dir: str) -> ReplenishmentWorkflowEngine:
        store = LocalJsonWorkflowStateStore(state_dir=tmp_dir)
        audit = AuditLogger(state_dir=tmp_dir)
        return ReplenishmentWorkflowEngine(store=store, audit=audit)

    def test_escalation_when_overdue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            policy = EscalationPolicy(approval_timeout_hours=1.0, max_escalations=2)
            state = engine.create_workflow("prod-006", escalation_policy=policy)
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)
            self.assertEqual(state.status, WorkflowStatus.PAUSED_FOR_APPROVAL)

            overdue_time = datetime.now(UTC) + timedelta(hours=2)
            escalated = engine.check_escalation(state.workflow_id, now=overdue_time)
            self.assertEqual(escalated.status, WorkflowStatus.ESCALATED)
            self.assertEqual(escalated.escalation_count, 1)

    def test_auto_reject_after_max_escalations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            policy = EscalationPolicy(approval_timeout_hours=1.0, max_escalations=1, auto_reject_after_escalations=True)
            state = engine.create_workflow("prod-007", escalation_policy=policy)
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            state = engine.advance(state.workflow_id)

            overdue = datetime.now(UTC) + timedelta(hours=2)
            # First escalation
            state = engine.check_escalation(state.workflow_id, now=overdue)
            self.assertEqual(state.status, WorkflowStatus.ESCALATED)

            # Reset to paused for second check (simulate re-pausing)
            raw_state = engine._store.load(state.workflow_id)
            assert raw_state is not None
            raw_state.status = WorkflowStatus.PAUSED_FOR_APPROVAL
            raw_state.approval_requested_at = datetime.now(UTC) - timedelta(hours=2)
            engine._store.save(raw_state)

            final = engine.check_escalation(state.workflow_id, now=overdue)
            self.assertEqual(final.status, WorkflowStatus.TIMED_OUT)


class TestCorruptedStateHandling(unittest.TestCase):
    def test_corrupted_json_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJsonWorkflowStateStore(state_dir=tmp)
            path = Path(tmp) / "wf-corrupted.json"
            path.write_text("{invalid json", encoding="utf-8")
            result = store.load("wf-corrupted")
            self.assertIsNone(result)

    def test_missing_workflow_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = ReplenishmentWorkflowEngine(store=LocalJsonWorkflowStateStore(state_dir=tmp))
            with self.assertRaises(KeyError):
                engine.get_status("wf-nonexistent")


class TestAuditLogReplay(unittest.TestCase):
    def test_replay_produces_correct_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJsonWorkflowStateStore(state_dir=tmp)
            audit = AuditLogger(state_dir=tmp)
            engine = ReplenishmentWorkflowEngine(store=store, audit=audit)

            state = engine.create_workflow("prod-010", requester="replay-test", risk_tolerance="medium")
            state = engine.compute_recommendation(state.workflow_id, current_stock=0, reorder_point=300, estimated_unit_cost_usd=200.0)
            state = engine.propose_order(state.workflow_id)
            engine.advance(state.workflow_id)

            events = audit.read_all(state.workflow_id)
            self.assertGreater(len(events), 0)

            summary = reconstruct_state_from_events(events)
            self.assertEqual(summary["workflow_id"], state.workflow_id)
            self.assertIn("PAUSED_FOR_APPROVAL", summary["status"])
            self.assertGreater(len(summary["timeline"]), 0)

    def test_timeline_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJsonWorkflowStateStore(state_dir=tmp)
            audit = AuditLogger(state_dir=tmp)
            engine = ReplenishmentWorkflowEngine(store=store, audit=audit)
            state = engine.create_workflow("prod-011", requester="alice")
            engine.compute_recommendation(state.workflow_id, current_stock=90, reorder_point=100, estimated_unit_cost_usd=10.0)
            engine.propose_order(state.workflow_id)
            engine.advance(state.workflow_id)

            timeline = audit.render_timeline(state.workflow_id)
            self.assertTrue(any("CREATED" in line for line in timeline))
            self.assertTrue(any("COMPLETED" in line for line in timeline))


if __name__ == "__main__":
    unittest.main()
