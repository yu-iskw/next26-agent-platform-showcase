# Next '26 Platform Roadmap

This document describes the current implementation status and the roadmap for
GA and preview features targeting Google Cloud Next '26.

---

## Implementation Status

### runnable-now

Features that work locally with no cloud dependencies beyond the repo baseline:

| Feature | Module | Notes |
|---|---|---|
| Multi-agent ADK orchestration | `app/agents/retailops_agent.py` | 5 agents: intake, knowledge, analytics, order, workflow |
| Durable workflow engine | `app/workflows/` | Pause/resume, approval, escalation, audit log |
| Local JSON state store | `app/workflows/state_store.py` | File-backed in `.local/state/` |
| Workflow REST API | `cloudrun/tool_api/main.py` | 6 new endpoints + existing 4 |
| Remote MCP server | `cloudrun/remote_mcp/main.py` | HTTP transport, Cloud Run-deployable |
| A2A local mock federation | `app/a2a/` | Finance + Supplier mock agents |
| Agent card generation | `app/a2a/agent_card.py` | `make generate-agent-card` |
| Local governance simulation | `app/governance/local_guardrails.py` | Regex-based (NOT for production) |
| Workspace mock connectors | `app/connectors/` | Drive, Gmail, Calendar mocks |
| Release scorecard | `app/observability/release_scorecard.py` | JSON artifact per eval run |
| Correlation ID propagation | `app/observability/correlation.py` | X-Request-ID + traceparent |
| Workflow eval suite | `app/evals/workflow_eval.py` | 10 golden cases |
| A2A eval suite | `app/evals/a2a_eval.py` | 10 golden cases |
| Policy eval suite | `app/evals/policy_eval.py` | 15 golden cases |
| Governance test pack | `tests/governance/` | Prompt injection + exfiltration cases |

### preview-scaffold

Features implemented as clean adapter boundaries awaiting preview program access:

| Feature | Module | Prerequisites |
|---|---|---|
| Gemini Enterprise A2A registration | `app/a2a/provider.py` | Preview program access + `ENABLE_A2A_EXPERIMENTAL=true` |
| Firestore workflow state store | `app/workflows/state_store.py` | `WORKFLOW_STATE_BACKEND=firestore` + GCP project |
| Agent Gateway policy enforcement | `governance/agent-gateway.example.yaml` | Preview program access |
| Semantic Governance | `governance/semantic-governance.example.yaml` | Preview program access |

### optional-integration

Features that require additional setup but are fully documented:

| Feature | Module | Prerequisites |
|---|---|---|
| Cloud Run remote MCP deployment | `cloudrun/remote_mcp/` | GCP project + `make deploy-remote-mcp` |
| Google Drive connector | `app/connectors/drive_connector.py` | `ENABLE_WORKSPACE_CONNECTORS=true` |
| Gmail connector | `app/connectors/gmail_connector.py` | `ENABLE_WORKSPACE_CONNECTORS=true` |
| Calendar connector | `app/connectors/calendar_connector.py` | `ENABLE_WORKSPACE_CONNECTORS=true` |
| Model Armor | `governance/model-armor.example.yaml` | GA in some regions |
| Firestore persistence | `cloudrun/tool_api/main.py` | GCP Firestore in Native mode |

---

## Architecture Narrative

### 1. Durable Workflows

RetailOps workflows are now first-class objects that survive agent session restarts.
The `ReplenishmentWorkflowEngine` drives a state machine with explicit checkpoints,
event sourcing, and human-in-the-loop approval at the right moments.

```
Agent → workflow_agent → start_replenishment_workflow()
      → workflow pauses for approval (PAUSED_FOR_APPROVAL)
      → human reviews via REST API or agent → approve_workflow()
      → workflow resumes → COMPLETED
```

### 2. External Agent Interoperability

The A2A federation layer demonstrates how RetailOps can delegate to specialized
external agents (Finance Approval, Supplier Negotiation) using a clean interface
that will map to Gemini Enterprise A2A when it becomes generally available.

```
Agent → A2AProvider → MockFinanceApprovalAgent (local)
                    → Gemini Enterprise A2A (preview/GA)
```

### 3. Transport-Flexible Tool Serving

The same business operations are now available through three transports with
zero business logic duplication:

```
mcp_remote_adapters.py  (shared business logic)
  ├─ cloudrun/tool_api/main.py    (REST)
  ├─ app/tools/mcp_stdio_retailops.py  (stdio MCP for Cursor)
  └─ cloudrun/remote_mcp/main.py       (remote MCP over HTTP)
```

### 4. Measurable Quality and Observability

Every release can now be scored:
- Workflow eval (10 cases)
- A2A eval (10 cases)
- Policy eval (15 cases)
- Agent eval (ADK eval SDK, requires cloud)

Correlation IDs tie logs across all service boundaries.

### 5. Governance-Ready Future Path

Local policy simulation documents the intended behavior that platform features
(Agent Gateway, Semantic Governance, Model Armor) will enforce when they become
generally available. The governance test pack ensures the intended behavior is
captured and testable before the platform features arrive.

---

## How to Contribute

1. Local demo: `make demo-workflow` and `make demo-a2a`
2. Tests: `make test`
3. Eval: `make eval-all`
4. Quality: `make quality-gate`
5. Cloud deploy: see README §Quick Paths
