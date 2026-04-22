"""Local A2A federation demo — runs without cloud credentials."""

from app.a2a.models import A2ATaskRequest
from app.a2a.provider import A2AProvider

provider = A2AProvider(use_mocks=True)

req = A2ATaskRequest(
    intent="finance.order.review",
    payload={"order_id": "po-demo", "total_cost_usd": 30000.0},
)
resp = provider.route(req)
print("Finance decision:", resp.result.get("decision"))

req2 = A2ATaskRequest(
    intent="supplier.quote.request",
    payload={"product_id": "prod-001", "quantity": 200},
)
resp2 = provider.route(req2)
unit_price = resp2.result.get("unit_price_usd", 0)
discount = resp2.result.get("discount_pct", 0)
print(f"Supplier quote: ${unit_price:.2f}/unit (discount={discount}%)")
