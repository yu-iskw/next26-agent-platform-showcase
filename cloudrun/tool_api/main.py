from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from google.cloud.firestore_v1 import Client
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from pydantic import BaseModel, Field
from starlette.responses import Response

app = FastAPI(title="RetailOps Tool API", version="0.1.0")
_firestore_client: Client | None = None
APPROVAL_THRESHOLD_USD = 25_000
_log = logging.getLogger("retailops_tool_api")


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


def db() -> Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return _firestore_client


class PurchaseOrderRequest(BaseModel):
    product_id: str
    units: int = Field(gt=0)
    requester: str = "agent"


class ApprovalRequest(BaseModel):
    order_id: str
    reason: str


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


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
    snap = cast(
        DocumentSnapshot,
        db().collection("purchase_orders").document(order_id).get(),
    )
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
