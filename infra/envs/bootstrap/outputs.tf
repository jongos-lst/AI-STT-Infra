output "state_bucket" { value = google_storage_bucket.tfstate.name }
output "artifact_repo" { value = module.artifact_registry.repo_path }
output "github_actions_inputs" { value = module.github_oidc.github_actions_inputs }
