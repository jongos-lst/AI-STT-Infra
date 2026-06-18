variable "project_id" { type = string }
variable "name_prefix" {
  type        = string
  description = "Bucket name prefix; final bucket name is '<name_prefix>-<role>' where role is 'audio' or 'transcripts'."
}
variable "location" {
  type        = string
  description = "GCS location — region for staging, dual-region (e.g. ASIA, NAM4) for prod"
}
variable "cors_origins" {
  type    = list(string)
  default = []
}
variable "audio_lifecycle_days" {
  type        = number
  description = "Move audio to COLDLINE after N days"
  default     = 30
}
variable "transcripts_lifecycle_days" {
  type        = number
  description = "Move transcripts to NEARLINE after N days"
  default     = 30
}
variable "uniform_access" {
  type    = bool
  default = true
}
