output "staging_bucket" {
  value = "gs://${google_storage_bucket.staging.name}"
}

output "bq_dataset" {
  value = google_bigquery_dataset.retailops.dataset_id
}

output "agent_runtime_service_account" {
  value = google_service_account.agent_runtime.email
}
