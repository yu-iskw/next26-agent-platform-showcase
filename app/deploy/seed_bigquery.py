from __future__ import annotations

import pathlib

from google.cloud import bigquery

from app.tools.config import settings

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATASETS_DIR = ROOT / "datasets"


def load_csv(
    client: bigquery.Client,
    table_id: str,
    csv_path: pathlib.Path,
    schema: list[bigquery.SchemaField],
) -> None:
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=False,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with csv_path.open("rb") as f:
        load_job = client.load_table_from_file(f, table_id, job_config=job_config)
    load_job.result()


def main() -> None:
    client = bigquery.Client(project=settings.project_id)
    dataset_id = f"{settings.project_id}.{settings.bq_dataset}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = settings.location
    client.create_dataset(dataset, exists_ok=True)

    products_schema = [
        bigquery.SchemaField("product_id", "STRING"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("inventory_on_hand", "INT64"),
        bigquery.SchemaField("reorder_point", "INT64"),
        bigquery.SchemaField("preferred_supplier", "STRING"),
        bigquery.SchemaField("unit_cost_usd", "FLOAT64"),
    ]
    sales_schema = [
        bigquery.SchemaField("month", "STRING"),
        bigquery.SchemaField("product_id", "STRING"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("quantity", "INT64"),
        bigquery.SchemaField("revenue_usd", "FLOAT64"),
    ]

    load_csv(
        client,
        f"{dataset_id}.{settings.bq_products_table}",
        DATASETS_DIR / "products.csv",
        products_schema,
    )
    load_csv(
        client,
        f"{dataset_id}.{settings.bq_sales_table}",
        DATASETS_DIR / "sales.csv",
        sales_schema,
    )
    print(f"Seeded dataset {dataset_id}")


if __name__ == "__main__":
    main()
