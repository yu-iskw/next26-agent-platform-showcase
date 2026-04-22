"""RetailOps Tool API — FastAPI service exposing commerce operations and durable workflows.

Endpoints (original):
  POST /purchase-orders
  GET  /purchase-orders/{order_id}
  POST /approvals
  GET  /healthz

Endpoints (new — Workstream A):
  POST /workflows/replenishment
  GET  /workflows/{workflow_id}
  POST /workflows/{workflow_id}/approve
  POST /workflows/{workflow_id}/reject
  POST /workflows/{workflow_id}/resume
  GET  /workflows/pending

Status: runnable-now (all endpoints work without cloud credentials in local mode)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

app = FastAPI(title="RetailOps Tool API", version="0.2.0")
_firestore_client: Any = None
APPROVAL_THRESHOLD_USD = 25_000
_log = logging.getLogger("retailops_tool_api")

# ---------------------------------------------------------------------------
# Workflow engine — lazy import so the service still starts without the app/
# package on a minimal Dockerfile path; full path enabled when sys.path set.
# ---------------------------------------------------------------------------


def _get_workflow_engine() -> Any:
    try:
        from app.workflows.order_replenishment import ReplenishmentWorkflowEngine

        return ReplenishmentWorkflowEngine()
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def correlation_logging_middleware(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    traceparent = request.headers.get("traceparent", "")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    _log.info(
        "request path=%s method=%s request_id=%s traceparent=%s",
        request.url.path,
        request.method,
        request_id,
        traceparent or "-",
    )
    return response


# ---------------------------------------------------------------------------
# Firestore helpers (existing)
# ---------------------------------------------------------------------------


def db() -> Any:
    global _firestore_client
    if _firestore_client is None:
        try:
            from google.cloud.firestore_v1 import Client

            _firestore_client = Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        except Exception as exc:
            _log.warning("Firestore unavailable (%s); orders will not be persisted to Firestore.", exc)
            _firestore_client = _InMemoryStore()
    return _firestore_client


class _InMemoryStore:
    """Local fallback when Firestore is not configured (dev / CI mode)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _InMemoryCollection:
        if name not in self._data:
            self._data[name] = {}
        return _InMemoryCollection(self._data[name])


class _InMemoryCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _InMemoryDocument:
        return _InMemoryDocument(self._store, doc_id)


class _InMemoryDocument:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self._id = doc_id

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._id] = data

    def get(self) -> _InMemorySnapshot:
        return _InMemorySnapshot(self._store.get(self._id))

    def delete(self) -> None:
        self._store.pop(self._id, None)


class _InMemorySnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PurchaseOrderRequest(BaseModel):
    product_id: str
    units: int = Field(gt=0)
    requester: str = "agent"


class ApprovalRequest(BaseModel):
    order_id: str
    reason: str


class WorkflowCreateRequest(BaseModel):
    product_id: str
    product_name: str = ""
    requester: str = "agent"
    risk_tolerance: str = "medium"
    current_stock: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    estimated_unit_cost_usd: float = Field(default=120.0, gt=0)


class WorkflowApprovalRequest(BaseModel):
    approver: str = "api-user"
    notes: str = ""


class WorkflowRejectionRequest(BaseModel):
    approver: str = "api-user"
    notes: str = ""


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": "0.2.0"}


# ---------------------------------------------------------------------------
# Purchase orders (existing endpoints — preserved)
# ---------------------------------------------------------------------------


@app.post("/purchase-orders")
def create_purchase_order(req: PurchaseOrderRequest) -> dict:
    order_id = f"po-{uuid.uuid4().hex[:10]}"
    estimated_unit_cost = 120.0
    total_cost = round(req.units * estimated_unit_cost, 2)
    approval_required = total_cost >= APPROVAL_THRESHOLD_USD
    doc = {
        "order_id": order_id,
        "product_id": req.product_id,
        "units": req.units,
        "requester": req.requester,
        "total_cost_usd": total_cost,
        "approval_required": approval_required,
        "status": "PENDING_APPROVAL" if approval_required else "CREATED",
        "created_at": datetime.now(UTC).isoformat(),
    }
    db().collection("purchase_orders").document(order_id).set(doc)
    return doc


