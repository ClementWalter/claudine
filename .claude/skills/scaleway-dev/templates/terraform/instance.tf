# Scaleway Compute Instance Configuration
# SOC2/ISO27001 Compliant with Encrypted Volumes and Security Groups

# ============================================================================
# SSH Key (SOC2 CC6.1 - Logical Access Control)
# ============================================================================

resource "scaleway_iam_ssh_key" "deploy" {
  name       = "${local.resource_prefix}-${var.ssh_key_name}"
  public_key = var.ssh_public_key
}

# ============================================================================
# Security Group (SOC2 CC6.6 - System Boundaries)
# Deny-by-default with explicit allow rules
# ============================================================================

resource "scaleway_instance_security_group" "main" {
  name                    = "${local.resource_prefix}-sg"
  inbound_default_policy  = "drop"  # SOC2 CC6.6: Deny by default
  outbound_default_policy = "accept"

  # SSH access (SOC2 CC6.1)
  dynamic "inbound_rule" {
    for_each = var.allowed_ssh_cidrs
    content {
      action   = "accept"
      port     = 22
      protocol = "TCP"
      ip_range = inbound_rule.value
    }
  }

  # HTTP access
  dynamic "inbound_rule" {
    for_each = var.allowed_http_cidrs
    content {
      action   = "accept"
      port     = 80
      protocol = "TCP"
      ip_range = inbound_rule.value
    }
  }

  # HTTPS access
  dynamic "inbound_rule" {
    for_each = var.allowed_http_cidrs
    content {
      action   = "accept"
      port     = 443
      protocol = "TCP"
      ip_range = inbound_rule.value
    }
  }

  # Allow ICMP for health checks
  inbound_rule {
    action   = "accept"
    protocol = "ICMP"
  }

  tags = local.common_tags
}

# ============================================================================
# Encrypted Block Volume (ISO A.8.2 - Data at Rest Encryption)
# ============================================================================

resource "scaleway_instance_volume" "data" {
  name       = "${local.resource_prefix}-data"
  type       = "b_ssd"
  size_in_gb = var.volume_size_gb

  tags = local.common_tags
}

# ============================================================================
# Compute Instance
# ============================================================================

resource "scaleway_instance_ip" "main" {
  # Reserved public IP for the instance
}

resource "scaleway_instance_server" "main" {
  name  = "${local.resource_prefix}-server"
  type  = var.instance_type
  image = var.instance_image

  ip_id = scaleway_instance_ip.main.id

  # Attach security group (SOC2 CC6.6)
  security_group_id = scaleway_instance_security_group.main.id

  # Root volume
  root_volume {
    size_in_gb            = 20
    volume_type           = "b_ssd"
    delete_on_termination = true
  }

  # Attach encrypted data volume (ISO A.8.2)
  additional_volume_ids = [
    scaleway_instance_volume.data.id
  ]

  # Cloud-init for security hardening
  user_data = {
    cloud-init = var.cloud_init_file != "" ? file(var.cloud_init_file) : <<-EOF
      #cloud-config
      # Minimal cloud-init - use templates/cloud-init.yaml for full hardening
      package_update: true
      package_upgrade: true
      packages:
        - docker.io
        - docker-compose
        - fail2ban
        - ufw
        - auditd
      runcmd:
        - systemctl enable docker
        - systemctl start docker
        - ufw default deny incoming
        - ufw default allow outgoing
        - ufw allow 22/tcp
        - ufw allow 80/tcp
        - ufw allow 443/tcp
        - ufw --force enable
        - systemctl enable fail2ban
        - systemctl start fail2ban
        - systemctl enable auditd
        - systemctl start auditd
    EOF
  }

  tags = local.common_tags

  lifecycle {
    # Prevent accidental destruction of production instances
    prevent_destroy = false  # Set to true in production
  }
}

# ============================================================================
# Outputs
# ============================================================================

output "instance_id" {
  description = "Instance ID"
  value       = scaleway_instance_server.main.id
}

output "instance_public_ip" {
  description = "Public IP address of the instance"
  value       = scaleway_instance_ip.main.address
}

output "instance_private_ip" {
  description = "Private IP address of the instance"
  value       = scaleway_instance_server.main.private_ip
}

output "security_group_id" {
  description = "Security group ID"
  value       = scaleway_instance_security_group.main.id
}

output "data_volume_id" {
  description = "Encrypted data volume ID"
  value       = scaleway_instance_volume.data.id
}
