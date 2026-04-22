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
    description="Creates purchase orders and approval requests.",
    instruction=(
        "You handle replenishment orders. "
        "First use recommend_reorder externally through the parent or prior context if needed. "
        "If a proposed order is high-value or the returned tool result indicates approval_required=true, "
        "submit an approval request after creating the order and explain that execution is pending approval."
    ),
    tools=[create_purchase_order, submit_approval_request, get_order_status],
)

root_agent = Agent(
    name="retailops_root",
    model=MODEL,
    description="Routes user requests across retail operations specialists.",
    instruction=(
        "You are RetailOps Copilot, a multi-agent coordinator for retail merchandising and replenishment. "
        "Delegate to the right specialist. "
        "Use analytics_agent for trends and reorder logic, knowledge_agent for inventory and docs, "
        "and order_agent for operational execution. "
        "When the user states a lasting preference such as risk tolerance or supplier preference, remember it explicitly in your response "
        "and ask the runtime memory subsystem to persist it when available."
    ),
    sub_agents=[knowledge_agent, analytics_agent, order_agent],
)

workflow = SequentialAgent(
    name="retailops_pipeline",
    sub_agents=[intake_agent, root_agent],
)

app = App(
    name="retailops_showcase",
    root_agent=workflow,
)
