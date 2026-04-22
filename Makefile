# destroy-* / describe-*: gcloud/ADC. destroy-agent needs DEPLOYED_AGENT_RESOURCE_NAME
# (optional AGENT_ENGINE_DELETE_FORCE=true). describe-agent: get() when that env is set,
# else lists engines matching DEPLOYED_AGENT_NAME (default retailops-copilot).
.PHONY: install seed-data run-local mcp-retailops test compile

.PHONY: deploy-agent deploy-agent-preflight deploy-tool-api
.PHONY: destroy-agent destroy-tool-api destroy-deployed
.PHONY: describe-agent describe-tool-api describe-deployed

.PHONY: eval-agent eval-judge-calibration

.PHONY: quality-gate quality-gate-optional
.PHONY: deps-export-agent-runtime deps-export-tool-api deps-verify-drift
.PHONY: lifecycle-ci lifecycle-gcp-preflight

install:
	uv sync

seed-data:
	uv run python -m app.deploy.seed_bigquery

run-local:
	uv run python -m app.deploy.run_local

mcp-retailops:
	bash scripts/run_mcp_stdio_retailops.sh

deploy-agent:
	PYTHONUNBUFFERED=1 uv run python -m app.deploy.deploy_agent_runtime

deploy-agent-preflight:
	uv run python -m app.deploy.preflight

eval-agent:
	uv run python -m app.deploy.evaluate_agent

eval-judge-calibration:
	uv run python -m app.deploy.evaluate_judge_calibration

deploy-tool-api:
	uv run bash scripts/deploy_cloudrun_tool_api.sh

destroy-agent:
	uv run python -m app.deploy.destroy_agent_runtime

destroy-tool-api:
	uv run bash scripts/destroy_cloudrun_tool_api.sh

destroy-deployed: destroy-tool-api destroy-agent

describe-agent:
	uv run python -m app.deploy.describe_agent_runtime

describe-tool-api:
	uv run bash scripts/describe_cloudrun_tool_api.sh

describe-deployed:
	@if ! uv run bash scripts/describe_cloudrun_tool_api.sh; then \
		echo "describe_cloudrun_tool_api failed (e.g. service missing); continuing to describe_agent_runtime." >&2; \
	fi
	uv run python -m app.deploy.describe_agent_runtime

compile:
	uv run python -m compileall app cloudrun

quality-gate:
	uv run ruff format --check app cloudrun
	uv run ruff check app cloudrun
	uv run pyright
	uv run bandit -q -c bandit.yaml -r app cloudrun/tool_api
	trunk check --filter=osv-scanner --all

quality-gate-optional:
	trunk check -y -a

deps-export-agent-runtime:
	uv run python -m app.deploy.export_requirements --target agent-runtime

deps-export-tool-api:
	uv run python -m app.deploy.export_requirements --target tool-api

deps-verify-drift:
	git diff --exit-code -- app/deploy/runtime.requirements.txt cloudrun/tool_api/requirements.txt

test:
	uv run python -m unittest discover -s tests -p 'test_*.py' -v

lifecycle-ci: deps-verify-drift quality-gate compile test

lifecycle-gcp-preflight: lifecycle-ci deploy-agent-preflight
