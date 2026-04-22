"""Stdio MCP server that proxies RetailOps tool calls to the Cloud Run REST API.

Run (from repo root, with ``.env`` or env vars set):

    uv run python -m app.tools.mcp_stdio_retailops

Cursor ``mcpServers`` example (adjust ``cwd`` to your clone path):

.. code-block:: json

    {
      "mcpServers": {
        "retailops-tool-api": {
          "command": "uv",
          "args": ["run", "python", "-m", "app.tools.mcp_stdio_retailops"],
          "cwd": "/absolute/path/to/next26-agent-platform-showcase",
          "env": {
            "CLOUDRUN_TOOL_API_BASE_URL": "https://YOUR-CLOUD-RUN-URL"
          }
        }
      }
    }

A ready-to-merge fragment lives at ``scripts/cursor-mcp-retailops.example.json``
(adjust ``cwd`` and env values, then merge ``mcpServers`` into your Cursor MCP config).
If ``cwd`` is unreliable in your host, use ``bash`` + absolute path to
``scripts/run_mcp_stdio_retailops.sh`` (see README §7). Do not point ``command``
at a bare ``python`` running ``-m app.tools...`` or you will get
``ModuleNotFoundError: No module named 'app'``.

``app.tools.config`` loads ``.env`` when ``cwd`` is the repository root.
Remote ``https://`` tool API URLs use an OIDC ID token (ADC); grant
``roles/run.invoker`` on the Cloud Run service to your user and to the
Agent Engine identity. Local ``http://localhost`` skips the token.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import commerce_tools

mcp = FastMCP("retailops-tool-api")


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
def create_purchase_order(product_id: str, units: int, requester: str = "agent") -> str:
    """Create a replenishment purchase order via the Cloud Run tool API."""
    doc = commerce_tools.create_purchase_order(product_id, units, requester)
    return _json_text(doc)


@mcp.tool()
def submit_approval_request(order_id: str, reason: str) -> str:
    """Submit an approval request for a high-value order."""
    doc = commerce_tools.submit_approval_request(order_id, reason)
    return _json_text(doc)


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Fetch purchase order status by order_id."""
    doc = commerce_tools.get_order_status(order_id)
    return _json_text(doc)


@mcp.tool()
def check_tool_api_health() -> str:
    """Call GET /healthz on the configured Cloud Run tool API base URL."""
    return _json_text(commerce_tools.get_tool_api_health())


if __name__ == "__main__":
    mcp.run()
