from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from starlette.testclient import TestClient


def _load_tool_api_app():
    repo = Path(__file__).resolve().parents[2]
    path = repo / "cloudrun" / "tool_api" / "main.py"
    spec = importlib.util.spec_from_file_location("tool_api_main", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app


class ToolApiCorrelationMiddlewareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _load_tool_api_app()

    def test_healthz_echoes_incoming_request_id(self) -> None:
        client = TestClient(self._app)
        response = client.get("/healthz", headers={"X-Request-ID": "fixed-test-id"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "fixed-test-id")

    def test_healthz_generates_request_id_when_absent(self) -> None:
        client = TestClient(self._app)
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        rid = response.headers.get("X-Request-ID")
        self.assertIsNotNone(rid)
        self.assertEqual(len(rid), 36)


if __name__ == "__main__":
    unittest.main()
