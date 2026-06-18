locals {
  topic_set = toset(concat(var.topics, [var.dlq_topic]))
}

resource "google_pubsub_topic" "topic" {
  for_each = local.topic_set
  project  = var.project_id
  name     = each.value

  message_retention_duration = var.message_retention_duration
}

resource "google_pubsub_subscription" "push" {
  for_each = var.push_subscriptions

  project = var.project_id
  name    = each.key
  topic   = google_pubsub_topic.topic[each.value.topic].name

  ack_deadline_seconds         = var.ack_deadline_seconds
  message_retention_duration   = var.message_retention_duration
  enable_message_ordering      = false
  enable_exactly_once_delivery = false

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.topic[var.dlq_topic].id
    max_delivery_attempts = var.max_delivery_attempts
  }

  push_config {
    push_endpoint = each.value.push_endpoint
    oidc_token {
      service_account_email = each.value.invoker_service_account
      # leave audience unset → Pub/Sub uses push_endpoint as audience
    }
  }
}

# Pull subscription for operators to drain/inspect the DLQ.
resource "google_pubsub_subscription" "dlq_inspector" {
  project = var.project_id
  name    = "${var.dlq_topic}-inspector"
  topic   = google_pubsub_topic.topic[var.dlq_topic].name

  ack_deadline_seconds         = 60
  message_retention_duration   = "1209600s" # 14 days
  enable_exactly_once_delivery = true
}
