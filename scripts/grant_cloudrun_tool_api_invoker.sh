#!/usr/bin/env bash
# Grant Cloud Run invoker on retailops-tool-api to a principal that must call it with an OIDC ID token.
#
# Examples:
#   MEMBER='user:you@example.com' bash scripts/grant_cloudrun_tool_api_invoker.sh
#   MEMBER='serviceAccount:YOUR_AGENT_ENGINE_SA@...iam.gserviceaccount.com' bash scripts/grant_cloudrun_tool_api_invoker.sh
#
# Find the Vertex AI Agent Engine / Reasoning Engine service identity in Cloud Console
# (IAM → include Google-managed principals) or in the Agent Engine resource details.
set -euo pipefail

_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${_script_dir}/lib/cloudrun_tool_api_env.sh"

: "${MEMBER:?Set MEMBER to an IAM member, e.g. user:you@example.com or serviceAccount:...@...iam.gserviceaccount.com}"

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
	--project="${GOOGLE_CLOUD_PROJECT}" \
	--region="${REGION}" \
	--platform=managed \
	--member="${MEMBER}" \
	--role="roles/run.invoker"

echo "Granted roles/run.invoker on ${SERVICE_NAME} (${REGION}) to ${MEMBER}"
