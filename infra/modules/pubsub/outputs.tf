output "topics" {
  description = "topic name → topic resource ID"
  value       = { for k, v in google_pubsub_topic.topic : k => v.id }
}

output "subscriptions" {
  value = { for k, v in google_pubsub_subscription.push : k => v.id }
}

output "dlq_topic" { value = google_pubsub_topic.topic[var.dlq_topic].id }
output "dlq_inspector_subscription" { value = google_pubsub_subscription.dlq_inspector.id }
