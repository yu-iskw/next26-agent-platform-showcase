variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "dataset_id" {
  type    = string
  default = "retailops_demo"
}

variable "staging_bucket_name" {
  type    = string
  default = null
}
