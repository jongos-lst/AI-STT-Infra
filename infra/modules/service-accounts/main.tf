resource "google_service_account" "sa" {
  for_each     = var.service_accounts
  project      = var.project_id
  account_id   = each.key
  display_name = try(each.value.display_name, each.key)
}

locals {
  bindings = flatten([
    for name, spec in var.service_accounts : [
      for role in spec.roles : { name = name, role = role }
    ]
  ])
}

resource "google_project_iam_member" "binding" {
  for_each = { for b in local.bindings : "${b.name}:${b.role}" => b }
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.sa[each.value.name].email}"
}
