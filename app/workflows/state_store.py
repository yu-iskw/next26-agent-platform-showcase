"""Workflow state persistence layer.

Status:
  LocalJsonWorkflowStateStore  — runnable-now (no cloud deps)
  FirestoreWorkflowStateStore  — optional-integration (scaffold only; requires Firestore)
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.workflows.state_models import ReplenishmentWorkflowState, WorkflowStatus

_log = logging.getLogger("retailops.workflow.state_store")

_LOCAL_STATE_DIR = Path(os.getenv("WORKFLOW_STATE_DIR", ".local/state"))


class WorkflowStateStore(ABC):
    """Abstract interface for workflow state persistence."""

    @abstractmethod
    def save(self, state: ReplenishmentWorkflowState) -> None: ...

    @abstractmethod
    def load(self, workflow_id: str) -> ReplenishmentWorkflowState | None: ...

    @abstractmethod
    def list_pending(self) -> list[ReplenishmentWorkflowState]: ...

    @abstractmethod
    def delete(self, workflow_id: str) -> bool: ...


class LocalJsonWorkflowStateStore(WorkflowStateStore):
    """File-backed JSON state store.  Suitable for local dev and CI.

    Each workflow is stored as ``<state_dir>/<workflow_id>.json``.
    """

    def __init__(self, state_dir: Path | str | None = None) -> None:
        self._dir = Path(state_dir) if state_dir else _LOCAL_STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, workflow_id: str) -> Path:
        safe = workflow_id.replace("/", "_").replace("..", "_")
        return self._dir / f"{safe}.json"

    def save(self, state: ReplenishmentWorkflowState) -> None:
        path = self._path(state.workflow_id)
        try:
            path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            _log.debug("Saved workflow %s to %s", state.workflow_id, path)
        except OSError as exc:
            _log.error("Failed to save workflow %s: %s", state.workflow_id, exc)
            raise

    def load(self, workflow_id: str) -> ReplenishmentWorkflowState | None:
        path = self._path(workflow_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
            return ReplenishmentWorkflowState.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            _log.error("Corrupted state file %s: %s", path, exc)
            return None

    def list_pending(self) -> list[ReplenishmentWorkflowState]:
        pending_statuses = {WorkflowStatus.PAUSED_FOR_APPROVAL, WorkflowStatus.ESCALATED}
        results: list[ReplenishmentWorkflowState] = []
        for p in sorted(self._dir.glob("wf-*.json")):
            state = self.load(p.stem)
            if state and state.status in pending_statuses:
                results.append(state)
        return results

    def delete(self, workflow_id: str) -> bool:
        path = self._path(workflow_id)
        if path.exists():
            path.unlink()
            return True
        return False


class FirestoreWorkflowStateStore(WorkflowStateStore):
    """Firestore-backed state store.

    Status: optional-integration

    Prerequisites:
      - GOOGLE_CLOUD_PROJECT env var
      - Firestore database in Native mode
      - Service account with roles/datastore.user

    This scaffold mirrors the local store's interface. Enable it by setting
    WORKFLOW_STATE_BACKEND=firestore in your environment.
    """

    COLLECTION = "workflow_states"

    def __init__(self, project: str | None = None) -> None:
        try:
            from google.cloud.firestore_v1 import Client

            self._client = Client(project=project or os.environ.get("GOOGLE_CLOUD_PROJECT"))
            _log.info("FirestoreWorkflowStateStore initialized (project=%s)", project)
        except ImportError:
            raise RuntimeError(
                "google-cloud-firestore is not installed. Install it or use LocalJsonWorkflowStateStore instead."
            ) from None

    def _col(self) -> Any:
        return self._client.collection(self.COLLECTION)

    def save(self, state: ReplenishmentWorkflowState) -> None:
        doc_data = json.loads(state.model_dump_json())
        self._col().document(state.workflow_id).set(doc_data)

    def load(self, workflow_id: str) -> ReplenishmentWorkflowState | None:
        snap = self._col().document(workflow_id).get()
        if not snap.exists:
            return None
        data: dict[str, Any] = snap.to_dict() or {}
        return ReplenishmentWorkflowState.model_validate(data)

    def list_pending(self) -> list[ReplenishmentWorkflowState]:
        pending_statuses = [WorkflowStatus.PAUSED_FOR_APPROVAL.value, WorkflowStatus.ESCALATED.value]
        results: list[ReplenishmentWorkflowState] = []
        for status in pending_statuses:
            docs = self._col().where("status", "==", status).stream()
            for doc in docs:
                data: dict[str, Any] = doc.to_dict() or {}
                results.append(ReplenishmentWorkflowState.model_validate(data))
        return results

    def delete(self, workflow_id: str) -> bool:
        ref = self._col().document(workflow_id)
        snap = ref.get()
        if snap.exists:
            ref.delete()
            return True
        return False


def get_default_state_store() -> WorkflowStateStore:
    """Return state store based on WORKFLOW_STATE_BACKEND env var.

    Values:
      ``local`` (default) — LocalJsonWorkflowStateStore
      ``firestore``        — FirestoreWorkflowStateStore (optional-integration)
    """
    backend = os.getenv("WORKFLOW_STATE_BACKEND", "local").lower()
    if backend == "firestore":
        return FirestoreWorkflowStateStore()
    return LocalJsonWorkflowStateStore()
