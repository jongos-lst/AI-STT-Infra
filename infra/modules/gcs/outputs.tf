output "buckets" {
  description = "role → bucket name"
  value       = { for k, v in google_storage_bucket.bucket : k => v.name }
}

output "audio_bucket" { value = google_storage_bucket.bucket["audio"].name }
output "transcripts_bucket" { value = google_storage_bucket.bucket["transcripts"].name }
