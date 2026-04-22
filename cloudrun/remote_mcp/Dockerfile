FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared app package (business logic shared with REST API)
COPY app/ ./app/

# Copy the remote MCP server
COPY cloudrun/remote_mcp/main.py .

ENV PORT=8090

# Authentication note:
# Cloud Run enforces IAM-authenticated invocations by default.
# For local development set REMOTE_MCP_SKIP_AUTH=true.
# See docs/remote-mcp-runbook.md for the full auth matrix.

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8090}"]
