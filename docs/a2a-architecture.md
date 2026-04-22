# A2A Federation Architecture

> **⚠️ WARNING: Gemini Enterprise A2A registration is a preview feature.**
> The implementation in this repo provides a clean adapter layer and local mock mode.
> Real agent registration requires preview program access from Google Cloud.
> Contact your Google Cloud representative to join the preview.

**Status:**
- Local mock federation: **runnable-now**
- Gemini Enterprise A2A registration: **preview-scaffold**

---

## Overview

Agent-to-Agent (A2A) federation allows RetailOps Copilot to delegate specialized tasks
to external agents. This repo implements:

1. **Agent Card** — machine-readable identity and capability manifest
2. **A2A Provider** — routes task requests to registered agents
3. **Mock External Agents** — Finance Approval Agent and Supplier Negotiation Agent
4. **Client wrappers** — clean calling interface for agent-callable tools

---

## Architecture

```
RetailOps Copilot (root agent)
        │
        │  delegate via A2AProvider
        │
        ├─── Finance Approval Agent ───[local mock]──► MockFinanceApprovalAgent
        │                              [preview]──────► Gemini Enterprise A2A
        │
        └─── Supplier Negotiation Agent ──[local mock]──► MockSupplierNegotiationAgent
                                          [preview]──────► Gemini Enterprise A2A
```

---

## Agent Card

The RetailOps agent card is at `docs/examples/retailops-agent-card.json`.

Generate/update it:
```bash
make generate-agent-card
```

The card describes:
- Agent identity (`agent_id`, `agent_name`, `version`)
- Capabilities (input/output schemas for each operation)
- Supported intents (routing keys)
- Authentication type (`bearer`)
- Endpoint URL (configurable via `CLOUDRUN_TOOL_API_BASE_URL`)

---

## Routing Rules

| Intent Prefix | Target Agent |
|---|---|
| `finance.*` | Finance Approval Agent |
| `supplier.*` | Supplier Negotiation Agent |

Routing is priority-based. Add new rules in `A2AProvider._routing_rules`.

---

## Local Demo

```bash
ENABLE_A2A_EXPERIMENTAL=false make demo-a2a
```

This runs mock routing without any external calls:
```
Finance decision: APPROVED
Supplier quote: $90.25/unit (discount=5.0%)
```

---

## Preview Registration Path

When Gemini Enterprise A2A preview access is granted:

1. Set `ENABLE_A2A_EXPERIMENTAL=true` in `.env`
2. Set `A2A_REGISTRY_URL=https://<a2a-registry-endpoint>`
3. Set `A2A_PROVIDER_ID=<your-org-id>`
4. Call `A2AProvider.register_preview()` to get the registration checklist
5. POST the agent card JSON to the A2A registry
6. Set `A2A_USE_MOCKS=false` to enable real agent calls

Required IAM roles (preview):
- `roles/aiplatform.user` on the Vertex AI project
- `roles/run.invoker` on any Cloud Run agent endpoints

---

## Security Boundaries

- Feature flag `ENABLE_A2A_EXPERIMENTAL` must be explicitly set to `true`
- There is **no silent fallback** from authenticated mode to mock mode
- Auth boundary stub: `app/a2a/provider.py` → `_dispatch()` method
- All requests carry correlation IDs (`X-Request-ID`, `traceparent`)
- Mock agents are clearly labeled and will not be called in production without the feature flag

---

## File Reference

| File | Description |
|---|---|
| `app/a2a/models.py` | A2A protocol types (agent card, task request/response) |
| `app/a2a/agent_card.py` | Agent card generator for RetailOps |
| `app/a2a/provider.py` | Task router and registration scaffold |
| `app/a2a/mock_external_agents.py` | Finance and Supplier mock agents |
| `app/a2a/clients/finance_agent_client.py` | Finance agent callable |
| `app/a2a/clients/supplier_agent_client.py` | Supplier agent callable |
| `docs/examples/retailops-agent-card.json` | Serialized agent card |
| `tests/a2a/test_a2a_provider.py` | Full test suite |
