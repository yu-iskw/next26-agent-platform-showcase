from __future__ import annotations

from typing import Any

from google.cloud import storage

from .config import settings


def list_grounding_documents(prefix: str = "knowledge/") -> list[dict[str, Any]]:
    """List documents available in the staging bucket to ground operational answers."""
    if not settings.staging_bucket.startswith("gs://"):
        return [{"error": "STAGING_BUCKET must be a gs:// bucket URL"}]
    bucket_name = settings.staging_bucket.replace("gs://", "", 1)
    client = storage.Client(project=settings.project_id)
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    return [
        {
            "name": blob.name,
            "size_bytes": blob.size,
            "updated": blob.updated.isoformat() if blob.updated else None,
            "content_type": blob.content_type,
        }
        for blob in blobs
    ]


def upload_demo_note(object_name: str, content: str) -> dict[str, Any]:
    """Upload a small text note into Cloud Storage for grounding experiments."""
    if not settings.staging_bucket.startswith("gs://"):
        return {"error": "STAGING_BUCKET must be a gs:// bucket URL"}
    bucket_name = settings.staging_bucket.replace("gs://", "", 1)
    client = storage.Client(project=settings.project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type="text/plain")
    return {"bucket": bucket_name, "object": object_name, "status": "uploaded"}
