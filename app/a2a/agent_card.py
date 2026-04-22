"""Agent card generator for RetailOps.

Generates the machine-readable identity manifest used by A2A federation.

Status: runnable-now (card generation)
         preview-scaffold (Gemini Enterprise registration endpoint)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.a2a.models import A2AAgentCard, A2ACapability


def build_retailops_agent_card(
    endpoint_url: str | None = None,
    provider: str | None = None,
) -> A2AAgentCard:
    """Build the RetailOps agent card.

    Args:
        endpoint_url: The public HTTPS URL where this agent is reachable.
                      Defaults to CLOUDRUN_TOOL_API_BASE_URL env var.
        provider: The provider/org identifier for A2A registration.

    Returns:
        A2AAgentCard ready for serialization and registration.
    """
    base_url = endpoint_url or os.getenv("CLOUDRUN_TOOL_API_BASE_URL", "http://localhost:8080")
    return A2AAgentCard(
        agent_id="retailops-copilot-v1",
        agent_name="RetailOps Copilot",
        description=(
            "Multi-agent retail operations assistant. "
            "Handles inventory queries, sales trend analysis, purchase order creation, "
            "and durable replenishment workflows with human-in-the-loop approval."
        ),
        version="1.0.0",
        provider=provider or os.getenv("A2A_PROVIDER_ID", "retailops-demo-org"),
        endpoint_url=base_url,
        capabilities=[
            A2ACapability(
                name="inventory_query",
                description="Query product inventory levels by name or ID.",
                input_schema={"type": "object", "properties": {"product_name": {"type": "string"}}},
                output_schema={"type": "object"},
            ),
            A2ACapability(
                name="sales_trend_analysis",
                description="Summarize monthly sales trends by product category.",
                input_schema={"type": "object", "properties": {"category": {"type": "string"}}},
                output_schema={"type": "object"},
            ),
            A2ACapability(
                name="reorder_recommendation",
                description="Compute a data-backed reorder recommendation for a product.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "multiplier": {"type": "number"},
                    },
                },
                output_schema={"type": "object"},
            ),
            A2ACapability(
                name="replenishment_workflow",
                description=(
                    "Initiate a durable replenishment workflow with optional human-in-the-loop approval. "
                    "Returns a workflow_id for async tracking."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "current_stock": {"type": "integer"},
                        "reorder_point": {"type": "integer"},
                        "risk_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["product_id"],
                },
                output_schema={"type": "object"},
            ),
            A2ACapability(
                name="purchase_order_status",
                description="Retrieve the status of an existing purchase order or workflow.",
                input_schema={
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                },
                output_schema={"type": "object"},
            ),
        ],
        supported_intents=[
            "inventory.query",
            "analytics.sales_trend",
            "analytics.reorder_recommendation",
            "order.create",
            "order.status",
            "workflow.replenishment.create",
            "workflow.replenishment.approve",
            "workflow.replenishment.reject",
            "workflow.pending.list",
        ],
        auth_type="bearer",
        metadata={
            "status": "runnable-now",
            "a2a_registration": "preview-scaffold",
            "docs": "https://github.com/yu-iskw/next26-agent-platform-showcase/blob/main/docs/a2a-architecture.md",
        },
    )


def write_agent_card_json(output_path: str | Path | None = None) -> Path:
    """Write the RetailOps agent card JSON to docs/examples/retailops-agent-card.json."""
    path = Path(output_path) if output_path else Path("docs/examples/retailops-agent-card.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    card = build_retailops_agent_card()
    path.write_text(
        json.dumps(card.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    written = write_agent_card_json()
    print(f"Agent card written to: {written}")
