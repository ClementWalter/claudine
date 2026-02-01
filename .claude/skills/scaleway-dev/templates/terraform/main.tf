# Scaleway Terraform Configuration
# SOC2/ISO27001 Compliant Infrastructure
#
# This configuration sets up the Scaleway provider with state locking
# for secure, auditable infrastructure management.

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.0"
    }
  }

  # Remote state with locking for SOC2 CC7.2 (Change Management)
  # Uncomment and configure for production use
  # backend "s3" {
  #   bucket                      = "terraform-state-${var.project_name}"
  #   key                         = "${var.environment}/terraform.tfstate"
  #   region                      = "fr-par"
  #   endpoint                    = "s3.fr-par.scw.cloud"
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_metadata_api_check     = true
  #   skip_requesting_account_id  = true
  #   skip_s3_checksum            = true
  # }
}

provider "scaleway" {
  access_key = var.scw_access_key
  secret_key = var.scw_secret_key
  project_id = var.scw_project_id
  region     = var.scw_region
  zone       = var.scw_zone
}

# Data source for current project info
data "scaleway_account_project" "current" {
  project_id = var.scw_project_id
}

# Local values for resource naming and tagging
locals {
  resource_prefix = "${var.project_name}-${var.environment}"

  # SOC2/ISO27001 compliance tags applied to all resources
  common_tags = [
    "project:${var.project_name}",
    "environment:${var.environment}",
    "managed-by:terraform",
    "compliance:soc2-iso27001",
    "encrypted:true",
  ]
}
