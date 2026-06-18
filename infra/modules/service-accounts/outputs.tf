output "emails" {
  value = { for k, v in google_service_account.sa : k => v.email }
}

output "ids" {
  value = { for k, v in google_service_account.sa : k => v.id }
}
