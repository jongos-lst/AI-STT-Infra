resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "${var.name} oncall email"
  type         = "email"
  labels       = { email_address = var.notification_email }
}

# Log-based metric: error rate from structured logs (level=ERROR).
resource "google_logging_metric" "errors" {
  project = var.project_id
  name    = "${var.name}/log_errors"
  filter  = "resource.type=\"cloud_run_revision\" AND severity>=ERROR"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "service_name"
      value_type  = "STRING"
      description = "Cloud Run service"
    }
  }
  label_extractors = {
    service_name = "EXTRACT(resource.labels.service_name)"
  }
}

# DLQ depth: any message in the DLQ pages an operator.
resource "google_monitoring_alert_policy" "dlq" {
  project      = var.project_id
  display_name = "${var.name} DLQ has messages"
  combiner     = "OR"

  conditions {
    display_name = "DLQ undelivered > 0"
    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.label.subscription_id=\"${var.dlq_subscription_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  alert_strategy { auto_close = "604800s" }
}

resource "google_monitoring_alert_policy" "api_5xx" {
  project      = var.project_id
  display_name = "${var.name} API 5xx > 1% for 5m"
  combiner     = "OR"

  conditions {
    display_name = "5xx rate"
    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_count\"",
        "resource.type=\"cloud_run_revision\"",
        "metric.label.response_code_class=\"5xx\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      duration        = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.service_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_alert_policy" "cloud_sql_cpu" {
  project      = var.project_id
  display_name = "${var.name} Cloud SQL CPU > 80% for 10m"
  combiner     = "OR"

  conditions {
    display_name = "cpu utilization"
    condition_threshold {
      filter          = "metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\" AND resource.label.database_id=\"${var.project_id}:${var.cloud_sql_instance}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "600s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_dashboard" "main" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "${var.name} — overview"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 6, height = 4
          widget = {
            title = "API request rate by service"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.label.service_name"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 6, width = 6, height = 4
          widget = {
            title = "API 5xx rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" metric.label.response_code_class=\"5xx\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          yPos = 4, width = 6, height = 4
          widget = {
            title = "Pub/Sub backlog (undelivered)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\""
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 6, yPos = 4, width = 6, height = 4
          widget = {
            title = "Cloud SQL CPU"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\""
                  }
                }
              }]
            }
          }
        },
      ]
    }
  })
}
