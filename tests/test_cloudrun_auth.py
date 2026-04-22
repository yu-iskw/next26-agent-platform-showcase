from __future__ import annotations

import unittest

from app.tools.cloudrun_auth import (
    correlation_headers_for_tool_api,
    should_attach_cloud_run_id_token,
    tool_api_id_token_audience,
)


class TestToolApiIdTokenAudience(unittest.TestCase):
    def test_https_returns_origin(self) -> None:
        self.assertEqual(
            tool_api_id_token_audience("https://svc-abc123-uc.a.run.app/"),
            "https://svc-abc123-uc.a.run.app",
        )

    def test_localhost_returns_none(self) -> None:
        self.assertIsNone(
            tool_api_id_token_audience("http://localhost:8080"),
        )

    def test_loopback_returns_none(self) -> None:
        self.assertIsNone(
            tool_api_id_token_audience("http://127.0.0.1:8080/"),
        )

    def test_non_https_returns_none(self) -> None:
        self.assertIsNone(
            tool_api_id_token_audience("http://example.com"),
        )


class TestCorrelationHeadersForToolApi(unittest.TestCase):
    def test_includes_request_id(self) -> None:
        headers = correlation_headers_for_tool_api()
        self.assertIn("X-Request-ID", headers)
        self.assertEqual(len(headers["X-Request-ID"]), 36)


class TestShouldAttachCloudRunIdToken(unittest.TestCase):
    def test_skip_flag_disables(self) -> None:
        self.assertFalse(should_attach_cloud_run_id_token("https://svc.example.run.app", skip_id_token=True))

    def test_https_without_skip(self) -> None:
        self.assertTrue(should_attach_cloud_run_id_token("https://svc.example.run.app", skip_id_token=False))

    def test_localhost_never_attaches(self) -> None:
        self.assertFalse(should_attach_cloud_run_id_token("http://localhost:8080", skip_id_token=False))


if __name__ == "__main__":
    unittest.main()
