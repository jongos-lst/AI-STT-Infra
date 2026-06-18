output "repo_id" { value = google_artifact_registry_repository.repo.id }
output "repo_path" {
  description = "use as: <location>-docker.pkg.dev/<project>/<repo>/<image>:<tag>"
  value       = "${google_artifact_registry_repository.repo.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}
