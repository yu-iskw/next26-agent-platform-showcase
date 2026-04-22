from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.deploy.export_requirements import (
    TARGET_TO_REQUIREMENTS,
    resolve_target,
    write_requirements,
)


class ExportRequirementsTests(unittest.TestCase):
    def test_resolve_target_returns_known_mapping(self) -> None:
        output_path, content = resolve_target("agent-runtime")
        self.assertEqual(output_path, Path("app/deploy/runtime.requirements.txt"))
        self.assertIn("cloud" + "pickle>=3.1.0\n", content)
        self.assertIn("google-auth>=2.29.0\n", content)
        self.assertIn("pydantic>=2.9.0\n", content)
        self.assertTrue(content.endswith("\n"))

    def test_resolve_target_rejects_unknown_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown target"):
            resolve_target("missing-target")

    def test_write_requirements_writes_exact_content(self) -> None:
        expected_content = TARGET_TO_REQUIREMENTS["tool-api"][1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "requirements.txt"
            write_requirements(output_path, expected_content)
            self.assertEqual(output_path.read_text(encoding="utf-8"), expected_content)


if __name__ == "__main__":
    unittest.main()
