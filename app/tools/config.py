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


settings = Settings()
