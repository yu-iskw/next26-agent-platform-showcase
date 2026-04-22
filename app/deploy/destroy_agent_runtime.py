# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false, reportAssignmentType=false
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from google.api_core import exceptions as google_exceptions
from vertexai import Client

from app.tools.config import settings


def _parse_force_delete() -> bool:
    raw = os.getenv("AGENT_ENGINE_DELETE_FORCE", "").strip().lower()
    return raw in {"1", "true", "yes", "y", "t"}


def _operation_done(operation: Any) -> bool:
    return bool(getattr(operation, "done", None))


def _operation_error(operation: Any) -> Any:
    return getattr(operation, "error", None)


def _poll_delete_operation(client: Client, initial_operation: Any, *, poll_interval_seconds: float = 5.0) -> Any:
    """Poll until delete LRO completes (SDK has no public operation waiter)."""
    engines = client.agent_engines
    operation = initial_operation
    get_op = getattr(engines, "_get_agent_operation", None)
    if get_op is None:
        raise RuntimeError("Vertex SDK AgentEngines missing _get_agent_operation.")

    while not _operation_done(operation):
        time.sleep(poll_interval_seconds)
        name = getattr(operation, "name", None)
        if not name:
            raise RuntimeError("Delete operation missing name; cannot poll.")
        operation = get_op(operation_name=name)

    err = _operation_error(operation)
    if err:
        raise RuntimeError(f"Agent Engine delete failed: {err}")
    return operation


def main() -> None:
    resource = os.environ.get("DEPLOYED_AGENT_RESOURCE_NAME", "").strip()
    if not resource:
        print(
            "Set DEPLOYED_AGENT_RESOURCE_NAME to the Agent Runtime resource name.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not settings.project_id:
        print("Set GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        sys.exit(1)

    client = Client(project=settings.project_id, location=settings.location)
    force = _parse_force_delete()

    try:
        operation = client.agent_engines.delete(name=resource, force=force)
    except google_exceptions.NotFound:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "not_found",
                    "resource": resource,
                },
                indent=2,
            )
        )
        return

    final = _poll_delete_operation(client, operation)
    print(
        json.dumps(
            {
                "status": "completed",
                "resource": resource,
                "operation": getattr(final, "name", None),
                "force": force,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
