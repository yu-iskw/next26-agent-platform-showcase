#!/usr/bin/env python3
"""Print a Cloud Logging URL for a Vertex Reasoning Engine / Agent Engine instance.

Usage:
  GOOGLE_CLOUD_PROJECT=my-proj python scripts/print_reasoning_engine_logs_url.py 3331599946754293760

Requires a numeric reasoning engine id (from create error text or Console).
"""

from __future__ import annotations

import argparse
import os
import sys

from app.deploy.agent_engine_troubleshoot import logs_explorer_url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reasoning_engine_id",
        help="Numeric id from .../reasoningEngines/<id> in error or resource name",
    )
    args = parser.parse_args()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        print("Set GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        sys.exit(1)
    print(logs_explorer_url(project_id=project_id, reasoning_engine_id=args.reasoning_engine_id))


if __name__ == "__main__":
    main()
