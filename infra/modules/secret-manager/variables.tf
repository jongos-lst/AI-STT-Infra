variable "project_id" { type = string }

variable "secrets" {
  description = <<-EOT
    Secrets to create. Set initial_value=null to leave creation to a human;
    the resource still gets created so IAM bindings work. Update later via
    `gcloud secrets versions add`.
  EOT
  type = map(object({
    initial_value = optional(string)
    accessors     = optional(list(string), []) # service-account emails
  }))
}

variable "replication" {
  type        = string
  default     = "automatic"
  description = "automatic or user-managed"
}
