"""A2A provider — routes incoming task requests to the correct external agent.

In local/demo mode all agents are mock implementations.
In preview mode the provider can be registered with Gemini Enterprise A2A.

WARNING: Gemini Enterprise A2A registration is a preview feature.
Enable with ENABLE_A2A_EXPERIMENTAL=true. See docs/a2a-architecture.md.

Status: runnable-now (mock routing)
         preview-scaffold (Gemini Enterprise registration)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.a2a.models import (
    A2AAgentCard,
    A2ARoutingRule,
    A2ATaskRequest,
    A2ATaskResponse,
    A2ATaskStatus,
)
from app.a2a.mock_external_agents import MockFinanceApprovalAgent, MockSupplierNegotiationAgent

_log = logging.getLogger("retailops.a2a.provider")

_A2A_ENABLED = os.getenv("ENABLE_A2A_EXPERIMENTAL", "").lower() in ("1", "true", "yes")


class A2AProvider:
    """Routes A2A task requests to the appropriate agent (mock or real).

    In local mode: all routes delegate to mock implementations.
    In preview mode: routes delegate to registered Gemini Enterprise agents.

    Do NOT add silent fallback from authenticated mode to unauthenticated mode.
    If an agent is unavailable, return a FAILED response with a clear error.
    """

    def __init__(self, use_mocks: bool = True) -> None:
        self._use_mocks = use_mocks
        self._finance_agent = MockFinanceApprovalAgent()
        self._supplier_agent = MockSupplierNegotiationAgent()

        self._routing_rules: list[A2ARoutingRule] = [
            A2ARoutingRule(intent_prefix="finance.", target_agent_id=MockFinanceApprovalAgent.AGENT_ID, priority=10),
            A2ARoutingRule(intent_prefix="supplier.", target_agent_id=MockSupplierNegotiationAgent.AGENT_ID, priority=10),
        ]

    @classmethod
    def from_env(cls) -> "A2AProvider":
        """Create a provider configured from environment variables."""
        use_mocks = not _A2A_ENABLED or os.getenv("A2A_USE_MOCKS", "true").lower() in ("1", "true", "yes")
        provider = cls(use_mocks=use_mocks)
        if not use_mocks:
            _log.warning(
                "A2A experimental mode enabled. "
                "Real external agent registration requires Gemini Enterprise preview access. "
                "See docs/a2a-architecture.md."
            )
        return provider

    def list_agents(self) -> list[A2AAgentCard]:
        """Return cards for all agents known to this provider."""
        from app.a2a.agent_card import build_retailops_agent_card

        return [
            build_retailops_agent_card(),
            self._finance_agent.get_card(),
            self._supplier_agent.get_card(),
        ]

    def route(self, request: A2ATaskRequest) -> A2ATaskResponse:
        """Route a task request to the appropriate agent and return its response.

        Correlation IDs are propagated so requests are traceable across service boundaries.
        """
        if not _A2A_ENABLED and not self._use_mocks:
            return A2ATaskResponse(
                task_id=request.task_id,
                status=A2ATaskStatus.FAILED,
                error="A2A federation is not enabled. Set ENABLE_A2A_EXPERIMENTAL=true.",
                correlation_id=request.correlation_id,
            )

        matched_rule = self._match_rule(request.intent)
        if matched_rule is None:
            _log.warning("No A2A route found for intent=%s", request.intent)
            return A2ATaskResponse(
                task_id=request.task_id,
                status=A2ATaskStatus.FAILED,
                error=f"No route found for intent '{request.intent}'. "
                      f"Supported prefixes: finance., supplier.",
                correlation_id=request.correlation_id,
            )

        _log.info(
            "A2A routing task_id=%s intent=%s → agent=%s correlation_id=%s",
            request.task_id,
            request.intent,
            matched_rule.target_agent_id,
            request.correlation_id,
        )

        return self._dispatch(request, matched_rule.target_agent_id)

    def _match_rule(self, intent: str) -> A2ARoutingRule | None:
        candidates = [r for r in self._routing_rules if intent.startswith(r.intent_prefix) and r.enabled]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.priority)

    def _dispatch(self, request: A2ATaskRequest, agent_id: str) -> A2ATaskResponse:
        if agent_id == MockFinanceApprovalAgent.AGENT_ID:
            return self._finance_agent.handle(request)
        if agent_id == MockSupplierNegotiationAgent.AGENT_ID:
            return self._supplier_agent.handle(request)

        # TODO(preview): dispatch to real Gemini Enterprise A2A endpoint when available
        # Requires: A2A_REGISTRY_URL, authenticated HTTP client, retry logic
        return A2ATaskResponse(
            task_id=request.task_id,
            status=A2ATaskStatus.FAILED,
            error=f"Agent {agent_id!r} is not registered in this provider. "
                  f"This path requires Gemini Enterprise A2A preview access.",
            correlation_id=request.correlation_id,
        )

    def register_preview(self) -> dict[str, Any]:
        """Scaffold for Gemini Enterprise A2A registration.

        This method documents the registration flow but cannot execute it without
        preview access credentials and the A2A registry endpoint.

        See docs/a2a-architecture.md for the registration checklist.
        """
        # TODO(preview): POST to Gemini Enterprise A2A registry when endpoint is available
        return {
            "status": "preview-scaffold",
            "note": (
                "Gemini Enterprise A2A registration requires preview program access. "
                "Contact your Google Cloud representative to join the preview."
            ),
            "required_env_vars": [
                "A2A_REGISTRY_URL",
                "GOOGLE_CLOUD_PROJECT",
                "A2A_PROVIDER_ID",
                "ENABLE_A2A_EXPERIMENTAL=true",
            ],
            "agent_card": "docs/examples/retailops-agent-card.json",
            "docs": "docs/a2a-architecture.md",
        }
