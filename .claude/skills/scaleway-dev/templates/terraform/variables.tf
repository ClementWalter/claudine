# Terraform Variables for Scaleway Deployment
# SOC2/ISO27001 Compliant Defaults

# ============================================================================
# Project Configuration
# ============================================================================

variable "project_name" {
  description = "Project identifier for resource naming"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "Project name must be 3-21 lowercase alphanumeric characters, starting with a letter."
  }
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

# ============================================================================
# Scaleway Credentials (Sensitive)
# ============================================================================

variable "scw_access_key" {
  description = "Scaleway access key"
  type        = string
  sensitive   = true
}

variable "scw_secret_key" {
  description = "Scaleway secret key"
  type        = string
  sensitive   = true
}

variable "scw_project_id" {
  description = "Scaleway project ID"
  type        = string
}

variable "scw_region" {
  description = "Scaleway region"
  type        = string
  default     = "fr-par"
}

variable "scw_zone" {
  description = "Scaleway zone"
  type        = string
  default     = "fr-par-1"
}

# ============================================================================
# SSH Access (SOC2 CC6.1 - Logical Access)
# ============================================================================

variable "ssh_public_key" {
  description = "SSH public key for instance access (key-only auth enforced)"
  type        = string

  validation {
    condition     = can(regex("^ssh-(rsa|ed25519|ecdsa)", var.ssh_public_key))
    error_message = "SSH public key must be a valid OpenSSH public key format."
  }
}

variable "ssh_key_name" {
  description = "Name for the SSH key resource"
  type        = string
  default     = "deploy-key"
}

# ============================================================================
# Instance Configuration
# ============================================================================

variable "instance_type" {
  description = "Scaleway instance type"
  type        = string
  default     = "DEV1-S"

  validation {
    condition = contains([
      "DEV1-S", "DEV1-M", "DEV1-L", "DEV1-XL",
      "GP1-XS", "GP1-S", "GP1-M", "GP1-L", "GP1-XL",
      "PRO2-XXS", "PRO2-XS", "PRO2-S", "PRO2-M", "PRO2-L"
    ], var.instance_type)
    error_message = "Instance type must be a valid Scaleway instance type."
  }
}

variable "instance_image" {
  description = "Instance OS image (Ubuntu 22.04 LTS recommended for security patches)"
  type        = string
  default     = "ubuntu_jammy"
}

# ============================================================================
# Compliance Settings - DO NOT DISABLE
# ============================================================================

variable "encrypted_volume" {
  description = "Enable encrypted block volume (ISO A.8.2 - Data at Rest Encryption). MUST remain true for compliance."
  type        = bool
  default     = true

  validation {
    condition     = var.encrypted_volume == true
    error_message = "Encrypted volume MUST be enabled for SOC2/ISO27001 compliance. This setting cannot be disabled."
  }
}

variable "volume_size_gb" {
  description = "Size of the encrypted data volume in GB"
  type        = number
  default     = 50

  validation {
    condition     = var.volume_size_gb >= 20
    error_message = "Volume size must be at least 20 GB."
  }
}

variable "enable_firewall" {
  description = "Enable security group firewall (SOC2 CC6.6). MUST remain true for compliance."
  type        = bool
  default     = true

  validation {
    condition     = var.enable_firewall == true
    error_message = "Firewall MUST be enabled for SOC2/ISO27001 compliance. This setting cannot be disabled."
  }
}

# ============================================================================
# Network Configuration (ISO A.13.1 - Network Security)
# ============================================================================

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed for SSH access (restrict to known IPs in production)"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Override in production with specific IPs
}

variable "allowed_http_cidrs" {
  description = "CIDR blocks allowed for HTTP/HTTPS access"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ============================================================================
# Container Registry
# ============================================================================

variable "registry_public" {
  description = "Make container registry public (should be false for production)"
  type        = bool
  default     = false
}

# ============================================================================
# Object Storage (ISO A.12.4 - Logging)
# ============================================================================

variable "s3_versioning" {
  description = "Enable S3 bucket versioning for audit trail"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Log retention period in days (365 = 1 year for compliance)"
  type        = number
  default     = 365

  validation {
    condition     = var.log_retention_days >= 365
    error_message = "Log retention must be at least 365 days for SOC2/ISO27001 compliance."
  }
}

# ============================================================================
# Cloud-init Configuration
# ============================================================================

variable "cloud_init_file" {
  description = "Path to cloud-init configuration file"
  type        = string
  default     = ""
}

variable "docker_compose_file" {
  description = "Path to docker-compose file for deployment"
  type        = string
  default     = ""
}
