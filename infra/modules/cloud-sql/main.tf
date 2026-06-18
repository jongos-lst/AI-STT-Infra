resource "random_password" "app" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "primary" {
  project             = var.project_id
  name                = "${var.name}-${var.region}"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection
  depends_on          = [var.private_service_connection]

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_type         = "PD_SSD"
    disk_size         = 50
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 14
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 2048
      record_application_tags = true
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }
  }
}

resource "google_sql_database" "db" {
  project  = var.project_id
  instance = google_sql_database_instance.primary.name
  name     = var.database
}

resource "google_sql_user" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.primary.name
  name     = var.app_user
  password = random_password.app.result
}

resource "google_sql_database_instance" "replica" {
  for_each             = toset(var.read_replica_regions)
  project              = var.project_id
  name                 = "${var.name}-replica-${each.value}"
  region               = each.value
  database_version     = "POSTGRES_16"
  master_instance_name = google_sql_database_instance.primary.name
  deletion_protection  = var.deletion_protection

  replica_configuration {
    failover_target = false
  }

  settings {
    tier              = var.tier
    availability_type = "ZONAL"
    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }
  }
}
