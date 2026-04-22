"""Gmail thread connector implementations.

MockGmailConnector     — runnable-now
WorkspaceGmailConnector — optional-integration

Status: runnable-now (mock)
         optional-integration (real Gmail API)
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.connectors.base import WORKSPACE_CONNECTORS_ENABLED, GmailConnector

_log = logging.getLogger("retailops.connectors.gmail")


class MockGmailConnector(GmailConnector):
    """In-memory mock Gmail connector.

    Returns synthetic supplier email threads for demo purposes.

    Status: runnable-now
    """

    _MOCK_THREADS: ClassVar[dict[str, dict[str, Any]]] = {
        "thread-supplier-001": {
            "id": "thread-supplier-001",
            "messages": [
                {
                    "from": "orders@globalsupply.example",
                    "subject": "Re: Q2 Replenishment Order",
                    "body": "We can fulfill 300 units of Trail Backpack Pro at $92/unit with 5% Q2 discount. Lead time: 14 days.",
                    "date": "2026-04-01",
                },
                {
                    "from": "procurement@retailops.example",
                    "subject": "Re: Q2 Replenishment Order",
                    "body": "Can we negotiate to $88/unit for 500+ units?",
                    "date": "2026-04-02",
                },
                {
                    "from": "orders@globalsupply.example",
                    "subject": "Re: Q2 Replenishment Order",
                    "body": "Best we can do is $90/unit at 500 units. Final offer.",
                    "date": "2026-04-03",
                },
            ],
        },
    }

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        thread = self._MOCK_THREADS.get(thread_id)
        if thread is None:
            return {"error": f"Thread {thread_id!r} not found in mock store"}
        return thread

    def search_threads(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        q = query.lower()
        results = []
        for thread in self._MOCK_THREADS.values():
            for msg in thread.get("messages", []):
                if q in msg.get("subject", "").lower() or q in msg.get("body", "").lower():
                    results.append({"id": thread["id"], "snippet": msg["subject"]})
                    break
        return results[:max_results]

    def summarize_thread(self, thread_id: str) -> str:
        thread = self.get_thread(thread_id)
        if "error" in thread:
            return thread["error"]
        messages = thread.get("messages", [])
        if not messages:
            return "No messages in thread."
        # Simple mock summary — in production use an LLM or Gemini summarization
        last = messages[-1]
        return (
            f"Thread has {len(messages)} messages. "
            f"Latest from {last.get('from', 'unknown')} ({last.get('date', '')}): "
            f"{last.get('body', '')[:200]}"
        )


class WorkspaceGmailConnector(GmailConnector):
    """Real Gmail connector using the Gmail API.

    Status: optional-integration

    Prerequisites:
      - ENABLE_WORKSPACE_CONNECTORS=true
      - GOOGLE_APPLICATION_CREDENTIALS or user ADC with Gmail scope
    """

    def __init__(self) -> None:
        if not WORKSPACE_CONNECTORS_ENABLED:
            raise RuntimeError("WorkspaceGmailConnector requires ENABLE_WORKSPACE_CONNECTORS=true.")
        # TODO(optional): initialize Gmail API client
        raise NotImplementedError(
            "WorkspaceGmailConnector is a scaffold. "
            "Implement using gmail API client when ENABLE_WORKSPACE_CONNECTORS=true. "
            "See docs/workspace-connectors.md."
        )

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def search_threads(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError

    def summarize_thread(self, thread_id: str) -> str:
        raise NotImplementedError


def get_gmail_connector() -> GmailConnector:
    if WORKSPACE_CONNECTORS_ENABLED:
        return WorkspaceGmailConnector()
    return MockGmailConnector()
