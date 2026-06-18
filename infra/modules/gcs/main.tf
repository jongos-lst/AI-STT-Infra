locals {
  buckets = {
    audio = {
      lifecycle_age           = var.audio_lifecycle_days
      lifecycle_storage_class = "COLDLINE"
    }
    transcripts = {
      lifecycle_age           = var.transcripts_lifecycle_days
      lifecycle_storage_class = "NEARLINE"
    }
  }
}

resource "google_storage_bucket" "bucket" {
  for_each                    = local.buckets
  project                     = var.project_id
  name                        = "${var.name_prefix}-${each.key}"
  location                    = var.location
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = var.uniform_access
  public_access_prevention    = "enforced"

  versioning { enabled = true }

  lifecycle_rule {
    condition { age = each.value.lifecycle_age }
    action {
      type          = "SetStorageClass"
      storage_class = each.value.lifecycle_storage_class
    }
  }

  # Older non-current versions cleaned up.
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action { type = "Delete" }
  }

  dynamic "cors" {
    for_each = length(var.cors_origins) > 0 ? [1] : []
    content {
      origin          = var.cors_origins
      method          = ["GET", "PUT", "POST", "HEAD", "OPTIONS"]
      response_header = ["Content-Type", "X-Goog-Content-Length-Range", "X-Goog-Resumable", "Authorization"]
      max_age_seconds = 3600
    }
  }
}
