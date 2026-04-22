# Evaluation Runbook

**Status: runnable-now** (local suites) | **optional-integration** (cloud agent eval)

This runbook covers the local evaluation suites added in the Next '26 expansion
and the existing hybrid evaluation flow for the RetailOps agent runtime.

---

## Local Evaluation Suites (New)

### Quick run — all local suites

```bash
make eval-all
# → runs workflow + A2A + policy evals, saves scorecard to eval/results/
```

### Workflow Eval

Tests the `ReplenishmentWorkflowEngine` against golden cases.
Golden cases: `eval/golden/workflow_cases.csv`

```bash
make eval-workflow
```

### A2A Eval

Tests A2A provider routing and mock external agents.
Golden cases: `eval/golden/a2a_cases.csv`

```bash
make eval-a2a
```

### Policy Eval

Tests approval policy thresholds and local governance guardrails.
Golden cases: `eval/golden/policy_cases.csv`

```bash
make eval-policy
```

---

## ADK Agent Evaluation (Cloud)

## Inputs

- Prompt dataset: `eval/eval_prompts.csv`
- Gate thresholds: `eval/eval_gate_config.json`
- Judge calibration set: `eval/judge_calibration.csv`

## Commands

- Run hybrid agent evaluation:
  - `make eval-agent`
- Run judge calibration:
  - `make eval-judge-calibration`

## Output artifacts

- Latest summary:
  - `eval/results/eval_summary_latest.json`
- Instance-level scoring:
  - `eval/results/last_instance_results.csv`
- Judge calibration summary:
  - `eval/results/judge_calibration_latest.json`

## What the hybrid gate enforces

`app/deploy/evaluate_agent.py` combines:

- deterministic checks from expected and forbidden keywords
- trajectory quality (`trajectory_precision`, `trajectory_recall`, exact match)
- Vertex rubric metrics (`FINAL_RESPONSE_QUALITY`, `TOOL_USE_QUALITY`, `HALLUCINATION`, `SAFETY`)
- reliability dimensions (`failure_rate`, `latency_p95_seconds`)

Threshold logic is loaded from `eval/eval_gate_config.json`.

- Keys ending with `_max` are treated as maximum allowed values.
- All other keys are minimum required values.

## CI behavior

The CI workflow at `.github/workflows/ci.yml`:

- always runs compile checks
- runs `make eval-agent` only when `DEPLOYED_AGENT_RESOURCE_NAME` secret is configured
- uploads `eval/results` as an artifact regardless of success/failure

## Troubleshooting

- Missing columns error:
  - ensure `eval/eval_prompts.csv` includes all required schema fields
- Empty trajectory scores:
  - confirm inference output includes trajectory/tool-call fields for your runtime
- Judge calibration preview API errors:
  - verify Vertex preview evaluation APIs are enabled for your project/region
