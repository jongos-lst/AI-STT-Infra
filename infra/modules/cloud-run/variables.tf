variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "image" {
  type        = string
  description = "Container image, e.g. asia-east1-docker.pkg.dev/<proj>/ai-stt/api:<tag>"
}
variable "command" {
  type    = list(string)
  default = null
}
variable "service_account_email" { type = string }
variable "vpc_connector" { type = string }
variable "min_instances" {
  type    = number
  default = 0
}
variable "max_instances" {
  type    = number
  default = 100
}
variable "concurrency" {
  type    = number
  default = 80
}
variable "cpu" {
  type    = string
  default = "1"
}
variable "memory" {
  type    = string
  default = "512Mi"
}
variable "timeout_seconds" {
  type    = number
  default = 300
}
variable "env" {
  description = "Plain environment variables"
  type        = map(string)
  default     = {}
}
variable "secret_env" {
  description = "Env vars sourced from Secret Manager secrets (name → secret_id)"
  type        = map(string)
  default     = {}
}
variable "ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}
variable "allow_unauthenticated" {
  type        = bool
  default     = false
  description = "Public-facing? Workers/Internal services should stay false."
}
variable "invoker_members" {
  description = "Additional members (eg. SA emails) granted run.invoker"
  type        = list(string)
  default     = []
}
variable "labels" {
  type    = map(string)
  default = {}
}
