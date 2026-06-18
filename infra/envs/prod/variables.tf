variable "project_id" { type = string }
variable "primary_region" {
  type    = string
  default = "asia-east1"
}
variable "secondary_region" {
  type    = string
  default = "us-central1"
}
variable "host" { type = string }
variable "image_tag" {
  type    = string
  default = "latest"
}
variable "artifact_repo" { type = string }
variable "notification_email" { type = string }
variable "gcs_dual_region_location" {
  type        = string
  default     = "ASIA"
  description = "GCS dual-region (e.g. ASIA, NAM4, EUR4)"
}
