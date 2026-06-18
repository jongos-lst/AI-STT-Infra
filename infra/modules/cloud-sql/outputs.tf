output "instance_name" { value = google_sql_database_instance.primary.name }
output "connection_name" { value = google_sql_database_instance.primary.connection_name }
output "private_ip" { value = google_sql_database_instance.primary.private_ip_address }
output "database" { value = google_sql_database.db.name }
output "app_user" { value = google_sql_user.app.name }
output "app_password" {
  value     = random_password.app.result
  sensitive = true
}
output "replica_instance_names" { value = { for k, v in google_sql_database_instance.replica : k => v.name } }
