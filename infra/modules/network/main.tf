resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "subnet" {
  for_each      = toset(var.regions)
  project       = var.project_id
  name          = "${var.name}-subnet-${each.value}"
  region        = each.value
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.subnet_cidrs[each.value]

  private_ip_google_access = true
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Serverless VPC connector for Cloud Run → Cloud SQL private IP.
resource "google_vpc_access_connector" "connector" {
  for_each       = toset(var.regions)
  project        = var.project_id
  name           = "${var.name}-conn-${each.value}"
  region         = each.value
  ip_cidr_range  = var.connector_cidrs[each.value]
  network        = google_compute_network.vpc.name
  min_throughput = 200
  max_throughput = 1000
}

# Reserved range for private service connection (Cloud SQL).
resource "google_compute_global_address" "private_ip" {
  project       = var.project_id
  name          = "${var.name}-private-svc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}
