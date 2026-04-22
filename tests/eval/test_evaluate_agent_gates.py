from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.deploy.evaluate_agent import (
    REQUIRED_COLUMNS,
    _apply_gates,
    _load_gate_thresholds,
    _validate_schema,
)


class ValidateSchemaTests(unittest.TestCase):
    def test_accepts_all_required_columns(self) -> None:
        columns = {c: [""] for c in REQUIRED_COLUMNS}
        _validate_schema(pd.DataFrame(columns))

    def test_raises_when_column_missing(self) -> None:
        cols = {c: [""] for c in REQUIRED_COLUMNS}
        del cols["scenario"]
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            _validate_schema(pd.DataFrame(cols))


class LoadGateThresholdsTests(unittest.TestCase):
    def test_loads_nested_thresholds_key(self) -> None:
        payload = {"thresholds": {"keyword_pass_rate": 0.85}}  # nosec B105
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gates.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = _load_gate_thresholds(path)
        self.assertEqual(loaded["keyword_pass_rate"], 0.85)  # nosec B105

    def test_missing_file_returns_empty(self) -> None:
        missing = Path("/nonexistent/eval_gate.json")
        self.assertEqual(_load_gate_thresholds(missing), {})


class ApplyGatesTests(unittest.TestCase):
    def test_min_threshold_passes_when_actual_above(self) -> None:
        summary = {"keyword_pass_rate": 0.95}  # nosec B105
        checks, ok = _apply_gates(summary, {"keyword_pass_rate": 0.9})  # nosec B105
        self.assertTrue(ok)
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].passed)
        self.assertEqual(checks[0].actual, 0.95)

    def test_min_threshold_fails_when_actual_below(self) -> None:
        summary = {"keyword_pass_rate": 0.5}  # nosec B105
        checks, ok = _apply_gates(summary, {"keyword_pass_rate": 0.9})  # nosec B105
        self.assertFalse(ok)
        self.assertFalse(checks[0].passed)

    def test_max_threshold_passes_when_actual_below(self) -> None:
        summary = {"failure_rate": 0.05}
        checks, ok = _apply_gates(summary, {"failure_rate_max": 0.1})
        self.assertTrue(ok)
        self.assertTrue(checks[0].passed)

    def test_max_threshold_fails_when_actual_above(self) -> None:
        summary = {"failure_rate": 0.2}
        checks, ok = _apply_gates(summary, {"failure_rate_max": 0.1})
        self.assertFalse(ok)
        self.assertFalse(checks[0].passed)

    def test_empty_thresholds_passes(self) -> None:
        checks, ok = _apply_gates({"keyword_pass_rate": 0.0}, {})  # nosec B105
        self.assertTrue(ok)
        self.assertEqual(checks, [])


if __name__ == "__main__":
    unittest.main()
