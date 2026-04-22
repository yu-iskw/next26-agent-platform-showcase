#!/usr/bin/env bash
set -euo pipefail

_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${_script_dir}/lib/cloudrun_tool_api_env.sh"

if ! gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --platform managed &>/dev/null; then
	echo "Cloud Run service ${SERVICE_NAME} not found in ${REGION}; nothing to delete."
	exit 0
fi

gcloud run services delete "${SERVICE_NAME}" --region "${REGION}" --platform managed --quiet
echo "Deleted Cloud Run service ${SERVICE_NAME}."
