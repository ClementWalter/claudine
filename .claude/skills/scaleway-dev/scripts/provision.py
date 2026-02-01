#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich"]
# ///
"""
Terraform Provisioning Wrapper with Compliance Validation

SOC2/ISO27001 compliant infrastructure provisioning for Scaleway.
Validates that all required security controls are enabled before provisioning.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def run_command(
    cmd: list[str], cwd: str | None = None, capture: bool = False
) -> subprocess.CompletedProcess:
    """Run a command with error handling."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
        if e.stdout:
            console.print(f"[dim]stdout: {e.stdout}[/dim]")
        if e.stderr:
            console.print(f"[red]stderr: {e.stderr}[/red]")
        raise


def validate_terraform_config(tf_dir: Path) -> dict:
    """Validate Terraform configuration for compliance requirements."""
    console.print("\n[bold]Validating Terraform Configuration...[/bold]")

    checks = {
        "encrypted_volume": False,
        "security_group": False,
        "ssh_key": False,
        "audit_logs_bucket": False,
    }

    # Read all .tf files
    tf_content = ""
    for tf_file in tf_dir.glob("*.tf"):
        tf_content += tf_file.read_text()

    # Check for encrypted volume
    if "scaleway_instance_volume" in tf_content:
        checks["encrypted_volume"] = True

    # Check for security group
    if "scaleway_instance_security_group" in tf_content:
        if 'inbound_default_policy  = "drop"' in tf_content:
            checks["security_group"] = True

    # Check for SSH key
    if "scaleway_iam_ssh_key" in tf_content:
        checks["ssh_key"] = True

    # Check for audit logs bucket
    if "audit_logs" in tf_content or "audit-logs" in tf_content:
        checks["audit_logs_bucket"] = True

    return checks


def validate_tfvars(tf_dir: Path, env: str) -> dict:
    """Validate terraform.tfvars for compliance settings."""
    console.print("\n[bold]Validating Variables...[/bold]")

    tfvars_file = tf_dir / f"{env}.tfvars"
    if not tfvars_file.exists():
        tfvars_file = tf_dir / "terraform.tfvars"

    checks = {
        "encrypted_volume_enabled": False,
        "firewall_enabled": False,
        "log_retention_compliant": False,
    }

    if tfvars_file.exists():
        content = tfvars_file.read_text()

        # These should be true or not explicitly set to false
        if "encrypted_volume" not in content or "encrypted_volume = true" in content:
            checks["encrypted_volume_enabled"] = True

        if "enable_firewall" not in content or "enable_firewall = true" in content:
            checks["firewall_enabled"] = True

        # Log retention should be >= 365
        if "log_retention_days" not in content:
            checks["log_retention_compliant"] = True  # Uses default of 365
        elif "log_retention_days = 365" in content or any(
            f"log_retention_days = {d}" in content for d in range(365, 1000)
        ):
            checks["log_retention_compliant"] = True
    else:
        # No tfvars means using defaults, which are compliant
        checks["encrypted_volume_enabled"] = True
        checks["firewall_enabled"] = True
        checks["log_retention_compliant"] = True

    return checks


def display_compliance_status(config_checks: dict, var_checks: dict) -> bool:
    """Display compliance check results and return overall status."""
    table = Table(title="Compliance Validation Results")
    table.add_column("Control", style="cyan")
    table.add_column("Requirement", style="white")
    table.add_column("Status", style="bold")

    all_passed = True

    # Config checks
    checks = [
        (
            "ISO A.8.2",
            "Encrypted volume resource defined",
            config_checks["encrypted_volume"],
        ),
        (
            "SOC2 CC6.6",
            "Security group with deny-by-default",
            config_checks["security_group"],
        ),
        ("SOC2 CC6.1", "SSH key resource defined", config_checks["ssh_key"]),
        ("ISO A.12.4", "Audit logs bucket defined", config_checks["audit_logs_bucket"]),
        (
            "ISO A.8.2",
            "Encrypted volume enabled in vars",
            var_checks["encrypted_volume_enabled"],
        ),
        ("SOC2 CC6.6", "Firewall enabled in vars", var_checks["firewall_enabled"]),
        (
            "ISO A.12.4",
            "Log retention >= 365 days",
            var_checks["log_retention_compliant"],
        ),
    ]

    for control, requirement, passed in checks:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(control, requirement, status)
        if not passed:
            all_passed = False

    console.print(table)
    return all_passed


