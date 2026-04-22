"""RetailOps Copilot — multi-agent ADK application.

Architecture:
  retailops_pipeline (SequentialAgent)
    └─ intake_agent          (normalises request)
    └─ retailops_root        (orchestrator)
         ├─ knowledge_agent  (inventory + docs)
         ├─ analytics_agent  (trends + reorder)
         ├─ order_agent      (purchase orders — direct Cloud Run path)
         └─ workflow_agent   (durable human-in-the-loop workflows — new)

A2A federation:
  retailops_root also delegates to A2A external agents when
  ENABLE_A2A_EXPERIMENTAL=true (preview-scaffold).
"""

from __future__ import annotations

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.apps import App

from app.tools.analytics_tools import (
    get_product_inventory,
    get_top_products,
    recommend_reorder,
    summarize_sales_trend,
)
from app.tools.commerce_tools import (
    create_purchase_order,
    get_order_status,
    submit_approval_request,
)
from app.tools.storage_tools import (
    list_grounding_documents,
    upload_demo_note,
)
from app.tools.workflow_tools import (
    approve_workflow,
    get_workflow_explanation,
    get_workflow_status,
    list_pending_approvals,
    reject_workflow,
    start_replenishment_workflow,
)

MODEL = "gemini-2.5-flash"


intake_agent = LlmAgent(
    name="intake_agent",
    model=MODEL,
    instruction=(
        "You are the intake specialist for RetailOps Copilot. "
        "Extract the user's task, normalize product names, category names, units, and urgency. "
        "Store a concise plan in state under key intake_plan."
    ),
    output_key="intake_plan",
)

knowledge_agent = Agent(
    name="knowledge_agent",
    model=MODEL,
    description="Answers grounded questions using warehouse facts and stored documents.",
    instruction=(
        "You answer product, inventory, and documentation questions. "
        "Prefer structured tool outputs. If the user asks what documents exist, call list_grounding_documents."
    ),
    tools=[
        get_product_inventory,
        get_top_products,
        list_grounding_documents,
        upload_demo_note,
    ],
)

analytics_agent = Agent(
    name="analytics_agent",
    model=MODEL,
    description="Understands revenue, demand trends, and reorder recommendations.",
    instruction=(
        "You are the analytics specialist. Use BigQuery-backed tools to summarize trends "
        "and make conservative, data-backed recommendations."
    ),
    tools=[get_top_products, summarize_sales_trend, recommend_reorder],
)

order_agent = Agent(
    name="order_agent",
    model=MODEL,
    description="Creates purchase orders and approval requests (direct / single-step path).",
    instruction=(
        "You handle replenishment orders. "
        "First use recommend_reorder externally through the parent or prior context if needed. "
        "If a proposed order is high-value or the returned tool result indicates approval_required=true, "
        "submit an approval request after creating the order and explain that execution is pending approval. "
        "For multi-step, resumable workflows use workflow_agent instead."
    ),
    tools=[create_purchase_order, submit_approval_request, get_order_status],
)

workflow_agent = Agent(
    name="workflow_agent",
    model=MODEL,
    description=(
        "Manages durable, resumable replenishment workflows with human-in-the-loop approval. "
        "Use when the user wants to track a workflow ID, resume a paused order, see pending approvals, "
        "approve or reject a specific workflow, or understand why an order is paused."
    ),
    instruction=(
        "You manage multi-step replenishment workflows that persist across sessions. "
        "Use start_replenishment_workflow to initiate a new durable workflow. "
        "Use list_pending_approvals to show which orders are waiting for human sign-off. "
        "Use get_workflow_status to check a specific workflow by ID. "
        "Use approve_workflow or reject_workflow to act on a paused order. "
        "Use get_workflow_explanation to explain why a workflow is paused or failed. "
        "Always share the workflow_id so the user can reference it later. "
        "When the user states a risk tolerance preference (low/medium/high), use it in start_replenishment_workflow."
    ),
    tools=[
        start_replenishment_workflow,
        get_workflow_status,
        list_pending_approvals,
        approve_workflow,
        reject_workflow,
        get_workflow_explanation,
    ],
)

root_agent = Agent(
    name="retailops_root",
    model=MODEL,
    description="Routes user requests across retail operations specialists.",
    instruction=(
        "You are RetailOps Copilot, a multi-agent coordinator for retail merchandising and replenishment. "
        "Delegate to the right specialist:\n"
        "  • analytics_agent — trends, reorder analysis, demand forecasting\n"
        "  • knowledge_agent — inventory levels, product details, stored documents\n"
        "  • order_agent     — quick/single-step purchase orders and approvals\n"
        "  • workflow_agent  — durable workflows, pending approvals, resume/approve/reject by workflow ID\n\n"
        "When the user states a lasting preference (risk tolerance, supplier preference, etc.), "
        "remember it explicitly in your response and ask the runtime memory subsystem to persist it. "
        "Always surface the workflow_id when a durable workflow is created so the user can reference it."
    ),
    sub_agents=[knowledge_agent, analytics_agent, order_agent, workflow_agent],
)

workflow = SequentialAgent(
    name="retailops_pipeline",
    sub_agents=[intake_agent, root_agent],
)

app = App(
    name="retailops_showcase",
    root_agent=workflow,
)
