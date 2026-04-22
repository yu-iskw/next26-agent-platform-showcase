"""Tests for the A2A federation provider, mock agents, and routing."""
from __future__ import annotations

import unittest

from app.a2a.agent_card import build_retailops_agent_card
from app.a2a.clients.finance_agent_client import request_finance_approval
from app.a2a.clients.supplier_agent_client import get_supplier_quote
from app.a2a.mock_external_agents import MockFinanceApprovalAgent, MockSupplierNegotiationAgent
from app.a2a.models import A2ATaskRequest, A2ATaskStatus
from app.a2a.provider import A2AProvider


class TestAgentCard(unittest.TestCase):
    def test_card_has_required_fields(self) -> None:
        card = build_retailops_agent_card()
        self.assertEqual(card.agent_id, "retailops-copilot-v1")
        self.assertGreater(len(card.capabilities), 0)
        self.assertGreater(len(card.supported_intents), 0)

    def test_card_serialization(self) -> None:
        card = build_retailops_agent_card()
        data = card.model_dump()
        self.assertIn("agent_id", data)
        self.assertIn("capabilities", data)

    def test_card_has_workflow_capability(self) -> None:
        card = build_retailops_agent_card()
        names = [c.name for c in card.capabilities]
        self.assertIn("replenishment_workflow", names)

    def test_supported_intents_include_workflow(self) -> None:
        card = build_retailops_agent_card()
        self.assertIn("workflow.replenishment.create", card.supported_intents)


class TestMockFinanceAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = MockFinanceApprovalAgent()

    def test_auto_approve_low_value(self) -> None:
        req = A2ATaskRequest(
            intent="finance.order.review",
            payload={"order_id": "po-001", "total_cost_usd": 10000.0},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.status, A2ATaskStatus.COMPLETED)
        self.assertEqual(resp.result["decision"], "APPROVED")

    def test_reject_high_value(self) -> None:
        req = A2ATaskRequest(
            intent="finance.order.review",
            payload={"order_id": "po-002", "total_cost_usd": 75000.0},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.status, A2ATaskStatus.COMPLETED)
        self.assertEqual(resp.result["decision"], "REJECTED")

    def test_vip_always_approved(self) -> None:
        req = A2ATaskRequest(
            intent="finance.order.review",
            payload={"order_id": "po-003", "total_cost_usd": 99999.0, "requester": "vip"},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.result["decision"], "APPROVED")

    def test_correlation_id_propagated(self) -> None:
        req = A2ATaskRequest(
            intent="finance.order.review",
            payload={"order_id": "po-004", "total_cost_usd": 1000.0},
            correlation_id="test-corr-123",
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.correlation_id, "test-corr-123")


class TestMockSupplierAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = MockSupplierNegotiationAgent()

    def test_returns_quote(self) -> None:
        req = A2ATaskRequest(
            intent="supplier.quote.request",
            payload={"product_id": "prod-001", "quantity": 10},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.status, A2ATaskStatus.COMPLETED)
        self.assertIn("unit_price_usd", resp.result)
        self.assertIn("total_price_usd", resp.result)

    def test_volume_discount_100_plus(self) -> None:
        req = A2ATaskRequest(
            intent="supplier.quote.request",
            payload={"product_id": "prod-001", "quantity": 100},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.result["discount_pct"], 5.0)

    def test_volume_discount_500_plus(self) -> None:
        req = A2ATaskRequest(
            intent="supplier.quote.request",
            payload={"product_id": "prod-001", "quantity": 500},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.result["discount_pct"], 10.0)

    def test_unknown_product_uses_default_price(self) -> None:
        req = A2ATaskRequest(
            intent="supplier.quote.request",
            payload={"product_id": "prod-unknown", "quantity": 1},
        )
        resp = self.agent.handle(req)
        self.assertEqual(resp.result["unit_price_usd"], 120.0)


class TestA2AProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = A2AProvider(use_mocks=True)

    def test_finance_routing(self) -> None:
        req = A2ATaskRequest(
            intent="finance.order.review",
            payload={"order_id": "po-001", "total_cost_usd": 5000.0},
        )
        resp = self.provider.route(req)
        self.assertEqual(resp.status, A2ATaskStatus.COMPLETED)

    def test_supplier_routing(self) -> None:
        req = A2ATaskRequest(
            intent="supplier.quote.request",
            payload={"product_id": "prod-001", "quantity": 50},
        )
        resp = self.provider.route(req)
        self.assertEqual(resp.status, A2ATaskStatus.COMPLETED)

    def test_unknown_intent_returns_failed(self) -> None:
        req = A2ATaskRequest(intent="unknown.intent", payload={})
        resp = self.provider.route(req)
        self.assertEqual(resp.status, A2ATaskStatus.FAILED)
        self.assertIn("No route found", resp.error)

    def test_list_agents_returns_three(self) -> None:
        agents = self.provider.list_agents()
        self.assertEqual(len(agents), 3)
        ids = [a.agent_id for a in agents]
        self.assertIn("retailops-copilot-v1", ids)
        self.assertIn(MockFinanceApprovalAgent.AGENT_ID, ids)
        self.assertIn(MockSupplierNegotiationAgent.AGENT_ID, ids)

    def test_register_preview_scaffold(self) -> None:
        result = self.provider.register_preview()
        self.assertEqual(result["status"], "preview-scaffold")

    def test_finance_client_wrapper(self) -> None:
        result = request_finance_approval("po-test", 5000.0)
        self.assertIn("result", result)

    def test_supplier_client_wrapper(self) -> None:
        result = get_supplier_quote("prod-001", 50)
        self.assertIn("result", result)

    def test_unavailable_agent_failure(self) -> None:
        req = A2ATaskRequest(intent="finance.order.review", payload={"order_id": "x", "total_cost_usd": 0})
        provider = A2AProvider(use_mocks=True)
        # Override routing to target a non-existent agent
        provider._routing_rules[0].target_agent_id = "nonexistent-agent"
        resp = provider._dispatch(req, "nonexistent-agent")
        self.assertEqual(resp.status, A2ATaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
