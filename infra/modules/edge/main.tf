locals {
  frontend_regions = keys(var.frontend_services)
  api_regions      = keys(var.api_services)
}

# Serverless NEGs — one per region, per service.
resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  for_each              = var.frontend_services
  project               = var.project_id
  name                  = "${var.name}-fe-${each.key}"
  region                = each.key
  network_endpoint_type = "SERVERLESS"
  cloud_run { service = each.value }
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  for_each              = var.api_services
  project               = var.project_id
  name                  = "${var.name}-api-${each.key}"
  region                = each.key
  network_endpoint_type = "SERVERLESS"
  cloud_run { service = each.value }
}

# Cloud Armor: WAF + rate limit + (optional) geo-block
resource "google_compute_security_policy" "armor" {
  project = var.project_id
  name    = "${var.name}-armor"

  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr { expression = "evaluatePreconfiguredExpr('sqli-v33-stable')" }
    }
    description = "OWASP SQLi"
  }

  rule {
    action   = "deny(403)"
    priority = 1001
    match {
      expr { expression = "evaluatePreconfiguredExpr('xss-v33-stable')" }
    }
    description = "OWASP XSS"
  }

  rule {
    action   = "throttle"
    priority = 2000
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_per_minute
        interval_sec = 60
      }
    }
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    description = "Per-IP rate limit"
  }

  dynamic "rule" {
    for_each = length(var.geo_block_codes) > 0 ? [1] : []
    content {
      action      = "deny(403)"
      priority    = 3000
      description = "Geo block"
      match {
        expr { expression = "origin.region_code.contains_any([${join(",", [for c in var.geo_block_codes : "\"${c}\""])}])" }
      }
    }
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    description = "default allow"
  }
}

resource "google_compute_backend_service" "frontend" {
  project               = var.project_id
  name                  = "${var.name}-fe-bes"
  protocol              = "HTTPS"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = var.enable_cdn
  security_policy       = google_compute_security_policy.armor.id

  dynamic "backend" {
    for_each = google_compute_region_network_endpoint_group.frontend_neg
    content {
      group = backend.value.id
    }
  }

  dynamic "cdn_policy" {
    for_each = var.enable_cdn ? [1] : []
    content {
      cache_mode                   = "CACHE_ALL_STATIC"
      default_ttl                  = 3600
      max_ttl                      = 86400
      client_ttl                   = 3600
      negative_caching             = true
      signed_url_cache_max_age_sec = 0
    }
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_backend_service" "api" {
  project               = var.project_id
  name                  = "${var.name}-api-bes"
  protocol              = "HTTPS"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false
  security_policy       = google_compute_security_policy.armor.id

  dynamic "backend" {
    for_each = google_compute_region_network_endpoint_group.api_neg
    content {
      group = backend.value.id
    }
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_url_map" "main" {
  project         = var.project_id
  name            = "${var.name}-url-map"
  default_service = google_compute_backend_service.frontend.id

  host_rule {
    hosts        = [var.host]
    path_matcher = "main"
  }

  path_matcher {
    name            = "main"
    default_service = google_compute_backend_service.frontend.id

    path_rule {
      paths   = ["/v1/*", "/healthz", "/readyz", "/docs", "/openapi.json"]
      service = google_compute_backend_service.api.id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "cert" {
  project = var.project_id
  name    = "${var.name}-cert"
  managed { domains = [var.host] }
}

resource "google_compute_target_https_proxy" "https" {
  project          = var.project_id
  name             = "${var.name}-https"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.cert.id]
}

resource "google_compute_global_address" "lb_ip" {
  project = var.project_id
  name    = "${var.name}-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "${var.name}-fwd"
  target                = google_compute_target_https_proxy.https.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}

# HTTPS-only — HTTP→HTTPS redirect.
resource "google_compute_url_map" "redirect" {
  project = var.project_id
  name    = "${var.name}-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http" {
  project = var.project_id
  name    = "${var.name}-http"
  url_map = google_compute_url_map.redirect.id
}

resource "google_compute_global_forwarding_rule" "http" {
  project               = var.project_id
  name                  = "${var.name}-fwd-http"
  target                = google_compute_target_http_proxy.http.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}
