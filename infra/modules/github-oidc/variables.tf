variable "project_id" { type = string }
variable "pool_id" {
  type    = string
  default = "github-actions"
}
variable "provider_id" {
  type    = string
  default = "github"
}
variable "github_owner" { type = string }
variable "github_repo" { type = string }

variable "deployer_account_id" {
  type    = string
  default = "gha-deployer"
}
variable "deployer_roles" {
  type        = list(string)
  description = "Project roles granted to the deployer SA"
  default = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/storage.admin",
    "roles/iam.serviceAccountUser",
    "roles/cloudsql.client",
    "roles/secretmanager.admin",
    "roles/pubsub.admin",
    "roles/compute.networkAdmin",
    "roles/compute.securityAdmin",
    "roles/monitoring.admin",
    "roles/logging.admin",
  ]
}
