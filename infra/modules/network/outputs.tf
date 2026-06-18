output "network_id" { value = google_compute_network.vpc.id }
output "network_name" { value = google_compute_network.vpc.name }
output "subnets" { value = { for k, v in google_compute_subnetwork.subnet : k => v.id } }
output "connectors" { value = { for k, v in google_vpc_access_connector.connector : k => v.id } }
output "private_service_connection" { value = google_service_networking_connection.private_vpc.id }
