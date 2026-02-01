# Scaleway Object Storage Configuration
# S3-compatible storage for logs, backups, and audit trails
# ISO A.12.4 - Logging and Monitoring

# ============================================================================
# Audit Logs Bucket (SOC2 CC7.1, ISO A.12.4)
# ============================================================================

resource "scaleway_object_bucket" "audit_logs" {
  name   = "${local.resource_prefix}-audit-logs"
  region = var.scw_region

  # Enable versioning for audit trail integrity (SOC2 CC7.2)
  versioning {
    enabled = var.s3_versioning
  }

  # Lifecycle rules for log retention (ISO A.12.4 - 1 year minimum)
  lifecycle_rule {
    id      = "audit-log-retention"
    enabled = true
    prefix  = "audit/"

    # Transition to cheaper storage after 90 days
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Delete after retention period
    expiration {
      days = var.log_retention_days
    }
  }

  lifecycle_rule {
    id      = "deploy-log-retention"
    enabled = true
    prefix  = "deploy/"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = var.log_retention_days
    }
  }

  tags = {
    project     = var.project_name
    environment = var.environment
    purpose     = "audit-logs"
    compliance  = "soc2-iso27001"
    retention   = "${var.log_retention_days}-days"
  }
}

# ============================================================================
# Application Data Bucket
# ============================================================================

resource "scaleway_object_bucket" "app_data" {
  name   = "${local.resource_prefix}-app-data"
  region = var.scw_region

  versioning {
    enabled = true
  }

  tags = {
    project     = var.project_name
    environment = var.environment
    purpose     = "app-data"
    compliance  = "soc2-iso27001"
  }
}

# ============================================================================
# Backup Bucket
# ============================================================================

resource "scaleway_object_bucket" "backups" {
  name   = "${local.resource_prefix}-backups"
  region = var.scw_region

  versioning {
    enabled = true
  }

  lifecycle_rule {
    id      = "backup-retention"
    enabled = true
    prefix  = ""

    # Keep backups for 90 days minimum
    expiration {
      days = 90
    }
  }

  tags = {
    project     = var.project_name
    environment = var.environment
    purpose     = "backups"
    compliance  = "soc2-iso27001"
  }
}

# ============================================================================
# Outputs
# ============================================================================

output "audit_logs_bucket" {
  description = "Audit logs bucket name"
  value       = scaleway_object_bucket.audit_logs.name
}

output "audit_logs_endpoint" {
  description = "Audit logs bucket endpoint"
  value       = scaleway_object_bucket.audit_logs.endpoint
}

output "app_data_bucket" {
  description = "Application data bucket name"
  value       = scaleway_object_bucket.app_data.name
}

output "backups_bucket" {
  description = "Backups bucket name"
  value       = scaleway_object_bucket.backups.name
}
