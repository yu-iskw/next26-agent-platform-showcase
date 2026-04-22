"""Helpers for triaging Agent Engine / Reasoning Engine create failures."""

from __future__ import annotations

import re
import sys
from urllib.parse import quote

VERTEX_AGENT_ENGINE_DEPLOY_TROUBLESHOOTING = (
    "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/troubleshooting/deploy"
)


def reasoning_engine_id_from_error(message: str) -> str | None:
    """Parse reasoning engine numeric id from API error text, if present."""
    match = re.search(r"reasoningEngines/(\d+)", message)
    return match.group(1) if match else None


def logs_explorer_url(*, project_id: str, reasoning_engine_id: str) -> str:
    """Same query shape as vertexai `agent_engines.create` progress log line."""
    query = (
        'resource.type="aiplatform.googleapis.com/ReasoningEngine"\n'
        f'resource.labels.reasoning_engine_id="{reasoning_engine_id}"'
    )
    return (
        "https://console.cloud.google.com/logs/query?"
        f"project={quote(project_id, safe='')}"
        f"&query={quote(query, safe='')}"
    )


def print_create_failure_hints(*, project_id: str, exc: BaseException) -> None:
    """Print troubleshooting URLs after `agent_engines.create` fails."""
    text = str(exc)
    engine_id = reasoning_engine_id_from_error(text)
    print(
        "\nAgent Engine create failed. Next steps:\n"
        f"- Troubleshooting guide: {VERTEX_AGENT_ENGINE_DEPLOY_TROUBLESHOOTING}\n",
        file=sys.stderr,
    )
    if engine_id:
        print(
            f"- Cloud Logging (ReasoningEngine id={engine_id}):\n"
            f"  {logs_explorer_url(project_id=project_id, reasoning_engine_id=engine_id)}\n",
            file=sys.stderr,
        )
    else:
        print(
            "- Open Cloud Logging and filter resource type "
            "aiplatform.googleapis.com/ReasoningEngine for this project.\n",
            file=sys.stderr,
        )
