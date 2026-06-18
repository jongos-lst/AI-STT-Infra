locals {
  name    = "ai-stt-prod"
  regions = [var.primary_region, var.secondary_region]

  subnet_cidrs = {
    (var.primary_region)   = "10.20.0.0/20"
    (var.secondary_region) = "10.21.0.0/20"
  }
  connector_cidrs = {
    (var.primary_region)   = "10.20.16.0/28"
    (var.secondary_region) = "10.21.16.0/28"
  }
}

module "network" {
  source          = "../../modules/network"
  project_id      = var.project_id
  name            = local.name
  regions         = local.regions
  subnet_cidrs    = local.subnet_cidrs
  connector_cidrs = local.connector_cidrs
}

module "service_accounts" {
  source     = "../../modules/service-accounts"
  project_id = var.project_id
  service_accounts = {
    api = {
      display_name = "API gateway (prod)"
      roles = [
        "roles/cloudsql.client",
        "roles/secretmanager.secretAccessor",
        "roles/pubsub.publisher",
        "roles/storage.objectAdmin",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
      ]
    }
    stt-worker = {
      display_name = "STT worker (prod)"
      roles = [
        "roles/cloudsql.client",
        "roles/secretmanager.secretAccessor",
        "roles/pubsub.publisher",
        "roles/storage.objectAdmin",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
      ]
    }
    llm-worker = {
      display_name = "LLM worker (prod)"
      roles = [
        "roles/cloudsql.client",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
      ]
    }
    outbox = {
      display_name = "Outbox sweeper (prod)"
      roles = [
        "roles/cloudsql.client",
        "roles/pubsub.publisher",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
      ]
    }
    frontend = {
      display_name = "Frontend (prod)"
      roles = [
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
      ]
    }
    pubsub-invoker = {
      display_name = "Pub/Sub push invoker (prod)"
      roles        = []
    }
  }
}

module "cloud_sql" {
  source                     = "../../modules/cloud-sql"
  project_id                 = var.project_id
  name                       = local.name
  region                     = var.primary_region
  tier                       = "db-custom-4-15360"
  availability_type          = "REGIONAL"
  deletion_protection        = true
  read_replica_regions       = [var.secondary_region]
  network_id                 = module.network.network_id
  private_service_connection = module.network.private_service_connection
}

module "gcs" {
  source       = "../../modules/gcs"
  project_id   = var.project_id
  name_prefix  = local.name
  location     = var.gcs_dual_region_location
  cors_origins = ["https://${var.host}"]
}

module "secrets" {
  source     = "../../modules/secret-manager"
  project_id = var.project_id

  secrets = {
    DATABASE_URL = {
      initial_value = "postgresql+asyncpg://${module.cloud_sql.app_user}:${module.cloud_sql.app_password}@${module.cloud_sql.private_ip}:5432/${module.cloud_sql.database}"
      accessors = [
        module.service_accounts.emails["api"],
        module.service_accounts.emails["stt-worker"],
        module.service_accounts.emails["llm-worker"],
        module.service_accounts.emails["outbox"],
      ]
    }
    OPENAI_API_KEY = {
      accessors = [
        module.service_accounts.emails["stt-worker"],
        module.service_accounts.emails["llm-worker"],
      ]
    }
  }
}

# ---------------- compute (one cloud-run module per region per service) ----------------
locals {
  shared_env = {
    APP_ENV                     = "prod"
    LOG_LEVEL                   = "INFO"
    AUTH_DISABLED               = "false"
    GCP_PROJECT_ID              = var.project_id
    GCS_BUCKET_AUDIO            = module.gcs.audio_bucket
    GCS_BUCKET_TRANSCRIPTS      = module.gcs.transcripts_bucket
    PUBSUB_TOPIC_STT            = "stt.requested"
    PUBSUB_TOPIC_LLM            = "llm.requested"
    PUBSUB_TOPIC_DLQ            = "tasks.dlq"
    OTEL_EXPORTER_OTLP_ENDPOINT = ""
    STT_PROVIDER                = "openai-whisper"
    LLM_PROVIDER                = "openai-gpt"
  }
  shared_secret_env = {
    DATABASE_URL   = "DATABASE_URL"
    OPENAI_API_KEY = "OPENAI_API_KEY"
  }
}

module "api" {
  for_each              = toset(local.regions)
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = each.value
  name                  = "ai-stt-api"
  image                 = "${var.artifact_repo}/api:${var.image_tag}"
  service_account_email = module.service_accounts.emails["api"]
  vpc_connector         = module.network.connectors[each.value]
  min_instances         = 2
  max_instances         = 100
  cpu                   = "2"
  memory                = "1Gi"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  env                   = local.shared_env
  secret_env            = local.shared_secret_env
  labels                = { env = "prod", app = "ai-stt", service = "api" }
}

