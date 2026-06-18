terraform {
  required_version = ">= 1.10"
  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.10, < 7.0" }
  }
  backend "gcs" {
    bucket = "ai-stt-tfstate"
    prefix = "envs/prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.primary_region
}
