output "pool_name" { value = google_iam_workload_identity_pool.pool.name }
output "provider_name" { value = google_iam_workload_identity_pool_provider.github.name }
output "deployer_email" { value = google_service_account.deployer.email }
output "github_actions_inputs" {
  description = "Paste these into the workflow's google-github-actions/auth step."
  value = {
    workload_identity_provider = google_iam_workload_identity_pool_provider.github.name
    service_account            = google_service_account.deployer.email
  }
}
