output "lb_ip" { value = module.edge.ip_address }
output "api_url" { value = module.api.url }
output "frontend_url" { value = module.frontend.url }
output "cloud_sql_instance" { value = module.cloud_sql.instance_name }
output "audio_bucket" { value = module.gcs.audio_bucket }
output "dashboard" { value = module.observability.dashboard }
