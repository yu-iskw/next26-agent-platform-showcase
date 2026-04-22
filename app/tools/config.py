from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    staging_bucket: str = os.getenv("STAGING_BUCKET", "")
    bq_dataset: str = os.getenv("BQ_DATASET", "retailops_demo")
    bq_products_table: str = os.getenv("BQ_PRODUCTS_TABLE", "products")
    bq_sales_table: str = os.getenv("BQ_SALES_TABLE", "sales")
    cloudrun_tool_api_base_url: str = os.getenv("CLOUDRUN_TOOL_API_BASE_URL", "http://localhost:8080")
    cloudrun_tool_api_skip_id_token: bool = os.getenv("CLOUDRUN_TOOL_API_SKIP_ID_TOKEN", "").lower() in (
        "1",
        "true",
        "yes",
    )
    deployed_agent_name: str = os.getenv("DEPLOYED_AGENT_NAME", "retailops-copilot")
    memory_bank_enabled: bool = os.getenv("MEMORY_BANK_ENABLED", "true").lower() == "true"
    # When true, deploy sets OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT on
    # Agent Runtime (logs prompts/completions; use only where policy allows).
    capture_genai_message_content: bool = os.getenv("CAPTURE_GENAI_MESSAGE_CONTENT", "").lower() in ("1", "true", "yes")
    runtime_service_account: str = os.getenv("RUNTIME_SERVICE_ACCOUNT", "")

    # Workstream A: Workflow state persistence
    workflow_state_backend: str = os.getenv("WORKFLOW_STATE_BACKEND", "local")
    workflow_state_dir: str = os.getenv("WORKFLOW_STATE_DIR", ".local/state")

    # Workstream B: A2A federation (preview-scaffold)
    enable_a2a_experimental: bool = os.getenv("ENABLE_A2A_EXPERIMENTAL", "").lower() in ("1", "true", "yes")
    a2a_provider_id: str = os.getenv("A2A_PROVIDER_ID", "retailops-demo-org")
    a2a_use_mocks: bool = os.getenv("A2A_USE_MOCKS", "true").lower() in ("1", "true", "yes")

    # Workstream C: Remote MCP
    remote_mcp_skip_auth: bool = os.getenv("REMOTE_MCP_SKIP_AUTH", "").lower() in ("1", "true", "yes")

    # Workstream E: Workspace connectors (optional-integration)
    enable_workspace_connectors: bool = os.getenv("ENABLE_WORKSPACE_CONNECTORS", "").lower() in ("1", "true", "yes")


settings = Settings()
