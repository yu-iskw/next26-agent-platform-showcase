"""Mock external agents for local A2A federation demo.

Provides deterministic, network-free implementations of:
  - Finance Approval Agent  (approves/rejects high-value orders)
  - Supplier Negotiation Agent  (queries mock supplier pricing)

These are local stand-ins for real external agents that would be registered
via Gemini Enterprise A2A in a preview/GA environment.

Status: runnable-now (local mock mode)

WARNING: These are demo mocks, not production agents.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.a2a.models import A2AAgentCard, A2ACapability, A2ATaskRequest, A2ATaskResponse, A2ATaskStatus

_log = logging.getLogger("retailops.a2a.mocks")


class MockFinanceApprovalAgent:
    """Simulates a Finance department approval agent.

    Decision logic (deterministic for demo):
      - total_cost_usd < $50 000 → auto-approved
      - total_cost_usd >= $50 000 → requires escalation (rejected in mock)
      - requester == "vip" → always approved
    """

    AGENT_ID = "finance-approval-agent-mock"

    def get_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.AGENT_ID,
            agent_name="Finance Approval Agent (Mock)",
            description="Reviews and approves high-value purchase orders on behalf of the Finance team.",
            provider="finance-dept-mock",
            endpoint_url="http://localhost:9001",
            capabilities=[
                A2ACapability(
                    name="review_order",
                    description="Review a purchase order and return an approve/reject decision.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "total_cost_usd": {"type": "number"},
                            "requester": {"type": "string"},
                        },
                        "required": ["order_id", "total_cost_usd"],
                    },
                )
            ],
            supported_intents=["finance.order.review", "finance.order.approve"],
            metadata={"status": "mock", "note": "Replace with real Finance A2A endpoint in production."},
        )

    def handle(self, request: A2ATaskRequest) -> A2ATaskResponse:
        order_id = request.payload.get("order_id", "unknown")
        total_cost = float(request.payload.get("total_cost_usd", 0))
        requester = request.payload.get("requester", "")

        _log.info("[MockFinanceAgent] Reviewing order %s ($%.2f)", order_id, total_cost)

        if requester == "vip" or total_cost < 50_000:
            decision = "APPROVED"
            rationale = f"Order ${total_cost:,.2f} within auto-approval limits."
        else:
            decision = "REJECTED"
            rationale = f"Order ${total_cost:,.2f} exceeds Finance auto-approval limit ($50,000). Manual review required."

        return A2ATaskResponse(
            task_id=request.task_id,
            status=A2ATaskStatus.COMPLETED,
            result={
                "order_id": order_id,
                "decision": decision,
                "rationale": rationale,
                "reviewed_by": self.AGENT_ID,
                "reviewed_at": datetime.now(UTC).isoformat(),
            },
            correlation_id=request.correlation_id,
            responding_agent_id=self.AGENT_ID,
        )


class MockSupplierNegotiationAgent:
    """Simulates a Supplier procurement agent that returns pricing quotes.

    Returns deterministic mock quotes based on product_id and quantity.

    Status: runnable-now (mock data)
    """

    AGENT_ID = "supplier-negotiation-agent-mock"

    _BASE_PRICES: dict[str, float] = {
        "prod-001": 95.0,
        "prod-002": 210.0,
        "prod-003": 45.0,
        "prod-004": 12.0,
        "prod-005": 85.0,
        "prod-006": 130.0,
    }
    _DEFAULT_PRICE = 120.0

    def get_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.AGENT_ID,
            agent_name="Supplier Negotiation Agent (Mock)",
            description="Queries supplier catalogs and negotiates bulk pricing for replenishment orders.",
            provider="procurement-mock",
            endpoint_url="http://localhost:9002",
            capabilities=[
                A2ACapability(
                    name="get_supplier_quote",
                    description="Return a unit price quote for a product and quantity.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["product_id", "quantity"],
                    },
                )
            ],
            supported_intents=["supplier.quote.request", "supplier.catalog.query"],
            metadata={"status": "mock", "note": "Replace with real Supplier A2A endpoint in production."},
        )

    def handle(self, request: A2ATaskRequest) -> A2ATaskResponse:
        product_id = request.payload.get("product_id", "unknown")
        quantity = int(request.payload.get("quantity", 1))

        base_price = self._BASE_PRICES.get(product_id, self._DEFAULT_PRICE)
        # Volume discount: 5% off for 100+ units, 10% off for 500+ units
        if quantity >= 500:
            discount = 0.10
        elif quantity >= 100:
            discount = 0.05
        else:
            discount = 0.0

        unit_price = round(base_price * (1 - discount), 2)
        total = round(unit_price * quantity, 2)

        _log.info("[MockSupplierAgent] Quote for %s ×%d: $%.2f/unit = $%.2f", product_id, quantity, unit_price, total)

        return A2ATaskResponse(
            task_id=request.task_id,
            status=A2ATaskStatus.COMPLETED,
            result={
                "product_id": product_id,
                "quantity": quantity,
                "unit_price_usd": unit_price,
                "total_price_usd": total,
                "discount_pct": discount * 100,
                "supplier": "GlobalSupply-Mock",
                "quoted_at": datetime.now(UTC).isoformat(),
                "valid_for_hours": 24,
            },
            correlation_id=request.correlation_id,
            responding_agent_id=self.AGENT_ID,
        )
