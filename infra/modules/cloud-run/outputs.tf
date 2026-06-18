output "service_id" { value = google_cloud_run_v2_service.svc.id }
output "service_name" { value = google_cloud_run_v2_service.svc.name }
output "url" { value = google_cloud_run_v2_service.svc.uri }
output "region" { value = google_cloud_run_v2_service.svc.location }
