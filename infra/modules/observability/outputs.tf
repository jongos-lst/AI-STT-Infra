output "notification_channel" { value = google_monitoring_notification_channel.email.id }
output "alerts" {
  value = {
    dlq           = google_monitoring_alert_policy.dlq.id
    api_5xx       = google_monitoring_alert_policy.api_5xx.id
    cloud_sql_cpu = google_monitoring_alert_policy.cloud_sql_cpu.id
  }
}
output "dashboard" { value = google_monitoring_dashboard.main.id }
