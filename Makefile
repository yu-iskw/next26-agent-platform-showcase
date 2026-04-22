# destroy-* / describe-*: gcloud/ADC. destroy-agent needs DEPLOYED_AGENT_RESOURCE_NAME
# (optional AGENT_ENGINE_DELETE_FORCE=true). describe-agent: get() when that env is set,
# else lists engines matching DEPLOYED_AGENT_NAME (default retailops-copilot).
.PHONY: install seed-data run-local mcp-retailops test compile

.PHONY: deploy-agent deploy-agent-preflight deploy-tool-api
.PHONY: destroy-agent destroy-tool-api destroy-deployed
.PHONY: describe-agent describe-tool-api describe-deployed

.PHONY: eval-agent eval-judge-calibration eval-workflow eval-a2a eval-policy eval-all

.PHONY: quality-gate quality-gate-optional
.PHONY: deps-export-agent-runtime deps-export-tool-api deps-verify-drift
.PHONY: lifecycle-ci lifecycle-gcp-preflight

.PHONY: run-remote-mcp-local deploy-remote-mcp test-remote-mcp describe-remote-mcp-config
.PHONY: demo-workflow demo-a2a generate-agent-card

install:
	uv sync

seed-data:
	uv run python -m app.deploy.seed_bigquery

run-local:
	uv run python -m app.deploy.run_local

mcp-retailops:
	bash scripts/run_mcp_stdio_retailops.sh

# ---- Workstream C: Remote MCP server (runnable-now) ---------

run-remote-mcp-local:
	@echo "Starting remote MCP server on http://localhost:8090 (REMOTE_MCP_SKIP_AUTH=true)"
	REMOTE_MCP_SKIP_AUTH=true CLOUDRUN_TOOL_API_SKIP_ID_TOKEN=true \
	uv run uvicorn cloudrun.remote_mcp.main:app --host 0.0.0.0 --port 8090 --reload

deploy-remote-mcp:
	@echo "Deploying remote MCP server to Cloud Run..."
	gcloud builds submit . \
		--dockerfile cloudrun/remote_mcp/Dockerfile \
		--tag gcr.io/$${GOOGLE_CLOUD_PROJECT}/retailops-remote-mcp
	gcloud run deploy retailops-remote-mcp \
		--image gcr.io/$${GOOGLE_CLOUD_PROJECT}/retailops-remote-mcp \
		--region $${GOOGLE_CLOUD_LOCATION:-us-central1} \
		--no-allow-unauthenticated \
		--set-env-vars CLOUDRUN_TOOL_API_BASE_URL=$${CLOUDRUN_TOOL_API_BASE_URL}

test-remote-mcp:
	@echo "Testing remote MCP server (requires server running on :8090)..."
	curl -s http://localhost:8090/healthz | uv run python -m json.tool
	curl -s http://localhost:8090/mcp/tools/list | uv run python -m json.tool

describe-remote-mcp-config:
	@echo "Remote MCP configuration:"
	@echo "  Local:  http://localhost:8090 (make run-remote-mcp-local)"
	@echo "  Deploy: make deploy-remote-mcp (requires GOOGLE_CLOUD_PROJECT)"
	@echo "  Docs:   docs/remote-mcp-runbook.md"

# ---- Workstream B: A2A demos & agent card -------------------

demo-a2a:
	@echo "Running local A2A federation demo..."
	uv run python -c "
from app.a2a.provider import A2AProvider
from app.a2a.models import A2ATaskRequest
provider = A2AProvider(use_mocks=True)
req = A2ATaskRequest(intent='finance.order.review', payload={'order_id': 'po-demo', 'total_cost_usd': 30000.0})
resp = provider.route(req)
print('Finance decision:', resp.result.get('decision'))
req2 = A2ATaskRequest(intent='supplier.quote.request', payload={'product_id': 'prod-001', 'quantity': 200})
resp2 = provider.route(req2)
print('Supplier quote: \$$%.2f/unit (discount=%s%%)' % (resp2.result.get('unit_price_usd', 0), resp2.result.get('discount_pct', 0)))
"

generate-agent-card:
	@echo "Generating agent card JSON..."
	uv run python -m app.a2a.agent_card
	@echo "Agent card: docs/examples/retailops-agent-card.json"

# ---- Workstream A: Workflow demo ----------------------------

demo-workflow:
	@echo "Running local workflow demo..."
	uv run python -c "
import tempfile, os
os.environ['WORKFLOW_STATE_DIR'] = '.local/state'
from app.workflows.order_replenishment import ReplenishmentWorkflowEngine
from app.workflows.state_models import ApprovalDecision, ApprovalStatus
engine = ReplenishmentWorkflowEngine()
state = engine.create_workflow('prod-001', product_name='Trail Backpack Pro', risk_tolerance='medium')
state = engine.compute_recommendation(state.workflow_id, current_stock=42, reorder_point=80, estimated_unit_cost_usd=95.0)
state = engine.propose_order(state.workflow_id)
state = engine.advance(state.workflow_id)
print('Workflow ID:', state.workflow_id)
print('Status:', state.status.value)
print('Approval required:', state.approval_required)
print('Proposed total: \$%.2f' % state.proposed_total_cost_usd)
if state.approval_required:
    print('  → Approving...')
    decision = ApprovalDecision(workflow_id=state.workflow_id, approver='demo-user', decision=ApprovalStatus.APPROVED, notes='Demo approval')
    engine.apply_approval(state.workflow_id, decision)
    state = engine.finalize(state.workflow_id)
    print('Final status:', state.status.value)
    print('Order ID:', state.order_id)
"

# ---- Evaluation (Workstream D) ------------------------------

eval-workflow:
	@echo "Running workflow evaluation suite..."
	uv run python -m app.evals.workflow_eval

eval-a2a:
	@echo "Running A2A evaluation suite..."
	uv run python -m app.evals.a2a_eval

eval-policy:
	@echo "Running policy evaluation suite..."
	uv run python -m app.evals.policy_eval

eval-all: eval-workflow eval-a2a eval-policy
	@echo "All eval suites complete. Check eval/results/ for scorecard artifacts."

# ---- Agent deployment lifecycle (existing) ------------------

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
