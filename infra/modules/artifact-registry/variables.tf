variable "project_id" { type = string }
variable "location" {
  type        = string
  description = "Region (or multi-region) for the repo"
}
variable "name" {
  type    = string
  default = "ai-stt"
}
variable "writers" {
  type        = list(string)
  description = "SA emails permitted to push (CI deployer)"
  default     = []
}
variable "readers" {
  type        = list(string)
  description = "SA emails permitted to pull (Cloud Run workload SAs)"
  default     = []
}
