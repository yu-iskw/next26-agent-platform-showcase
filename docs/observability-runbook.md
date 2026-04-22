# Observability Runbook

**Status: runnable-now**

## Overview

RetailOps uses OpenTelemetry for distributed tracing, structured logging with
correlation IDs, and a release scorecard system for eval-based quality gates.

---

## Correlation IDs

Every request carries two correlation identifiers:

| Header | Description |
|---|---|
| `X-Request-ID` | Unique identifier for a single HTTP request |
| `traceparent` | W3C trace context (trace_id + span_id) |
| `X-Correlation-ID` | Alias for X-Request-ID (some clients prefer this) |

### How to trace a request across services

1. Find the `X-Request-ID` in the agent or tool API response headers
2. Search Cloud Logging with:
   ```
   jsonPayload.correlation_id="<request-id>"
   ```
3. Or use Cloud Trace with the `trace_id` from the `traceparent` header

### Generating correlation context

```python
from app.observability.correlation import correlation_headers, extract_from_headers

# Outbound: add to HTTP request
headers = correlation_headers()

# Inbound: extract from incoming request
cid = extract_from_headers(dict(request.headers))

# Structured logging
from app.observability.correlation import structured_log_fields
import logging
log = logging.getLogger(__name__)
log.info("Processing request", extra={"json_fields": structured_log_fields()})
```

---

## Tracing

Wrap any business operation in a trace span:

```python
from app.observability.trace_helpers import span, timed

with span("workflow.finalize", {"workflow_id": wf_id}):
    engine.finalize(wf_id)

@timed
def compute_recommendation(...)
    ...
```

Spans are no-ops if the OTel SDK is not configured (safe for local dev).

---

## How to Investigate a Failed Workflow

1. Find the `workflow_id` in the agent response or tool API response
2. Check the workflow state:
   ```bash
   cat .local/state/<workflow_id>.json | python -m json.tool
   ```
3. Replay the audit log:
   ```bash
   cat .local/state/audit/<workflow_id>.jsonl
   ```
4. Use the Python API:
   ```python
   from app.workflows.audit_log import AuditLogger, reconstruct_state_from_events
   audit = AuditLogger()
   summary = reconstruct_state_from_events(audit.read_all("wf-xxx"))
   print(summary["status"])
   print("\n".join(summary["timeline"]))
   ```
5. Get a human-readable explanation:
   ```python
   from app.workflows.resume_handlers import get_workflow_explanation
   from app.workflows.state_store import get_default_state_store
   store = get_default_state_store()
   state = store.load("wf-xxx")
   print(get_workflow_explanation(state))
   ```

---

## Release Scorecard

Run the full eval suite and generate a scorecard:

```bash
make eval-all
```

Results land in `eval/results/scorecard_<timestamp>.json`.

### Compare with a prior run

```python
from app.observability.release_scorecard import ReleaseScorecard
from pathlib import Path

scorecard = ReleaseScorecard(release_tag="v1.2.0")
# ... add suites ...
regression = scorecard.compare_with_prior()
print(regression["status"])   # "stable", "improvement", or "regression"
print(regression["delta"])
```

### Scorecard artifact format

```json
{
  "release_tag": "v1.2.0",
  "overall_pass_rate": 0.95,
  "suite_count": 3,
  "total_cases": 35,
  "suites": [
    {
      "suite_name": "workflow",
      "pass_rate": 1.0,
      "p50_latency_ms": 45.2,
      "p95_latency_ms": 120.5,
      "top_failure_categories": {}
    }
  ]
}
```

---

## Cloud Logging Checklist

Verify these APIs are enabled (from Terraform):
- `logging.googleapis.com`
- `cloudtrace.googleapis.com`
- `monitoring.googleapis.com`
- `telemetry.googleapis.com`

Agent Runtime telemetry env vars:
```bash
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false  # Only enable with compliance approval
GOOGLE_CLOUD_PROJECT=your-project-id
```

Navigate to: Cloud Logging → Log Explorer → Filter by `logName` containing `retailops`

---

## Metrics Reference

| Metric | Description |
|---|---|
| `workflow.completion.latency_ms` | Time from CREATED to COMPLETED |
| `workflow.approval.wait_ms` | Time from PAUSED to decision |
| `a2a.delegation.latency_ms` | Time for external agent round-trip |
| `tool_api.request.latency_ms` | REST tool API response time |
| `eval.pass_rate` | Fraction of eval cases passing |
