# Workflow State Model

**Status: runnable-now** (local JSON state store) | **preview-scaffold** (Firestore)

## Overview

The `app/workflows/` package implements a durable, resumable human-in-the-loop
replenishment workflow. It supports:

- Explicit checkpoints for pause/resume
- Event-sourced audit log for replay and debugging
- Escalation and timeout policies
- Risk-tolerance-adjusted approval thresholds
- Local file-backed persistence (no cloud required)
- Optional Firestore persistence scaffold

---

## State Machine

```
CREATED
  │
  ▼
RUNNING ──────────────────────────────────────────────────────────────────────▶ FAILED
  │                                                                            ▲
  │ propose_order                                                              │
  ▼                                                                            │
approval_required?
  ├── No  ──────────────────────────────────────────────────────────────────▶ COMPLETED
  └── Yes
        │
        ▼
  PAUSED_FOR_APPROVAL
        │
        ├──[timeout]──────────────────────────────▶ ESCALATED ──[max exceeded]──▶ TIMED_OUT
        │
        ├──[approved]──────────────────────────────▶ APPROVED ──[finalize]──────▶ COMPLETED
        │
        ├──[rejected]──────────────────────────────▶ REJECTED
        │
        └──[revision requested]────────────────────▶ REVISION_REQUIRED ──[re-propose]──▶ RUNNING
```

---

## Domain Models

### `WorkflowStatus`

| Status | Description |
|---|---|
| `CREATED` | Workflow initialized, not yet running |
| `RUNNING` | Actively processing (recommendation computed, order proposed) |
| `PAUSED_FOR_APPROVAL` | Waiting for human approval decision |
| `APPROVED` | Approval granted; ready to finalize |
| `REJECTED` | Approval denied; workflow closed |
| `REVISION_REQUIRED` | Approver requested changes before re-submission |
| `ESCALATED` | Approval deadline passed; escalated to secondary approver |
| `TIMED_OUT` | Max escalations exceeded; auto-rejected |
| `COMPLETED` | Order finalized and submitted |
| `FAILED` | Unexpected error; see `failure_reason` |

### `ApprovalStatus`

| Status | Description |
|---|---|
| `PENDING` | Awaiting a decision |
| `APPROVED` | Decision: approved |
| `REJECTED` | Decision: rejected |
| `ESCALATED` | Escalated to secondary approver |
| `EXPIRED` | Approval window expired |

### `EscalationPolicy`

```python
EscalationPolicy(
    approval_timeout_hours=24.0,   # Hours before escalation triggers
    escalation_contact="manager@retailops.example",
    max_escalations=2,             # After this, auto-reject
    auto_reject_after_escalations=True,
)
```

### Approval Threshold

The approval threshold depends on `risk_tolerance`:

| Risk Tolerance | Threshold |
|---|---|
| `low` | $20,000 (80% × $25k) |
| `medium` (default) | $25,000 |
| `high` | $37,500 (150% × $25k) |

---

## Persistence

### Local Mode (default)

State files are stored as JSON in `WORKFLOW_STATE_DIR` (default: `.local/state/`).
Audit logs are stored in `WORKFLOW_STATE_DIR/audit/` as append-only JSONL files.

```bash
.local/state/
  wf-abc123.json          # Mutable state
  audit/
    wf-abc123.jsonl       # Immutable event log
```

### Firestore Mode (optional-integration)

Set `WORKFLOW_STATE_BACKEND=firestore` and ensure:
- `GOOGLE_CLOUD_PROJECT` is set
- Firestore is in Native mode
- Service account has `roles/datastore.user`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/workflows/replenishment` | Create a new workflow |
| `GET` | `/workflows/pending` | List workflows awaiting approval |
| `GET` | `/workflows/{id}` | Get workflow status |
| `POST` | `/workflows/{id}/approve` | Approve a paused workflow |
| `POST` | `/workflows/{id}/reject` | Reject a paused workflow |
| `POST` | `/workflows/{id}/resume` | Resume an approved workflow |

---

## Replayability

The audit log (`AuditLogger`) is append-only and separate from the mutable state store.
To debug or reconstruct a workflow's history:

```python
from app.workflows.audit_log import AuditLogger, reconstruct_state_from_events

audit = AuditLogger()
events = audit.read_all("wf-abc123")
summary = reconstruct_state_from_events(events)
timeline = audit.render_timeline("wf-abc123")
```

---

## Quick Demo

```bash
make demo-workflow
```

Expected output:
```
Workflow ID: wf-abc123xxxx
Status: COMPLETED
Approval required: False
Proposed total: $3,610.00
```

For high-value orders:
```
Status: PAUSED_FOR_APPROVAL
Approval required: True
  → Approving...
Final status: COMPLETED
Order ID: po-xxxxxxxxxx
```
