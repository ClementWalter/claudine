# Terraform Outputs for Scaleway Infrastructure
# Consolidated outputs for deployment scripts

# ============================================================================
# Instance Outputs (from instance.tf)
# ============================================================================

# Note: instance_id, instance_public_ip, instance_private_ip,
# security_group_id, and data_volume_id are defined in instance.tf

# ============================================================================
# Registry Outputs (from registry.tf)
# ============================================================================

# Note: registry_namespace and registry_endpoint are defined in registry.tf

# ============================================================================
# Storage Outputs (from storage.tf)
# ============================================================================

# Note: audit_logs_bucket, audit_logs_endpoint, app_data_bucket,
# and backups_bucket are defined in storage.tf

# ============================================================================
# Consolidated Deployment Info
# ============================================================================

output "deployment_info" {
  description = "Consolidated deployment information for scripts"
  value = {
    project     = var.project_name
    environment = var.environment
    region      = var.scw_region
    zone        = var.scw_zone

    # Connection info
    ssh_user = "root"
    ssh_host = scaleway_instance_ip.main.address

    # Registry info for docker login
    registry = {
      endpoint  = scaleway_registry_namespace.main.endpoint
      namespace = scaleway_registry_namespace.main.name
    }

    # Storage endpoints
    storage = {
      audit_logs = scaleway_object_bucket.audit_logs.endpoint
      app_data   = scaleway_object_bucket.app_data.endpoint
      backups    = scaleway_object_bucket.backups.endpoint
    }

    # Compliance verification
    compliance = {
      encrypted_volume = var.encrypted_volume
      firewall_enabled = var.enable_firewall
      log_retention    = var.log_retention_days
    }
  }
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh root@${scaleway_instance_ip.main.address}"
}

output "docker_login_command" {
  description = "Docker login command for the registry"
  value       = "docker login ${scaleway_registry_namespace.main.endpoint} -u nologin --password-stdin <<< $SCW_SECRET_KEY"
  sensitive   = false
}
