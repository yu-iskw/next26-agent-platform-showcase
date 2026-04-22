#!/usr/bin/env bash
set -euo pipefail

_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${_script_dir}/lib/cloudrun_tool_api_env.sh"

IMAGE="gcr.io/${GOOGLE_CLOUD_PROJECT}/${SERVICE_NAME}:latest"

gcloud builds submit . --dockerfile cloudrun/tool_api/Dockerfile --tag "${IMAGE}"

gcloud run deploy "${SERVICE_NAME}" --image "${IMAGE}" --platform managed --region "${REGION}" \
	--no-allow-unauthenticated \
	--set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}"

SERVICE_URL="$(
	gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --platform managed \
		--format 'value(status.url)'
)"

echo "Cloud Run service deployed (authenticated invokers only)."
echo "Service URL: ${SERVICE_URL}"
echo "Set CLOUDRUN_TOOL_API_BASE_URL in .env to this URL."
echo "Grant roles/run.invoker to callers: MEMBER='serviceAccount:...' bash scripts/grant_cloudrun_tool_api_invoker.sh"
