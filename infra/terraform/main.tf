terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  staging_bucket_name = var.staging_bucket_name != null ? var.staging_bucket_name : "${var.project_id}-retailops-staging"
}

resource "google_project_service" "services" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    # Agent observability: OTLP telemetry ingestion, topology console prerequisites.
    "telemetry.googleapis.com",
    "apphub.googleapis.com",
    "observability.googleapis.com",
    "apptopology.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "staging" {
  name                        = local.staging_bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.services]
}

resource "google_bigquery_dataset" "retailops" {
  dataset_id                 = var.dataset_id
  location                   = var.region
  delete_contents_on_destroy = true
  depends_on                 = [google_project_service.services]
}

resource "google_service_account" "agent_runtime" {
  account_id   = "retailops-agent-runtime"
  display_name = "RetailOps Agent Runtime"
  depends_on   = [google_project_service.services]
}

resource "google_project_iam_member" "agent_runtime_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_runtime_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_runtime_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_runtime_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}
