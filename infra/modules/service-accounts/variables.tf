variable "project_id" { type = string }
variable "service_accounts" {
  description = "name → roles (project-level)"
  type = map(object({
    display_name = optional(string)
    roles        = list(string)
  }))
}
