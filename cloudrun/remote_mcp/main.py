"""Remote MCP server deployable to Cloud Run.

Exposes the same business operations as the stdio MCP server but over HTTP,
enabling remote MCP clients (e.g., Claude Desktop, Cursor) to connect without
a local Python process.

Architecture:
  This server is a thin HTTP transport wrapper around the shared service layer
  in app/tools/mcp_remote_adapters.py. Business logic is NOT duplicated.

Authentication:
  Cloud Run assumes authenticated invocations (IAM-enforced).
  For local development use REMOTE_MCP_SKIP_AUTH=true.
  See docs/remote-mcp-runbook.md for the full auth matrix.

Status:
  runnable-now  — local HTTP mode (REMOTE_MCP_SKIP_AUTH=true)
  runnable-now  — Cloud Run deployment with IAM

Usage:
  Local:  uvicorn cloudrun.remote_mcp.main:app --port 8090 --reload
  Docker: docker run -p 8090:8090 retailops-remote-mcp
  Cloud:  see Makefile target deploy-remote-mcp and docs/remote-mcp-runbook.md
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

# Ensure app package is importable when running from cloudrun/remote_mcp/
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

app = FastAPI(
    title="RetailOps Remote MCP Server",
    version="0.1.0",
    description=("Remote MCP transport for RetailOps tools. Deploy to Cloud Run for authenticated remote access."),
)
_log = logging.getLogger("retailops.remote_mcp")
_SKIP_AUTH = os.getenv("REMOTE_MCP_SKIP_AUTH", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def correlation_middleware(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    _log.info(
        "remote_mcp path=%s method=%s request_id=%s",
        request.url.path,
        request.method,
        request_id,
    )
    return response


# ---------------------------------------------------------------------------
# MCP tool registry — describes available tools to MCP clients
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "create_purchase_order",
        "description": "Create a replenishment purchase order through the Cloud Run tool API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "units": {"type": "integer", "minimum": 1},
                "requester": {"type": "string", "default": "agent"},
            },
            "required": ["product_id", "units"],
        },
    },
    {
        "name": "submit_approval_request",
        "description": "Submit an approval request for a high-value order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Fetch the status of an existing purchase order.",
        "inputSchema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "start_replenishment_workflow",
        "description": (
            "Start a durable replenishment workflow. Returns a workflow_id. "
            "If the order exceeds the approval threshold the workflow pauses for human approval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "product_name": {"type": "string"},
                "requester": {"type": "string"},
                "risk_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
                "current_stock": {"type": "integer", "minimum": 0},
                "reorder_point": {"type": "integer", "minimum": 0},
                "estimated_unit_cost_usd": {"type": "number", "minimum": 0.01},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "get_workflow_status",
        "description": "Fetch the current status and timeline of a replenishment workflow.",
        "inputSchema": {
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}},
            "required": ["workflow_id"],
        },
    },
    {
        "name": "list_pending_approvals",
        "description": "List all replenishment workflows currently awaiting human approval.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "approve_workflow",
        "description": "Approve a paused replenishment workflow and finalize the order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "approver": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "reject_workflow",
        "description": "Reject a paused replenishment workflow.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "approver": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "check_tool_api_health",
        "description": "Check the health of the underlying Cloud Run tool API.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# MCP protocol endpoints
# ---------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": "0.1.0", "transport": "remote-mcp"}


@app.get("/mcp/tools/list")
def list_tools() -> dict[str, Any]:
    """Return the tool manifest to MCP clients."""
    return {"tools": _TOOLS}


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.post("/mcp/tools/call")
def call_tool(req: ToolCallRequest) -> dict[str, Any]:
    """Dispatch a tool call to the shared service layer.

    The shared layer (mcp_remote_adapters) ensures business logic is not
    duplicated between REST and MCP transports.
    """
    try:
        from app.tools import mcp_remote_adapters as adapters

        dispatcher: dict[str, Any] = {
            "create_purchase_order": lambda a: adapters.tool_create_purchase_order(**a),
            "submit_approval_request": lambda a: adapters.tool_submit_approval_request(**a),
            "get_order_status": lambda a: adapters.tool_get_order_status(**a),
            "check_tool_api_health": lambda _: adapters.tool_check_health(),
            "start_replenishment_workflow": lambda a: adapters.tool_start_replenishment_workflow(**a),
            "get_workflow_status": lambda a: adapters.tool_get_workflow_status(**a),
            "list_pending_approvals": lambda _: adapters.tool_list_pending_approvals(),
            "approve_workflow": lambda a: adapters.tool_approve_workflow(**a),
            "reject_workflow": lambda a: adapters.tool_reject_workflow(**a),
        }

        fn = dispatcher.get(req.name)
        if fn is None:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {req.name!r}")

        result = fn(req.arguments)
        return {"content": [{"type": "text", "text": result}], "isError": False}
    except HTTPException:
        raise
    except Exception as exc:
        _log.error("Tool call %s failed: %s", req.name, exc)
        return {
            "content": [{"type": "text", "text": str(exc)}],
            "isError": True,
        }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8090"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)  # noqa: S104
