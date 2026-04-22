#!/usr/bin/env bash
# Print deployed Cloud Run tool API URL and a Cursor-ready mcpServers fragment for the local stdio MCP bridge.
set -euo pipefail

_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${_script_dir}/lib/cloudrun_tool_api_env.sh"

cd "${REPO_ROOT}"

JSON_ONLY=false
if [[ ${1-} == "--json" ]]; then
	JSON_ONLY=true
fi

if ! gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --platform managed &>/dev/null; then
	echo "Cloud Run service ${SERVICE_NAME} not found in ${REGION} (project ${GOOGLE_CLOUD_PROJECT})." >&2
	exit 1
fi

TOOL_API_URL="$(
	gcloud run services describe "${SERVICE_NAME}" \
		--region "${REGION}" \
		--platform managed \
		--format='value(status.url)'
)"
TOOL_API_URL="${TOOL_API_URL%/}"

export TOOL_API_URL

emit_json() {
	python3 <<'PY'
import json
import os

repo = os.environ["REPO_ROOT"]
url = os.environ["TOOL_API_URL"]
print(
    json.dumps(
        {
            "mcpServers": {
                "retailops-tool-api": {
                    "command": "uv",
                    "args": ["run", "python", "-m", "app.tools.mcp_stdio_retailops"],
                    "cwd": repo,
                    "env": {"CLOUDRUN_TOOL_API_BASE_URL": url},
                }
            }
        },
        indent=2,
    )
)
PY
}

if [[ ${JSON_ONLY} == true ]]; then
	emit_json
	exit 0
fi

cat <<EOF
Local stdio MCP -> deployed Cloud Run tool API
  project: ${GOOGLE_CLOUD_PROJECT}
  region:  ${REGION}
  service: ${SERVICE_NAME}
  CLOUDRUN_TOOL_API_BASE_URL: ${TOOL_API_URL}

Merge the JSON below into your Cursor MCP config (machine-readable: ${0##*/} --json).

--- mcpServers fragment (uv run + cwd) ---
EOF
emit_json

cat <<EOF

--- Launcher variant (absolute path, no cwd) ---
  command: bash
  args: ["${REPO_ROOT}/scripts/run_mcp_stdio_retailops.sh"]
  env:   { "CLOUDRUN_TOOL_API_BASE_URL": "${TOOL_API_URL}" }

EOF
