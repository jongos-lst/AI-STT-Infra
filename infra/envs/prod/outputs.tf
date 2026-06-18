output "lb_ip" { value = module.edge.ip_address }
output "api_urls" { value = { for r, s in module.api : r => s.url } }
output "frontend_urls" { value = { for r, s in module.frontend : r => s.url } }
output "cloud_sql_primary" { value = module.cloud_sql.instance_name }
output "cloud_sql_replicas" { value = module.cloud_sql.replica_instance_names }
output "audio_bucket" { value = module.gcs.audio_bucket }
output "dashboard" { value = module.observability.dashboard }
