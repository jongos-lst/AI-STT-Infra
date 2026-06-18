variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "name" {
  type        = string
  description = "Network/prefix name"
  default     = "ai-stt"
}

variable "regions" {
  type        = list(string)
  description = "Regions to create subnets + VPC connectors in"
}

variable "subnet_cidrs" {
  type        = map(string)
  description = "Map of region → subnet CIDR (must cover every region)"
}

variable "connector_cidrs" {
  type        = map(string)
  description = "Map of region → /28 for the serverless VPC connector"
}
