"""Calendar connector implementations.

MockCalendarConnector     — runnable-now
WorkspaceCalendarConnector — optional-integration

Status: runnable-now (mock)
         optional-integration (real Calendar API)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.connectors.base import WORKSPACE_CONNECTORS_ENABLED, CalendarConnector

_log = logging.getLogger("retailops.connectors.calendar")


class MockCalendarConnector(CalendarConnector):
    """In-memory mock Calendar connector.

    Status: runnable-now
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = [
            {
                "id": "evt-001",
                "summary": "Supplier Review Meeting",
                "start": {"dateTime": "2026-04-23T10:00:00Z"},
                "end": {"dateTime": "2026-04-23T11:00:00Z"},
                "attendees": ["procurement@retailops.example", "orders@globalsupply.example"],
            }
        ]

    def list_events(self, _calendar_id: str = "primary", max_results: int = 10) -> list[dict[str, Any]]:
        return self._events[:max_results]

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: list[str] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        import uuid

        event: dict[str, Any] = {
            "id": f"evt-{uuid.uuid4().hex[:8]}",
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "description": description,
            "attendees": attendees or [],
            "created": datetime.now(UTC).isoformat(),
        }
        self._events.append(event)
        _log.info("Mock calendar event created: %s", summary)
        return event

    def schedule_approval_meeting(
        self,
        workflow_id: str,
        approver_email: str,
        requester_email: str = "agent@retailops.example",
    ) -> dict[str, Any]:
        """Convenience: schedule an approval review meeting for a paused workflow."""
        start = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        end = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
        return self.create_event(
            summary=f"Approval Review: Workflow {workflow_id}",
            start_time=start,
            end_time=end,
            attendees=[approver_email, requester_email],
            description=f"Replenishment workflow {workflow_id} requires approval. Please review before the meeting.",
        )


class WorkspaceCalendarConnector(CalendarConnector):
    """Real Google Calendar connector.

    Status: optional-integration

    Prerequisites:
      - ENABLE_WORKSPACE_CONNECTORS=true
      - GOOGLE_APPLICATION_CREDENTIALS with Calendar scope
    """

    def __init__(self) -> None:
        if not WORKSPACE_CONNECTORS_ENABLED:
            raise RuntimeError("WorkspaceCalendarConnector requires ENABLE_WORKSPACE_CONNECTORS=true.")
        raise NotImplementedError("WorkspaceCalendarConnector is a scaffold. See docs/workspace-connectors.md.")

    def list_events(self, calendar_id: str = "primary", max_results: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError

    def create_event(
        self, summary: str, start_time: str, end_time: str, attendees: list[str] | None = None, description: str = ""
    ) -> dict[str, Any]:
        raise NotImplementedError


def get_calendar_connector() -> CalendarConnector:
    if WORKSPACE_CONNECTORS_ENABLED:
        return WorkspaceCalendarConnector()
    return MockCalendarConnector()
