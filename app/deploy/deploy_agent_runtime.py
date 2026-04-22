from __future__ import annotations

import json
import os
from contextlib import chdir
from pathlib import Path

from vertexai import Client, agent_engines, types

from app.agents.retailops_agent import app
from app.deploy.agent_engine_troubleshoot import print_create_failure_hints
from app.tools.config import settings


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_runtime_requirements() -> list[str]:
    req_file = Path(__file__).with_name("runtime.requirements.txt")
    requirements = [
        line.strip()
        for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not requirements:
        raise ValueError(f"No runtime requirements found in {req_file}.")
    return requirements


def _build_env_vars() -> dict[str, str]:
    # `extra_packages` includes `app/` (see create + chdir(repo_root)); runtime
    # must resolve `import app.*` alongside ADK under `/code`.
    repo_root = _repo_root()
    repo_bundle = f"/code/{repo_root.name}"
    pythonpath = f"/code:{repo_bundle}"
    existing = os.environ.get("PYTHONPATH", "").strip()
    if existing:
        pythonpath = f"{pythonpath}:{existing}"

    env_vars = {
        "STAGING_BUCKET": settings.staging_bucket,
        "BQ_DATASET": settings.bq_dataset,
        "BQ_PRODUCTS_TABLE": settings.bq_products_table,
        "BQ_SALES_TABLE": settings.bq_sales_table,
        "CLOUDRUN_TOOL_API_BASE_URL": settings.cloudrun_tool_api_base_url,
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "MEMORY_BANK_ENABLED": str(settings.memory_bank_enabled).lower(),
        "PYTHONPATH": pythonpath,
    }
    if settings.capture_genai_message_content:
        env_vars["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
    # Agent Runtime rejects env vars with unset/empty values.
    return {key: value for key, value in env_vars.items() if value}


def main() -> None:
    if not settings.project_id or not settings.staging_bucket:
        raise ValueError("GOOGLE_CLOUD_PROJECT and STAGING_BUCKET must be set.")

    repo_root = _repo_root()
    client = Client(project=settings.project_id, location=settings.location)

    config = {
        "display_name": settings.deployed_agent_name,
        "requirements": _load_runtime_requirements(),
        "extra_packages": ["app"],
        "staging_bucket": settings.staging_bucket,
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "env_vars": _build_env_vars(),
    }

    print(
        "Starting Agent Engine create (upload + Vertex provisioning; often several minutes). "
        "Do not interrupt unless you intend to abort.",
        flush=True,
    )

    # Agent Identity is mutually exclusive with explicitly setting service_account.
    if settings.runtime_service_account:
        print(
            "Ignoring RUNTIME_SERVICE_ACCOUNT because identity_type is AGENT_IDENTITY.",
            flush=True,
        )

    try:
        with chdir(repo_root):
            print(
                "Packaging extra_packages from repo root; uploading to staging bucket...",
                flush=True,
            )
            remote_app = client.agent_engines.create(
                agent=agent_engines.AdkApp(agent=app.root_agent),
                config=config,
            )
    except RuntimeError as exc:
        print_create_failure_hints(project_id=settings.project_id, exc=exc)
        raise

    print("Agent Engine create finished.", flush=True)
    print(
        json.dumps(
            {
                "name": getattr(remote_app.api_resource, "name", None),
                "display_name": settings.deployed_agent_name,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
