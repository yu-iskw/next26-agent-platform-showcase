# Remote MCP Server Runbook

**Status: runnable-now** (local and Cloud Run)

The remote MCP server exposes the same RetailOps business operations as the
stdio MCP server and the REST tool API, but over HTTP for use by remote MCP clients
(Claude Desktop, Cursor, etc.) without requiring a local Python process.

---

## When to Use Each Transport

| Transport | Use when |
|---|---|
| **stdio MCP** (`app/tools/mcp_stdio_retailops.py`) | Cursor/Claude Desktop; local dev with `.env`; single user |
| **REST tool API** (`cloudrun/tool_api/main.py`) | Agent runtime; programmatic access; Firestore persistence |
| **Remote MCP** (`cloudrun/remote_mcp/main.py`) | Remote MCP clients; team-shared server; no local Python needed |

All three transports share the same business logic via `app/tools/mcp_remote_adapters.py`.
Business rules are not duplicated.

---

## Quick Start — Local

```bash
# Start the remote MCP server locally (no auth required)
make run-remote-mcp-local

# Verify it's running
curl http://localhost:8090/healthz
# → {"status":"ok","version":"0.1.0","transport":"remote-mcp"}

# List available tools
curl http://localhost:8090/mcp/tools/list | python -m json.tool

# Call a tool
curl -X POST http://localhost:8090/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "list_pending_approvals", "arguments": {}}'
```

---

## Available Tools

| Tool Name | Description |
|---|---|
| `create_purchase_order` | Create a purchase order via the Cloud Run tool API |
| `submit_approval_request` | Submit an approval request for a high-value order |
| `get_order_status` | Fetch order status by order_id |
| `start_replenishment_workflow` | Start a durable replenishment workflow |
| `get_workflow_status` | Get workflow status by workflow_id |
| `list_pending_approvals` | List all workflows awaiting approval |
| `approve_workflow` | Approve a paused workflow |
| `reject_workflow` | Reject a paused workflow |
| `check_tool_api_health` | Check the underlying tool API health |

---

## Deploy to Cloud Run

```bash
# Requires: GOOGLE_CLOUD_PROJECT, CLOUDRUN_TOOL_API_BASE_URL
make deploy-remote-mcp
```

Grant invocation access:
```bash
gcloud run services add-iam-policy-binding retailops-remote-mcp \
  --region us-central1 \
  --member "user:YOUR_EMAIL" \
  --role roles/run.invoker
```

---

## Authentication Matrix

| Environment | Auth Required | How |
|---|---|---|
| Local (`localhost:8090`) | No | `REMOTE_MCP_SKIP_AUTH=true` (set by `make run-remote-mcp-local`) |
| Local → Cloud Run tool API (http://) | No | `CLOUDRUN_TOOL_API_SKIP_ID_TOKEN=true` |
| Local → Cloud Run tool API (https://) | Yes | ADC / `gcloud auth application-default login` |
| Cloud Run → tool API | Yes | Cloud Run service account with `roles/run.invoker` |
| MCP client → Cloud Run remote MCP | Yes | Bearer token via `gcloud auth print-identity-token` |

---

## Describe Configuration

```bash
make describe-remote-mcp-config
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**

The remote MCP server auto-adds the repo root to `sys.path`. Run it from the
repo root or ensure `PYTHONPATH` includes the repo root:

```bash
cd /path/to/next26-agent-platform-showcase
make run-remote-mcp-local
```

**`403 Forbidden` from Cloud Run**

The Cloud Run service requires IAM authentication. Grant `roles/run.invoker` to your
identity or service account.

**Tool API connection refused**

Set `CLOUDRUN_TOOL_API_BASE_URL` to a reachable URL. For pure local testing without
the REST tool API, set `CLOUDRUN_TOOL_API_SKIP_ID_TOKEN=true` and start the tool API
server separately:

```bash
uv run uvicorn cloudrun.tool_api.main:app --port 8080 --reload
```

---

## File Reference

| File | Description |
|---|---|
| `cloudrun/remote_mcp/main.py` | Remote MCP HTTP server |
| `cloudrun/remote_mcp/Dockerfile` | Container image |
| `cloudrun/remote_mcp/requirements.txt` | Runtime dependencies |
| `app/tools/mcp_remote_adapters.py` | Shared business logic (transport-agnostic) |
| `app/tools/mcp_stdio_retailops.py` | stdio MCP server (Cursor) |
