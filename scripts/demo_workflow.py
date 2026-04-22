"""Local workflow demo — runs without cloud credentials."""

import os

os.environ.setdefault("WORKFLOW_STATE_DIR", ".local/state")

from app.workflows.order_replenishment import ReplenishmentWorkflowEngine
from app.workflows.state_models import ApprovalDecision, ApprovalStatus

engine = ReplenishmentWorkflowEngine()
state = engine.create_workflow(
    "prod-001",
    product_name="Trail Backpack Pro",
    risk_tolerance="medium",
)
state = engine.compute_recommendation(
    state.workflow_id,
    current_stock=42,
    reorder_point=80,
    estimated_unit_cost_usd=95.0,
)
state = engine.propose_order(state.workflow_id)
state = engine.advance(state.workflow_id)

print("Workflow ID:", state.workflow_id)
print("Status:", state.status.value)
print("Approval required:", state.approval_required)
print(f"Proposed total: ${state.proposed_total_cost_usd:.2f}")

if state.approval_required:
    print("  → Approving...")
    decision = ApprovalDecision(
        workflow_id=state.workflow_id,
        approver="demo-user",
        decision=ApprovalStatus.APPROVED,
        notes="Demo approval",
    )
    engine.apply_approval(state.workflow_id, decision)
    state = engine.finalize(state.workflow_id)
    print("Final status:", state.status.value)
    print("Order ID:", state.order_id)
