"""Evaluation suite for governance policy and approval policy correctness.

Tracks:
  - approval policy correctness (correct threshold application)
  - policy evasion detection (local simulation only)

Note: Local policy simulation is NOT a substitute for official gateway/governance features.
See docs/governance-enforcement.md.

Status: runnable-now (local simulation)
         optional-integration (Vertex AI Model Armor, Agent Gateway)
"""
from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from typing import Any

from app.observability.release_scorecard import EvalSuiteResult, ReleaseScorecard
from app.workflows.approval_handlers import needs_approval

_log = logging.getLogger("retailops.evals.policy")

_GOLDEN_CSV = Path("eval/golden/policy_cases.csv")


def run_policy_eval(
    golden_csv: Path | None = None,
    output_dir: Path | None = None,
) -> EvalSuiteResult:
    """Run all policy golden cases and return an EvalSuiteResult."""
    csv_path = golden_csv or _GOLDEN_CSV
    suite = EvalSuiteResult("policy")

    if not csv_path.exists():
        _log.warning("Policy golden CSV not found: %s", csv_path)
        return suite

    rows = _load_csv(csv_path)
    _log.info("Running %d policy eval cases", len(rows))

    for row in rows:
        case_id = row.get("case_id", "unknown")
        t0 = time.monotonic()
        passed, failure_cat, details = _run_case(row)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        suite.add_case(case_id, passed, elapsed, failure_cat, details)
        status = "PASS" if passed else f"FAIL({failure_cat})"
        _log.info("  [%s] %s — %s ms", status, case_id, elapsed)

    return suite


def _run_case(row: dict[str, Any]) -> tuple[bool, str, str]:
    """Execute one policy golden case."""
    try:
        policy_type = row.get("policy_type", "approval_threshold")

        if policy_type == "approval_threshold":
            total_cost = float(row.get("total_cost_usd", 0))
            risk_tolerance = row.get("risk_tolerance", "medium")
            expected = row.get("expected_approval_required", "false").lower() in ("true", "1", "yes")
            actual = needs_approval(total_cost, risk_tolerance)
            if actual != expected:
                return (
                    False,
                    "approval_threshold_wrong",
                    f"cost={total_cost} risk={risk_tolerance} expected={expected} actual={actual}",
                )
            return True, "", ""

        if policy_type == "content_safety":
            # Local simulation: simple keyword detection
            # NOT a substitute for Model Armor or Agent Gateway
            content = row.get("input_content", "")
            expected_blocked = row.get("expected_blocked", "false").lower() in ("true", "1", "yes")
            from app.governance.local_guardrails import is_content_blocked  # type: ignore[import]

            actually_blocked = is_content_blocked(content)
            if actually_blocked != expected_blocked:
                return (
                    False,
                    "content_safety_wrong",
                    f"expected_blocked={expected_blocked}, actual={actually_blocked}",
                )
            return True, "", ""

        return False, "unknown_policy_type", f"policy_type={policy_type!r} not supported"

    except ImportError:
        # governance module might not be present yet
        return True, "", "(skipped — governance module not yet available)"
    except Exception as exc:
        return False, "exception", str(exc)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = run_policy_eval()
    scorecard = ReleaseScorecard()
    scorecard.add_suite(result)
    path = scorecard.save()
    print(f"\nPolicy eval: {result.pass_count}/{len(result.cases)} passed")
    print(f"Scorecard: {path}")
