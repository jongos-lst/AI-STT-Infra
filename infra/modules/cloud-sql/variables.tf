variable "project_id" { type = string }
variable "name" {
  type        = string
  description = "Instance prefix"
  default     = "ai-stt"
}
variable "region" { type = string }
variable "tier" {
  type        = string
  description = "Cloud SQL machine tier"
  default     = "db-custom-2-7680"
}
variable "availability_type" {
  type        = string
  description = "ZONAL (staging) or REGIONAL (prod, HA)"
  default     = "ZONAL"
  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.availability_type)
    error_message = "must be ZONAL or REGIONAL"
  }
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "network_id" {
  type        = string
  description = "VPC network self-link for private IP"
}
variable "private_service_connection" {
  type        = string
  description = "Pass network.private_service_connection so SQL waits for VPC peering"
}
variable "read_replica_regions" {
  type        = list(string)
  default     = []
  description = "Regions to provision cross-region read replicas in"
}
variable "database" {
  type    = string
  default = "ai_stt"
}
variable "app_user" {
  type    = string
  default = "ai_stt_app"
}
