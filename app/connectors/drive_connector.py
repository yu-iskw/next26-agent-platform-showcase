"""Drive/Docs connector implementations.

MockDriveConnector     — runnable-now, no credentials
WorkspaceDriveConnector — optional-integration, requires ENABLE_WORKSPACE_CONNECTORS=true
                          and Google Workspace API credentials.

See docs/workspace-connectors.md for setup instructions.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.connectors.base import WORKSPACE_CONNECTORS_ENABLED, DriveConnector

_log = logging.getLogger("retailops.connectors.drive")


class MockDriveConnector(DriveConnector):
    """In-memory mock Drive connector for local development and CI.

    Returns synthetic documents that mirror the kinds of policy/SOP docs
    a real Workspace integration would retrieve.

    Status: runnable-now
    """

    _MOCK_DOCS: ClassVar[dict[str, dict[str, Any]]] = {
        "sop-reorder-001": {
            "id": "sop-reorder-001",
            "name": "Replenishment SOP v2.3",
            "mimeType": "application/vnd.google-apps.document",
            "content": (
                "Replenishment Standard Operating Procedure\n\n"
                "1. Check current stock against reorder point.\n"
                "2. Generate reorder recommendation using 1.25x safety multiplier.\n"
                "3. Orders above $25,000 require Finance approval within 24 hours.\n"
                "4. VIP suppliers get priority allocation in Q4.\n"
                "5. All orders above $100,000 require VP sign-off."
            ),
        },
        "policy-supplier-001": {
            "id": "policy-supplier-001",
            "name": "Supplier Policy FY2026",
            "mimeType": "application/vnd.google-apps.document",
            "content": (
                "Supplier Policy FY2026\n\n"
                "Preferred suppliers: GlobalSupply, AlpineGear, TechPack.\n"
                "Single-source orders above $50,000 require dual approval.\n"
                "Volume discounts apply at 100+ and 500+ unit thresholds."
            ),
        },
    }

    def get_document(self, doc_id: str) -> dict[str, Any]:
        doc = self._MOCK_DOCS.get(doc_id)
        if doc is None:
            return {"error": f"Document {doc_id!r} not found in mock store"}
        return doc

    def search_documents(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        q = query.lower()
        results = [d for d in self._MOCK_DOCS.values() if q in d["name"].lower() or q in d["content"].lower()]
        return results[:max_results]


class WorkspaceDriveConnector(DriveConnector):
    """Real Google Drive connector using the googleapis Python SDK.

    Status: optional-integration

    Prerequisites:
      - ENABLE_WORKSPACE_CONNECTORS=true
      - GOOGLE_APPLICATION_CREDENTIALS or user ADC with Drive scope
      - `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`

    See docs/workspace-connectors.md.
    """

    def __init__(self) -> None:
        if not WORKSPACE_CONNECTORS_ENABLED:
            raise RuntimeError(
                "WorkspaceDriveConnector requires ENABLE_WORKSPACE_CONNECTORS=true. "
                "Use MockDriveConnector for local development."
            )
        try:
            from google.auth import default  # type: ignore[import]
            from googleapiclient.discovery import build  # type: ignore[import]

            creds, _ = default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
            self._service = build("drive", "v3", credentials=creds)
            _log.info("WorkspaceDriveConnector initialized")
        except ImportError:
            raise RuntimeError(
                "google-api-python-client is not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2"
            ) from None

    def get_document(self, doc_id: str) -> dict[str, Any]:
        meta = self._service.files().get(fileId=doc_id, fields="id,name,mimeType").execute()
        content = self._service.files().export(fileId=doc_id, mimeType="text/plain").execute().decode("utf-8")
        return {**meta, "content": content}

    def search_documents(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        results = (
            self._service.files()
            .list(q=f"fullText contains '{query}'", pageSize=max_results, fields="files(id,name,mimeType)")
            .execute()
        )
        return results.get("files", [])


def get_drive_connector() -> DriveConnector:
    """Return the appropriate Drive connector based on ENABLE_WORKSPACE_CONNECTORS."""
    if WORKSPACE_CONNECTORS_ENABLED:
        return WorkspaceDriveConnector()
    return MockDriveConnector()
