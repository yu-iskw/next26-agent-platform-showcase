from __future__ import annotations

import json
import unittest

import pandas as pd

from app.deploy.evaluate_agent import (
    REQUIRED_COLUMNS,
    _build_instance_rows,
    _compute_pr,
    _normalize_step,
)


def _eval_row(**overrides: str | object) -> dict[str, object]:
    row: dict[str, object] = {
        "prompt": "p1",
        "scenario": "s",
        "capability": "c",
        "risk_tier": "low",
        "expected_keywords": "",
        "forbidden_keywords": "",
        "must_mention_approval": "false",
        "requires_tool": "",
        "reference_trajectory": "[]",
    }
    row.update(overrides)
    missing = REQUIRED_COLUMNS - row.keys()
    if missing:
        raise ValueError(f"fixture missing keys: {missing}")
    return row


class BuildInstanceRowsTests(unittest.TestCase):
    def test_keyword_pass_with_expected_keywords(self) -> None:
        merged = pd.DataFrame(
            [
                _eval_row(
                    expected_keywords="refund|policy",
                    response="Our refund policy requires manager approval.",
                )
            ]
        )
        rows = _build_instance_rows(merged)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["keyword_pass"])
        self.assertEqual(rows[0]["forbidden_keyword_hits"], 0)

    def test_keyword_fail_when_forbidden_present(self) -> None:
        merged = pd.DataFrame(
            [
                _eval_row(
                    expected_keywords="help",
                    forbidden_keywords="password",
                    response="Your password is help123.",
                )
            ]
        )
        rows = _build_instance_rows(merged)
        self.assertFalse(rows[0]["keyword_pass"])
        self.assertGreater(rows[0]["forbidden_keyword_hits"], 0)

    def test_must_mention_approval_requires_approval_word(self) -> None:
        merged = pd.DataFrame(
            [
                _eval_row(
                    must_mention_approval="true",
                    response="I will process the refund now.",
                )
            ]
        )
        rows = _build_instance_rows(merged)
        self.assertFalse(rows[0]["keyword_pass"])
        merged_ok = pd.DataFrame(
            [
                _eval_row(
                    must_mention_approval="true",
                    response="Manager approval is required before refund.",
                )
            ]
        )
        rows_ok = _build_instance_rows(merged_ok)
        self.assertTrue(rows_ok[0]["keyword_pass"])
        self.assertTrue(rows_ok[0]["approval_mentioned"])

    def test_trajectory_precision_recall(self) -> None:
        ref = [{"tool_name": "lookup", "tool_input": {"id": "1"}}]
        pred = [{"tool_name": "lookup", "tool_input": {"id": "1"}}]
        merged = pd.DataFrame(
            [
                _eval_row(
                    reference_trajectory=json.dumps(ref),
                    predicted_trajectory=json.dumps(pred),
                    response="done",
                )
            ]
        )
        rows = _build_instance_rows(merged)
        self.assertEqual(rows[0]["trajectory_precision"], 1.0)
        self.assertEqual(rows[0]["trajectory_recall"], 1.0)
        self.assertTrue(rows[0]["trajectory_exact_match"])


class ComputePrTests(unittest.TestCase):
    def test_both_empty_is_perfect(self) -> None:
        p, r, ex = _compute_pr([], [])
        self.assertEqual(p, 1.0)
        self.assertEqual(r, 1.0)
        self.assertTrue(ex)

    def test_partial_overlap(self) -> None:
        pred = ["a", "b"]
        ref = ["b", "c"]
        p, r, ex = _compute_pr(pred, ref)
        self.assertEqual(p, 0.5)
        self.assertEqual(r, 0.5)
        self.assertFalse(ex)


class NormalizeStepTests(unittest.TestCase):
    def test_string_step(self) -> None:
        self.assertEqual(_normalize_step("  Hello "), "hello")

    def test_dict_step_stable_json(self) -> None:
        step = {"tool_name": "fetch", "tool_input": {"z": 1, "a": 2}}
        out = _normalize_step(step)
        self.assertTrue(out.startswith("fetch:"))
        self.assertIn('"a":2', out)
        self.assertIn('"z":1', out)


if __name__ == "__main__":
    unittest.main()
