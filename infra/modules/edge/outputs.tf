output "ip_address" {
  description = "Point your DNS A record at this address."
  value       = google_compute_global_address.lb_ip.address
}
output "armor_policy" { value = google_compute_security_policy.armor.id }
output "ssl_cert_status" {
  description = "Will report ACTIVE once DNS propagates."
  value       = google_compute_managed_ssl_certificate.cert.managed
}
