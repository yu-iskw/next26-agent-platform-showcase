from __future__ import annotations

import contextlib
import io
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from app.deploy import agent_engine_troubleshoot, deploy_agent_runtime
from app.deploy.deploy_agent_runtime import _repo_root
from app.tools.config import settings


class DeployAgentRuntimeTests(unittest.TestCase):
    def test_repo_root_contains_app_agents(self) -> None:
        root = _repo_root()
        self.assertTrue((root / "app" / "agents").is_dir())
        self.assertTrue((root / "pyproject.toml").is_file())

    def test_chdir_repo_root_app_is_dir(self) -> None:
        root = _repo_root()
        with contextlib.chdir(root):
            self.assertTrue(Path("app").is_dir())

    def test_build_env_vars_includes_otel_capture_when_enabled(self) -> None:
        fake_settings = replace(
            settings,
            capture_genai_message_content=True,
            staging_bucket="gs://fake-staging",
            cloudrun_tool_api_base_url="https://tool.example.run.app",
        )
        with mock.patch.object(deploy_agent_runtime, "settings", fake_settings):
            env = deploy_agent_runtime._build_env_vars()
        self.assertEqual(
            env.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"),
            "true",
        )

    def test_build_env_vars_omits_otel_capture_when_disabled(self) -> None:
        fake_settings = replace(
            settings,
            capture_genai_message_content=False,
            staging_bucket="gs://fake-staging",
            cloudrun_tool_api_base_url="https://tool.example.run.app",
        )
        with mock.patch.object(deploy_agent_runtime, "settings", fake_settings):
            env = deploy_agent_runtime._build_env_vars()
        self.assertIsNone(env.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"))

    def test_reasoning_engine_id_from_error(self) -> None:
        msg = "Reasoning Engine resource [projects/p/locations/us-central1/reasoningEngines/3331599946754293760] failed"
        self.assertEqual(
            agent_engine_troubleshoot.reasoning_engine_id_from_error(msg),
            "3331599946754293760",
        )
        self.assertIsNone(agent_engine_troubleshoot.reasoning_engine_id_from_error("no id here"))

    def test_logs_explorer_url_contains_project_and_id(self) -> None:
        url = agent_engine_troubleshoot.logs_explorer_url(
            project_id="my-project",
            reasoning_engine_id="42",
        )
        self.assertIn("project=my-project", url)
        self.assertIn("reasoning_engine_id%3D%2242%22", url)
        self.assertIn("ReasoningEngine", url)


class PrintCreateFailureHintsTests(unittest.TestCase):
    def test_print_hints_with_engine_id(self) -> None:
        err = RuntimeError("Failed: reasoningEngines/999] failed")  # still matches numeric part if pattern fits
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            agent_engine_troubleshoot.print_create_failure_hints(project_id="demo-proj", exc=err)
        out = buf.getvalue()
        self.assertIn("Troubleshooting guide", out)
        self.assertIn("demo-proj", out)


if __name__ == "__main__":
    unittest.main()
