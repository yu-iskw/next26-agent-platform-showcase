# Workspace Connectors

**Status: optional-integration**

> All connector paths are fully optional. Local mock connectors work with no credentials.
> Real connector paths require Google Workspace API credentials and `ENABLE_WORKSPACE_CONNECTORS=true`.

---

## Overview

The `app/connectors/` package provides an interface for Google Workspace integrations:

| Connector | Mock (runnable-now) | Real (optional-integration) |
|---|---|---|
| Drive/Docs retrieval | `MockDriveConnector` | `WorkspaceDriveConnector` |
| Gmail thread summarization | `MockGmailConnector` | `WorkspaceGmailConnector` |
| Calendar scheduling | `MockCalendarConnector` | `WorkspaceCalendarConnector` |

---

## Example Scenarios

### 1. Summarize supplier email thread before approval

```python
from app.connectors.gmail_connector import get_gmail_connector

connector = get_gmail_connector()  # Returns mock by default
summary = connector.summarize_thread("thread-supplier-001")
# → "Thread has 3 messages. Latest from orders@globalsupply.example..."
```

### 2. Fetch policy/SOP doc before creating an order

```python
from app.connectors.drive_connector import get_drive_connector

drive = get_drive_connector()
docs = drive.search_documents("replenishment SOP")
sop = drive.get_document(docs[0]["id"])
print(sop["content"][:200])
```

### 3. Schedule an approval review meeting

```python
from app.connectors.calendar_connector import MockCalendarConnector

cal = MockCalendarConnector()
event = cal.schedule_approval_meeting(
    workflow_id="wf-abc123",
    approver_email="manager@retailops.example",
    requester_email="agent@retailops.example",
)
print(event["summary"])
# → "Approval Review: Workflow wf-abc123"
```

---

## Setup: Real Connectors

1. Set `ENABLE_WORKSPACE_CONNECTORS=true` in `.env`
2. Enable the following APIs in your GCP project:
   ```bash
   gcloud services enable drive.googleapis.com gmail.googleapis.com calendar-json.googleapis.com
   ```
3. Create credentials with the required OAuth scopes:
   - Drive: `https://www.googleapis.com/auth/drive.readonly`
   - Gmail: `https://www.googleapis.com/auth/gmail.readonly`
   - Calendar: `https://www.googleapis.com/auth/calendar`
4. Install the optional SDK:
   ```bash
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```
5. Run `gcloud auth application-default login` with the required scopes

### Rollback

To disable Workspace connectors, set `ENABLE_WORKSPACE_CONNECTORS=false` (the default).
All code paths fall back to mock implementations automatically.

---

## Feature Flag

```bash
# .env
ENABLE_WORKSPACE_CONNECTORS=false   # default — mock connectors
ENABLE_WORKSPACE_CONNECTORS=true    # real Workspace API connectors
```

The flag is read at connector construction time, not at import time, so you can
safely import the connector modules without triggering real API calls.

---

## File Reference

| File | Description |
|---|---|
| `app/connectors/base.py` | Abstract interfaces |
| `app/connectors/drive_connector.py` | Drive mock + real |
| `app/connectors/gmail_connector.py` | Gmail mock + scaffold |
| `app/connectors/calendar_connector.py` | Calendar mock + scaffold |
