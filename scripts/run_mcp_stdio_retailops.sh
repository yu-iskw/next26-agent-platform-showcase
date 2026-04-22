#!/usr/bin/env bash
# Run the RetailOps stdio MCP server from repo root so `app` resolves and uv uses pyproject.toml.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
exec uv run python -m app.tools.mcp_stdio_retailops