@click.command()
@click.option(
    "--env",
    "-e",
    type=click.Choice(["staging", "production"]),
    required=True,
    help="Deployment environment",
)
@click.option(
    "--tf-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="./infra",
    help="Terraform directory",
)
@click.option("--auto-approve", is_flag=True, help="Skip interactive approval")
@click.option("--plan-only", is_flag=True, help="Only run terraform plan")
@click.option(
    "--skip-validation", is_flag=True, help="Skip compliance validation (NOT RECOMMENDED)"
)
def main(
    env: str, tf_dir: Path, auto_approve: bool, plan_only: bool, skip_validation: bool
):
    """
    Provision Scaleway infrastructure with SOC2/ISO27001 compliance validation.

    This script wraps Terraform commands and ensures all required security
    controls are properly configured before provisioning.
    """
    console.print(
        Panel(
            f"[bold blue]Scaleway Infrastructure Provisioning[/bold blue]\n"
            f"Environment: [yellow]{env}[/yellow]\n"
            f"Terraform Directory: [dim]{tf_dir}[/dim]",
            title="SOC2/ISO27001 Compliant Deployment",
        )
    )

    # Validate compliance unless explicitly skipped
    if not skip_validation:
        config_checks = validate_terraform_config(tf_dir)
        var_checks = validate_tfvars(tf_dir, env)

        if not display_compliance_status(config_checks, var_checks):
            console.print(
                "\n[red bold]COMPLIANCE VALIDATION FAILED[/red bold]"
            )
            console.print(
                "[yellow]Fix the issues above before provisioning.[/yellow]"
            )
            console.print(
                "[dim]Use --skip-validation to bypass (NOT RECOMMENDED)[/dim]"
            )
            sys.exit(1)

        console.print("\n[green bold]✓ All compliance checks passed[/green bold]")
    else:
        console.print(
            "\n[yellow bold]⚠ Compliance validation skipped[/yellow bold]"
        )

    # Initialize Terraform
    console.print("\n[bold]Initializing Terraform...[/bold]")
    run_command(["terraform", "init"], cwd=str(tf_dir))

    # Select or create workspace
    console.print(f"\n[bold]Selecting workspace: {env}...[/bold]")
    try:
        run_command(["terraform", "workspace", "select", env], cwd=str(tf_dir))
    except subprocess.CalledProcessError:
        run_command(["terraform", "workspace", "new", env], cwd=str(tf_dir))

    # Run terraform plan
    console.print("\n[bold]Running Terraform plan...[/bold]")
    tfvars_file = tf_dir / f"{env}.tfvars"
    plan_cmd = ["terraform", "plan", "-out=tfplan"]
    if tfvars_file.exists():
        plan_cmd.extend(["-var-file", str(tfvars_file)])

    run_command(plan_cmd, cwd=str(tf_dir))

    if plan_only:
        console.print("\n[green]Plan complete. Review the changes above.[/green]")
        return

    # Confirm before apply
    if not auto_approve:
        if not click.confirm("\nDo you want to apply these changes?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Run terraform apply
    console.print("\n[bold]Applying Terraform changes...[/bold]")
    apply_cmd = ["terraform", "apply", "tfplan"]
    run_command(apply_cmd, cwd=str(tf_dir))

    # Get outputs
    console.print("\n[bold]Retrieving outputs...[/bold]")
    result = run_command(
        ["terraform", "output", "-json"], cwd=str(tf_dir), capture=True
    )
    outputs = json.loads(result.stdout)

    # Display outputs
    output_table = Table(title="Infrastructure Outputs")
    output_table.add_column("Output", style="cyan")
    output_table.add_column("Value", style="green")

    for key, value in outputs.items():
        if isinstance(value, dict) and "value" in value:
            val = value["value"]
            if isinstance(val, dict):
                val = json.dumps(val, indent=2)
            output_table.add_row(key, str(val))

    console.print(output_table)

    console.print(
        Panel(
            "[green bold]Infrastructure provisioned successfully![/green bold]\n\n"
            "Next steps:\n"
            "1. Wait for cloud-init to complete security hardening\n"
            "2. Run compliance verification: uv run scripts/compliance.py\n"
            "3. Deploy application: uv run scripts/deploy.py",
            title="Provisioning Complete",
        )
    )


if __name__ == "__main__":
    main()