module "stt_worker" {
  for_each              = toset(local.regions)
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = each.value
  name                  = "ai-stt-stt-worker"
  image                 = "${var.artifact_repo}/api:${var.image_tag}"
  command               = ["uvicorn", "app.workers.stt_worker:app", "--host", "0.0.0.0", "--port", "8080"]
  service_account_email = module.service_accounts.emails["stt-worker"]
  vpc_connector         = module.network.connectors[each.value]
  min_instances         = 1
  max_instances         = 50
  cpu                   = "4"
  memory                = "2Gi"
  timeout_seconds       = 900
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_members       = ["serviceAccount:${module.service_accounts.emails["pubsub-invoker"]}"]
  env                   = local.shared_env
  secret_env            = local.shared_secret_env
  labels                = { env = "prod", app = "ai-stt", service = "stt-worker" }
}

module "llm_worker" {
  for_each              = toset(local.regions)
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = each.value
  name                  = "ai-stt-llm-worker"
  image                 = "${var.artifact_repo}/api:${var.image_tag}"
  command               = ["uvicorn", "app.workers.llm_worker:app", "--host", "0.0.0.0", "--port", "8080"]
  service_account_email = module.service_accounts.emails["llm-worker"]
  vpc_connector         = module.network.connectors[each.value]
  min_instances         = 1
  max_instances         = 50
  cpu                   = "2"
  memory                = "1Gi"
  timeout_seconds       = 600
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_members       = ["serviceAccount:${module.service_accounts.emails["pubsub-invoker"]}"]
  env                   = local.shared_env
  secret_env            = local.shared_secret_env
  labels                = { env = "prod", app = "ai-stt", service = "llm-worker" }
}

# Sweeper runs in the primary region only — single writer to the Pub/Sub topic.
module "outbox" {
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = var.primary_region
  name                  = "ai-stt-outbox"
  image                 = "${var.artifact_repo}/api:${var.image_tag}"
  command               = ["python", "-m", "app.workers.outbox_sweeper"]
  service_account_email = module.service_accounts.emails["outbox"]
  vpc_connector         = module.network.connectors[var.primary_region]
  min_instances         = 1
  max_instances         = 1
  cpu                   = "1"
  memory                = "512Mi"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env                   = local.shared_env
  secret_env            = local.shared_secret_env
  labels                = { env = "prod", app = "ai-stt", service = "outbox-sweeper" }
}

module "frontend" {
  for_each              = toset(local.regions)
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = each.value
  name                  = "ai-stt-frontend"
  image                 = "${var.artifact_repo}/frontend:${var.image_tag}"
  service_account_email = module.service_accounts.emails["frontend"]
  vpc_connector         = module.network.connectors[each.value]
  min_instances         = 2
  max_instances         = 50
  cpu                   = "1"
  memory                = "512Mi"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  env = {
    NEXT_PUBLIC_API_BASE_URL = "https://${var.host}"
    NEXT_PUBLIC_APP_ENV      = "prod"
  }
  labels = { env = "prod", app = "ai-stt", service = "frontend" }
}

# ---------------- messaging ----------------
# Push subscription targets the primary worker; secondary serves the user/API
# region but workers consume via the same global topic in primary.
module "pubsub" {
  source     = "../../modules/pubsub"
  project_id = var.project_id

  push_subscriptions = {
    stt-worker = {
      topic                   = "stt.requested"
      push_endpoint           = "${module.stt_worker[var.primary_region].url}/_pubsub/stt"
      invoker_service_account = module.service_accounts.emails["pubsub-invoker"]
    }
    llm-worker = {
      topic                   = "llm.requested"
      push_endpoint           = "${module.llm_worker[var.primary_region].url}/_pubsub/llm"
      invoker_service_account = module.service_accounts.emails["pubsub-invoker"]
    }
  }
}

# ---------------- edge ----------------
module "edge" {
  source     = "../../modules/edge"
  project_id = var.project_id
  host       = var.host

  frontend_services = { for r, svc in module.frontend : r => svc.service_name }
  api_services      = { for r, svc in module.api : r => svc.service_name }
}

# ---------------- observability ----------------
module "observability" {
  source              = "../../modules/observability"
  project_id          = var.project_id
  notification_email  = var.notification_email
  dlq_subscription_id = "tasks.dlq-inspector"
  cloud_sql_instance  = module.cloud_sql.instance_name
  api_service_names   = [for r, svc in module.api : svc.service_name]
}
