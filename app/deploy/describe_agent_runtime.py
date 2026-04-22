# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false, reportAssignmentType=false
from __future__ import annotations

import json
import os
import sys
from typing import Any

from google.api_core import exceptions as google_exceptions
from vertexai import Client

from app.tools.config import settings


def _reasoning_engine_to_json(api_resource: Any) -> dict[str, Any]:
    dump = getattr(api_resource, "model_dump", None)
    if callable(dump):
        raw = dump(mode="json")
        if isinstance(raw, dict):
            return raw
    name = getattr(api_resource, "name", None)
    display_name = getattr(api_resource, "display_name", None)
    return {"name": name, "display_name": display_name, "repr": repr(api_resource)}


def main() -> None:
    if not settings.project_id:
        print("Set GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        sys.exit(1)

    client = Client(project=settings.project_id, location=settings.location)
    resource = os.environ.get("DEPLOYED_AGENT_RESOURCE_NAME", "").strip()

    if resource:
        try:
            agent = client.agent_engines.get(name=resource)
        except google_exceptions.NotFound:
            print(
                json.dumps(
                    {"error": "not_found", "resource": resource},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            sys.exit(1)
        payload = {
            "source": "get",
            "resource_name": resource,
            "reasoning_engine": _reasoning_engine_to_json(agent.api_resource),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    matches: list[dict[str, Any]] = []
    for eng in client.agent_engines.list():
        res = eng.api_resource
        if res is None:
            continue
        if getattr(res, "display_name", None) == settings.deployed_agent_name:
            row = _reasoning_engine_to_json(res)
            matches.append(row)

    print(
        json.dumps(
            {
                "source": "list_by_display_name",
                "display_name": settings.deployed_agent_name,
                "match_count": len(matches),
                "matches": matches,
                "hint": ("Set DEPLOYED_AGENT_RESOURCE_NAME for a single-resource describe or eval runs."),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
