resource "google_secret_manager_secret" "secret" {
  for_each  = var.secrets
  project   = var.project_id
  secret_id = each.key

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "initial" {
  for_each    = { for k, v in var.secrets : k => v if try(v.initial_value, null) != null }
  secret      = google_secret_manager_secret.secret[each.key].id
  secret_data = each.value.initial_value
}

locals {
  bindings = flatten([
    for k, v in var.secrets : [
      for sa in try(v.accessors, []) : { secret = k, sa = sa }
    ]
  ])
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each  = { for b in local.bindings : "${b.secret}:${b.sa}" => b }
  project   = var.project_id
  secret_id = google_secret_manager_secret.secret[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa}"
}
