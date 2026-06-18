variable "project_id" { type = string }
variable "name" {
  type    = string
  default = "ai-stt"
}

variable "host" {
  type        = string
  description = "Fully-qualified hostname, e.g. app.example.com"
}

variable "frontend_services" {
  description = "Map region → Cloud Run service name for the frontend"
  type        = map(string)
}

variable "api_services" {
  description = "Map region → Cloud Run service name for the API"
  type        = map(string)
}

variable "enable_cdn" {
  type    = bool
  default = true
}

variable "rate_limit_per_minute" {
  type    = number
  default = 6000
}

variable "geo_block_codes" {
  type        = list(string)
  default     = []
  description = "ISO-2 country codes to deny (Cloud Armor)"
}
