"""Release scorecard builder for the RetailOps evaluation framework.

Aggregates pass/fail results from all eval suites into a single artifact.
Supports regression detection against a prior run.

Status: runnable-now

Output: eval/results/scorecard_{timestamp}.json
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger("retailops.observability.scorecard")

_RESULTS_DIR = Path("eval/results")
_REGRESSION_DELTA = -0.05
_IMPROVEMENT_DELTA = 0.02


class EvalSuiteResult:
    """Results for a single eval suite."""

    def __init__(self, suite_name: str) -> None:
        self.suite_name = suite_name
        self.cases: list[dict[str, Any]] = []
        self.started_at = datetime.now(UTC)

    def add_case(
        self,
        case_id: str,
        passed: bool,
        latency_ms: float,
        failure_category: str = "",
        details: str = "",
    ) -> None:
        self.cases.append(
            {
                "case_id": case_id,
                "passed": passed,
                "latency_ms": latency_ms,
                "failure_category": failure_category if not passed else "",
                "details": details,
            }
        )

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.cases if c["passed"])

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.cases if not c["passed"])

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return self.pass_count / len(self.cases)

    @property
    def latencies(self) -> list[float]:
        return [c["latency_ms"] for c in self.cases]

    @property
    def p50_ms(self) -> float:
        return _percentile(self.latencies, 50)

    @property
    def p95_ms(self) -> float:
        return _percentile(self.latencies, 95)

    @property
    def failure_categories(self) -> dict[str, int]:
        cats: dict[str, int] = {}
        for c in self.cases:
            cat = c.get("failure_category", "")
            if cat:
                cats[cat] = cats.get(cat, 0) + 1
        return cats

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total_cases": len(self.cases),
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "pass_rate": round(self.pass_rate, 4),
            "p50_latency_ms": self.p50_ms,
            "p95_latency_ms": self.p95_ms,
            "top_failure_categories": self.failure_categories,
            "cases": self.cases,
        }


class ReleaseScorecard:
    """Aggregates multiple EvalSuiteResults into a single scorecard artifact."""

    def __init__(self, release_tag: str = "") -> None:
        self.release_tag = release_tag or "unreleased"
        self.suites: list[EvalSuiteResult] = []
        self.generated_at = datetime.now(UTC)

    def add_suite(self, suite: EvalSuiteResult) -> None:
        self.suites.append(suite)

    @property
    def overall_pass_rate(self) -> float:
        total = sum(len(s.cases) for s in self.suites)
        if total == 0:
            return 0.0
        passed = sum(s.pass_count for s in self.suites)
        return passed / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_tag": self.release_tag,
            "generated_at": self.generated_at.isoformat(),
            "overall_pass_rate": round(self.overall_pass_rate, 4),
            "suite_count": len(self.suites),
            "total_cases": sum(len(s.cases) for s in self.suites),
            "suites": [s.to_dict() for s in self.suites],
        }

    def save(self, output_dir: Path | None = None) -> Path:
        """Save scorecard as JSON to eval/results/."""
        out_dir = output_dir or _RESULTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = self.generated_at.strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"scorecard_{ts}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        _log.info("Scorecard saved to %s (overall_pass_rate=%.1f%%)", path, self.overall_pass_rate * 100)
        return path

    def compare_with_prior(self, prior_path: Path | None = None) -> dict[str, Any]:
        """Compare this scorecard with the most recent prior run (if available)."""
        results_dir = _RESULTS_DIR
        if prior_path is None:
            candidates = sorted(results_dir.glob("scorecard_*.json"))
            if not candidates:
                return {"status": "no_prior_run"}
            prior_path = candidates[-1]

        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "prior_run_unreadable", "path": str(prior_path)}

        prior_rate = prior.get("overall_pass_rate", 0.0)
        current_rate = self.overall_pass_rate
        delta = round(current_rate - prior_rate, 4)

        return {
            "status": "regression"
            if delta < _REGRESSION_DELTA
            else ("improvement" if delta > _IMPROVEMENT_DELTA else "stable"),
            "prior_pass_rate": prior_rate,
            "current_pass_rate": round(current_rate, 4),
            "delta": delta,
            "prior_scorecard": str(prior_path),
        }


def _percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * pct / 100) - 1)
    return round(sorted_vals[idx], 1)