@app.get("/purchase-orders/{order_id}")
def get_purchase_order(order_id: str) -> dict[str, Any]:
    snap = db().collection("purchase_orders").document(order_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    payload = snap.to_dict()
    if payload is None:
        raise HTTPException(status_code=500, detail=f"Order {order_id} has no payload")
    return cast(dict[str, Any], payload)


@app.post("/approvals")
def create_approval(req: ApprovalRequest) -> dict:
    approval_id = f"apr-{uuid.uuid4().hex[:10]}"
    doc = {
        "approval_id": approval_id,
        "order_id": req.order_id,
        "reason": req.reason,
        "status": "SUBMITTED",
        "created_at": datetime.now(UTC).isoformat(),
    }
    db().collection("approvals").document(approval_id).set(doc)
    return doc


# ---------------------------------------------------------------------------
# Workflow endpoints (Workstream A — new)
# ---------------------------------------------------------------------------


def _engine_or_503() -> Any:
    engine = _get_workflow_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workflow engine unavailable. "
                "Ensure the app/ package is on PYTHONPATH when running the tool API. "
                "See docs/workflow-state-model.md."
            ),
        )
    return engine


@app.post("/workflows/replenishment", summary="Create a durable replenishment workflow")
def create_replenishment_workflow(req: WorkflowCreateRequest) -> dict[str, Any]:
    """Create, advance, and return a new replenishment workflow.

    If the proposed order exceeds the approval threshold the workflow is paused;
    poll ``GET /workflows/{workflow_id}`` and then call the approve/reject endpoints.
    """
    engine = _engine_or_503()
    try:
        state = engine.create_workflow(
            product_id=req.product_id,
            product_name=req.product_name,
            requester=req.requester,
            risk_tolerance=req.risk_tolerance,
        )
        state = engine.compute_recommendation(
            state.workflow_id,
            current_stock=req.current_stock,
            reorder_point=req.reorder_point,
            estimated_unit_cost_usd=req.estimated_unit_cost_usd,
        )
        state = engine.propose_order(state.workflow_id)
        state = engine.advance(state.workflow_id)
        return engine.get_status(state.workflow_id)
    except Exception as exc:
        _log.error("Failed to create workflow: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/workflows/pending", summary="List workflows awaiting approval")
def list_pending_workflows() -> dict[str, Any]:
    engine = _engine_or_503()
    pending = engine.list_pending()
    return {"count": len(pending), "pending": pending}


@app.get("/workflows/{workflow_id}", summary="Get workflow status")
def get_workflow(workflow_id: str) -> dict[str, Any]:
    engine = _engine_or_503()
    try:
        return engine.get_status(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found") from None


@app.post("/workflows/{workflow_id}/approve", summary="Approve a paused workflow")
def approve_workflow(workflow_id: str, req: WorkflowApprovalRequest) -> dict[str, Any]:
    """Approve and finalize an order that was paused for human review."""
    engine = _engine_or_503()
    from app.workflows.state_models import ApprovalDecision, ApprovalStatus

    decision = ApprovalDecision(
        workflow_id=workflow_id,
        approver=req.approver,
        decision=ApprovalStatus.APPROVED,
        notes=req.notes,
    )
    try:
        engine.apply_approval(workflow_id, decision)
        engine.finalize(workflow_id)
        return engine.get_status(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/workflows/{workflow_id}/reject", summary="Reject a paused workflow")
def reject_workflow(workflow_id: str, req: WorkflowRejectionRequest) -> dict[str, Any]:
    """Reject an order that was paused for human review."""
    engine = _engine_or_503()
    from app.workflows.state_models import ApprovalDecision, ApprovalStatus

    decision = ApprovalDecision(
        workflow_id=workflow_id,
        approver=req.approver,
        decision=ApprovalStatus.REJECTED,
        notes=req.notes,
    )
    try:
        engine.apply_approval(workflow_id, decision)
        return engine.get_status(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/workflows/{workflow_id}/resume", summary="Resume an approved workflow")
def resume_workflow(workflow_id: str) -> dict[str, Any]:
    """Resume a workflow that has been approved but not yet finalized."""
    engine = _engine_or_503()
    try:
        from app.workflows.resume_handlers import resume_after_approval
        from app.workflows.state_store import get_default_state_store

        store = get_default_state_store()
        resume_after_approval(workflow_id, store)
        engine.finalize(workflow_id)
        return engine.get_status(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
