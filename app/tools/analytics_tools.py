from __future__ import annotations

from typing import Any

from google.cloud import bigquery

from .config import settings

APPROVAL_THRESHOLD_USD = 25_000


def _client() -> bigquery.Client:
    return bigquery.Client(project=settings.project_id)


def _table(table_name: str) -> str:
    return f"{settings.project_id}.{settings.bq_dataset}.{table_name}"


def get_top_products(limit: int = 5) -> list[dict[str, Any]]:
    """Return the top-selling products in the demo warehouse."""
    query = f"""
    SELECT
      product_id,
      product_name,
      category,
      SUM(quantity) AS total_units,
      SUM(revenue_usd) AS total_revenue_usd
    FROM `{_table(settings.bq_sales_table)}`
    GROUP BY product_id, product_name, category
    ORDER BY total_units DESC, total_revenue_usd DESC
    LIMIT @limit
    """  # noqa: S608  # nosec B608
    job = _client().query(
        query,
        job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]),
    )
    return [dict(r.items()) for r in job.result()]


def get_product_inventory(product_name: str) -> list[dict[str, Any]]:
    """Look up inventory and reorder data for a product by partial name."""
    query = f"""
    SELECT
      product_id,
      product_name,
      category,
      inventory_on_hand,
      reorder_point,
      preferred_supplier,
      unit_cost_usd
    FROM `{_table(settings.bq_products_table)}`
    WHERE LOWER(product_name) LIKE LOWER(@needle)
    ORDER BY inventory_on_hand ASC
    """  # noqa: S608  # nosec B608
    job = _client().query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("needle", "STRING", f"%{product_name}%")]
        ),
    )
    return [dict(r.items()) for r in job.result()]


def summarize_sales_trend(category: str) -> list[dict[str, Any]]:
    """Summarize recent sales by month for a given category."""
    query = f"""
    SELECT
      month,
      category,
      SUM(quantity) AS total_units,
      ROUND(SUM(revenue_usd), 2) AS revenue_usd
    FROM `{_table(settings.bq_sales_table)}`
    WHERE LOWER(category) = LOWER(@category)
    GROUP BY month, category
    ORDER BY month
    """  # noqa: S608  # nosec B608
    job = _client().query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("category", "STRING", category)]
        ),
    )
    return [dict(r.items()) for r in job.result()]


def recommend_reorder(product_name: str, multiplier: float = 1.25) -> dict[str, Any]:
    """Create a simple reorder recommendation based on recent demand and current stock."""
    query = f"""
    WITH sales AS (
      SELECT product_id, product_name, AVG(quantity) AS avg_monthly_qty
      FROM `{_table(settings.bq_sales_table)}`
      WHERE LOWER(product_name) LIKE LOWER(@needle)
      GROUP BY product_id, product_name
    )
    SELECT
      p.product_id,
      p.product_name,
      p.inventory_on_hand,
      p.reorder_point,
      p.unit_cost_usd,
      p.preferred_supplier,
      s.avg_monthly_qty
    FROM `{_table(settings.bq_products_table)}` p
    JOIN sales s USING (product_id, product_name)
    WHERE LOWER(p.product_name) LIKE LOWER(@needle)
    LIMIT 1
    """  # noqa: S608  # nosec B608
    job = _client().query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("needle", "STRING", f"%{product_name}%")]
        ),
    )
    rows = [dict(r.items()) for r in job.result()]
    if not rows:
        return {"error": f"No product matched: {product_name}"}
    row = rows[0]
    suggested_units = max(int(row["avg_monthly_qty"] * multiplier), int(row["reorder_point"]))
    estimated_cost = round(suggested_units * row["unit_cost_usd"], 2)
    approval_required = estimated_cost >= APPROVAL_THRESHOLD_USD
    return {
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "inventory_on_hand": row["inventory_on_hand"],
        "reorder_point": row["reorder_point"],
        "avg_monthly_qty": row["avg_monthly_qty"],
        "suggested_reorder_units": suggested_units,
        "estimated_cost_usd": estimated_cost,
        "preferred_supplier": row["preferred_supplier"],
        "approval_required": approval_required,
    }
