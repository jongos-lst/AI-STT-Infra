variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "asia-east1"
}
variable "host" {
  type        = string
  description = "Public host, e.g. stg.ai-stt.example.com"
}
variable "image_tag" {
  type        = string
  description = "Container tag to deploy; overridden by CI on each apply"
  default     = "latest"
}
variable "artifact_repo" {
  type        = string
  description = "Artifact Registry path: <region>-docker.pkg.dev/<proj>/ai-stt"
}
variable "notification_email" { type = string }
