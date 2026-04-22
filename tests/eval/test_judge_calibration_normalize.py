from __future__ import annotations

import unittest

from app.deploy.evaluate_judge_calibration import _normalize_winner


class NormalizeWinnerTests(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_normalize_winner(None))

    def test_nan_returns_none(self) -> None:
        self.assertIsNone(_normalize_winner(float("nan")))

    def test_aliases_map_to_canonical(self) -> None:
        for raw, expected in (
            ("LEFT", "a"),
            ("response_a", "a"),
            ("2", "b"),
            ("winner_b", "b"),
            ("draw", "tie"),
            ("0", "tie"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_normalize_winner(raw), expected)

    def test_unknown_string_passthrough_lowercased(self) -> None:
        self.assertEqual(_normalize_winner("Maybe"), "maybe")


if __name__ == "__main__":
    unittest.main()
