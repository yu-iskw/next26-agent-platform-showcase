# Shared environment for retailops-tool-api Cloud Run helper scripts.
# shellcheck shell=bash
_lib_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_repo_root="$(cd -- "${_lib_dir}/../.." && pwd)"

if [[ -f "${_repo_root}/.env" ]]; then
	set -a
	# shellcheck disable=SC1091
	source "${_repo_root}/.env"
	set +a
fi

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT in .env or environment}"

# Set for scripts that source this file (not referenced in this file).
# shellcheck disable=SC2034
SERVICE_NAME="retailops-tool-api"
# shellcheck disable=SC2034
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

export REPO_ROOT="${_repo_root}"
