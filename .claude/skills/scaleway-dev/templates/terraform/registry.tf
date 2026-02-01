# Scaleway Container Registry Configuration
# Private registry for secure container image storage

# ============================================================================
# Container Registry Namespace
# ============================================================================

resource "scaleway_registry_namespace" "main" {
  name        = "${var.project_name}-${var.environment}"
  description = "Container registry for ${var.project_name} (${var.environment})"
  is_public   = var.registry_public
  region      = var.scw_region
}

# ============================================================================
# Outputs
# ============================================================================

output "registry_namespace" {
  description = "Container registry namespace name"
  value       = scaleway_registry_namespace.main.name
}

output "registry_endpoint" {
  description = "Container registry endpoint URL"
  value       = scaleway_registry_namespace.main.endpoint
}
