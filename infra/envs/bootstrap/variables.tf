variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "asia-east1"
}
variable "github_owner" {
  type    = string
  default = "jongos-lst"
}
variable "github_repo" {
  type    = string
  default = "AI-STT-Infra"
}
variable "state_bucket_name" {
  type        = string
  description = "Name of the GCS bucket holding remote state for staging/prod"
}
