"""Evaluation suite for the ReplenishmentWorkflowEngine.

Runs structured golden cases from eval/golden/workflow_cases.csv.
Tracks:
  - workflow completion correctness
  - approval policy correctness
  - latency buckets
  - error rate

Status: runnable-now
"""
from __future__ import annotations

import csv
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from app.observability.release_scorecard import EvalSuiteResult, ReleaseScorecard
from app.workflows.order_replenishment import ReplenishmentWorkflowEngine
from app.workflows.state_models import ApprovalDecision, ApprovalStatus, WorkflowStatus
from app.workflows.state_store import LocalJsonWorkflowStateStore

_log = logging.getLogger("retailops.evals.workflow")

_GOLDEN_CSV = Path("eval/golden/workflow_cases.csv")


def _parse_bool(v: str) -> bool:
    return v.strip().lower() in ("true", "1", "yes")


def run_workflow_eval(
    golden_csv: Path | None = None,
    output_dir: Path | None = None,
) -> EvalSuiteResult:
    """Run all workflow golden cases and return an EvalSuiteResult."""
    csv_path = golden_csv or _GOLDEN_CSV
    suite = EvalSuiteResult("workflow")

    if not csv_path.exists():
        _log.warning("Workflow golden CSV not found: %s", csv_path)
        return suite

    rows = _load_csv(csv_path)
    _log.info("Running %d workflow eval cases from %s", len(rows), csv_path)

    with tempfile.TemporaryDirectory() as tmp:
        for row in rows:
            case_id = row.get("case_id", "unknown")
            t0 = time.monotonic()
            passed, failure_cat, details = _run_case(row, tmp)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            suite.add_case(case_id, passed, elapsed, failure_cat, details)
            status = "PASS" if passed else f"FAIL({failure_cat})"
            _log.info("  [%s] %s — %s ms", status, case_id, elapsed)

    return suite


def _run_case(row: dict[str, Any], tmp_dir: str) -> tuple[bool, str, str]:
    """Execute one golden case. Returns (passed, failure_category, details)."""
    try:
        store = LocalJsonWorkflowStateStore(state_dir=tmp_dir)
        engine = ReplenishmentWorkflowEngine(store=store)

        product_id = row.get("product_id", "prod-eval")
        risk_tolerance = row.get("risk_tolerance", "medium")
        current_stock = int(row.get("current_stock", 0))
        reorder_point = int(row.get("reorder_point", 100))
        unit_cost = float(row.get("unit_cost_usd", 120.0))
        expected_status = row.get("expected_status", "COMPLETED")
        expect_approval = _parse_bool(row.get("expect_approval_required", "false"))
        auto_approve = _parse_bool(row.get("auto_approve", "false"))

        state = engine.create_workflow(product_id=product_id, risk_tolerance=risk_tolerance)
        state = engine.compute_recommendation(state.workflow_id, current_stock, reorder_point, unit_cost)
        state = engine.propose_order(state.workflow_id)
        state = engine.advance(state.workflow_id)

        if state.approval_required != expect_approval:
            return (
                False,
                "approval_policy",
                f"expected approval_required={expect_approval}, got {state.approval_required}",
            )

        if auto_approve and state.status == WorkflowStatus.PAUSED_FOR_APPROVAL:
            decision = ApprovalDecision(
                workflow_id=state.workflow_id,
                approver="eval-auto-approver",
                decision=ApprovalStatus.APPROVED,
                notes="Auto-approved by eval harness",
            )
            engine.apply_approval(state.workflow_id, decision)
            state = engine.finalize(state.workflow_id)

        actual_status = state.status.value
        if actual_status != expected_status:
            return (
                False,
                "wrong_terminal_status",
                f"expected={expected_status}, got={actual_status}",
            )

        return True, "", ""

    except Exception as exc:
        return False, "exception", str(exc)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = run_workflow_eval()
    scorecard = ReleaseScorecard()
    scorecard.add_suite(result)
    path = scorecard.save()
    print(f"\nWorkflow eval: {result.pass_count}/{len(result.cases)} passed")
    print(f"Scorecard: {path}")
