variable "project_id" { type = string }
variable "name" {
  type    = string
  default = "ai-stt"
}

variable "topics" {
  type        = list(string)
  description = "Application topics (DLQ is created separately)"
  default     = ["stt.requested", "llm.requested"]
}

variable "dlq_topic" {
  type    = string
  default = "tasks.dlq"
}

variable "push_subscriptions" {
  description = <<-EOT
    Push subscription specs.
      key  = subscription name
      value:
        topic            = topic to subscribe to (must be in var.topics)
        push_endpoint    = HTTPS URL of the worker (Cloud Run)
        invoker_service_account = SA email used to sign OIDC tokens for push
  EOT
  type = map(object({
    topic                   = string
    push_endpoint           = string
    invoker_service_account = string
  }))
  default = {}
}

variable "ack_deadline_seconds" {
  type    = number
  default = 60
}

variable "max_delivery_attempts" {
  type    = number
  default = 5
}

variable "message_retention_duration" {
  type    = string
  default = "604800s" # 7 days
}
