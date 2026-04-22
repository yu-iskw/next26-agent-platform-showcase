"""Abstract base classes for enterprise connectors.

All connectors follow the same pattern:
  - abstract interface defined here
  - mock implementation for local/CI mode
  - optional real implementation behind a feature flag (ENABLE_WORKSPACE_CONNECTORS)

Status: runnable-now (mock implementations)
         optional-integration (real Workspace API implementations)

WARNING: Real connector paths require Google Workspace API credentials and
ENABLE_WORKSPACE_CONNECTORS=true. See docs/workspace-connectors.md.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

WORKSPACE_CONNECTORS_ENABLED = os.getenv("ENABLE_WORKSPACE_CONNECTORS", "").lower() in ("1", "true", "yes")


class DriveConnector(ABC):
    """Interface for Google Drive / Docs retrieval."""

    @abstractmethod
    def get_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve a document by Drive file ID."""
        ...

    @abstractmethod
    def search_documents(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search Drive for documents matching a query."""
        ...


class GmailConnector(ABC):
    """Interface for Gmail thread summarization."""

    @abstractmethod
    def get_thread(self, thread_id: str) -> dict[str, Any]:
        """Retrieve a Gmail thread by ID."""
        ...

    @abstractmethod
    def search_threads(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search Gmail for threads matching a query."""
        ...

    @abstractmethod
    def summarize_thread(self, thread_id: str) -> str:
        """Return a plain-text summary of a Gmail thread."""
        ...


class CalendarConnector(ABC):
    """Interface for Google Calendar scheduling."""

    @abstractmethod
    def list_events(self, calendar_id: str = "primary", max_results: int = 10) -> list[dict[str, Any]]:
        """List upcoming calendar events."""
        ...

    @abstractmethod
    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: list[str] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a calendar event."""
        ...
