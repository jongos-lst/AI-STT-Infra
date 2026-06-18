# One-shot bootstrap: state bucket + Artifact Registry + GitHub OIDC.
# Runs with local state (no backend block) because the state bucket doesn't
# exist yet — that's what this apply creates.

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "serviceusage.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate" {
  project                     = var.project_id
  name                        = var.state_bucket_name
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning { enabled = true }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
      with_state         = "ARCHIVED"
    }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

module "artifact_registry" {
  source     = "../../modules/artifact-registry"
  project_id = var.project_id
  location   = var.region

  depends_on = [google_project_service.apis]
}

module "github_oidc" {
  source       = "../../modules/github-oidc"
  project_id   = var.project_id
  github_owner = var.github_owner
  github_repo  = var.github_repo

  depends_on = [google_project_service.apis]
}

# Let the deployer push to the AR repo.
resource "google_artifact_registry_repository_iam_member" "deployer_writer" {
  project    = var.project_id
  location   = var.region
  repository = "ai-stt"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${module.github_oidc.deployer_email}"
  depends_on = [module.artifact_registry]
}
