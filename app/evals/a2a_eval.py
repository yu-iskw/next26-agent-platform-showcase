"""Evaluation suite for A2A federation routing and mock external agents.

Tracks:
  - delegation correctness (right agent for each intent)
  - failure path handling (unavailable agents)
  - correlation ID propagation

Status: runnable-now (mock mode, no network required)
"""
from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from typing import Any

from app.a2a.models import A2ATaskRequest, A2ATaskStatus
from app.a2a.provider import A2AProvider
from app.observability.release_scorecard import EvalSuiteResult, ReleaseScorecard

_log = logging.getLogger("retailops.evals.a2a")

_GOLDEN_CSV = Path("eval/golden/a2a_cases.csv")


def run_a2a_eval(
    golden_csv: Path | None = None,
    output_dir: Path | None = None,
) -> EvalSuiteResult:
    """Run all A2A golden cases and return an EvalSuiteResult."""
    csv_path = golden_csv or _GOLDEN_CSV
    suite = EvalSuiteResult("a2a")

    if not csv_path.exists():
        _log.warning("A2A golden CSV not found: %s", csv_path)
        return suite

    provider = A2AProvider(use_mocks=True)
    rows = _load_csv(csv_path)
    _log.info("Running %d A2A eval cases", len(rows))

    for row in rows:
        case_id = row.get("case_id", "unknown")
        t0 = time.monotonic()
        passed, failure_cat, details = _run_case(row, provider)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        suite.add_case(case_id, passed, elapsed, failure_cat, details)
        status = "PASS" if passed else f"FAIL({failure_cat})"
        _log.info("  [%s] %s — %s ms", status, case_id, elapsed)

    return suite


def _run_case(row: dict[str, Any], provider: A2AProvider) -> tuple[bool, str, str]:
    """Execute one A2A golden case."""
    try:
        intent = row.get("intent", "")
        payload_str = row.get("payload", "{}")
        import json

        payload = json.loads(payload_str) if payload_str else {}
        expected_status = row.get("expected_status", "completed")
        check_corr_id = row.get("check_correlation_id", "true").lower() in ("true", "1", "yes")

        req = A2ATaskRequest(intent=intent, payload=payload, correlation_id="eval-corr-001")
        resp = provider.route(req)

        if resp.status.value != expected_status:
            return False, "wrong_status", f"expected={expected_status}, got={resp.status.value}"

        if check_corr_id and resp.correlation_id != req.correlation_id:
            return False, "correlation_id_lost", f"expected={req.correlation_id}, got={resp.correlation_id}"

        return True, "", ""

    except Exception as exc:
        return False, "exception", str(exc)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = run_a2a_eval()
    scorecard = ReleaseScorecard()
    scorecard.add_suite(result)
    path = scorecard.save()
    print(f"\nA2A eval: {result.pass_count}/{len(result.cases)} passed")
    print(f"Scorecard: {path}")
