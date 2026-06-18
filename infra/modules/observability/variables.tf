variable "project_id" { type = string }
variable "name" {
  type    = string
  default = "ai-stt"
}
variable "notification_email" {
  type        = string
  description = "Email channel for alert policies"
}
variable "dlq_subscription_id" {
  type        = string
  description = "DLQ inspector subscription ID — alerts when unacked messages > 0"
}
variable "cloud_sql_instance" {
  type        = string
  description = "Cloud SQL instance name (e.g. ai-stt-asia-east1)"
}
variable "api_service_names" {
  type        = list(string)
  description = "Cloud Run API service names to monitor (one per region)"
}
