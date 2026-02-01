#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "paramiko", "boto3"]
# ///
"""
Application Rollback Script with Audit Trail

SOC2/ISO27001 compliant rollback with:
- SOC2 CC7.2: Change management audit trail
- Version tracking and verification
- Pre-rollback state capture
- Post-rollback health verification
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import click
import paramiko
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()


def create_audit_log(
    action: str,
    from_version: str,
    to_version: str,
    host: str,
    status: str,
    reason: str,
    details: dict | None = None,
) -> dict:
    """Create an audit log entry for rollback operations."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "from_version": from_version,
        "to_version": to_version,
        "host": host,
        "status": status,
        "reason": reason,
        "user": os.environ.get("USER", "unknown"),
        "ci_job_id": os.environ.get("CI_JOB_ID", "manual"),
        "details": details or {},
    }
    return log_entry


def save_audit_log(log_entry: dict, local_path: Path, s3_bucket: str | None = None):
    """Save audit log locally and optionally to S3."""
    local_path.parent.mkdir(parents=True, exist_ok=True)

    logs = []
    if local_path.exists():
        logs = json.loads(local_path.read_text())

    logs.append(log_entry)
    local_path.write_text(json.dumps(logs, indent=2))

    console.print(f"[dim]Audit log saved to {local_path}[/dim]")

    if s3_bucket:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=os.environ.get(
                    "SCW_S3_ENDPOINT", "https://s3.fr-par.scw.cloud"
                ),
                aws_access_key_id=os.environ.get("SCW_ACCESS_KEY"),
                aws_secret_access_key=os.environ.get("SCW_SECRET_KEY"),
            )
            date_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")
            s3_key = f"rollback/{log_entry['host']}/{date_path}/audit.json"
            s3.put_object(
                Bucket=s3_bucket, Key=s3_key, Body=json.dumps(log_entry, indent=2)
            )
            console.print(f"[dim]Audit log uploaded to s3://{s3_bucket}/{s3_key}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to upload audit log to S3: {e}[/yellow]")


def ssh_connect(host: str, user: str, key_path: str | None = None) -> paramiko.SSHClient:
    """Create SSH connection to remote host."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {"hostname": host, "username": user}

    if key_path:
        connect_kwargs["key_filename"] = key_path
    else:
        default_key = Path.home() / ".ssh" / "id_ed25519"
        if not default_key.exists():
            default_key = Path.home() / ".ssh" / "id_rsa"
        if default_key.exists():
            connect_kwargs["key_filename"] = str(default_key)

    client.connect(**connect_kwargs)
    return client


def ssh_exec(client: paramiko.SSHClient, command: str) -> tuple[str, str, int]:
    """Execute command over SSH and return stdout, stderr, exit code."""
    stdin, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return stdout.read().decode(), stderr.read().decode(), exit_code


def get_current_version(client: paramiko.SSHClient) -> str | None:
    """Get current deployed version from remote host."""
    stdout, stderr, code = ssh_exec(
        client, "docker compose ps --format json 2>/dev/null | head -1"
    )
    if code != 0 or not stdout.strip():
        # Try alternative method
        stdout, stderr, code = ssh_exec(
            client, "cat /opt/app/.env 2>/dev/null | grep APP_VERSION | cut -d= -f2"
        )
        if code == 0 and stdout.strip():
            return stdout.strip()
        return None

    try:
        container_info = json.loads(stdout)
        image = container_info.get("Image", "")
        if ":" in image:
            return image.split(":")[-1]
    except json.JSONDecodeError:
        pass

    return None


def get_available_versions(image_base: str, limit: int = 10) -> list[str]:
    """Get list of available image versions from registry."""
    try:
        result = subprocess.run(
            [
                "docker",
                "image",
                "ls",
                "--format",
                "{{.Tag}}",
                image_base,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        versions = [v for v in result.stdout.strip().split("\n") if v and v != "<none>"]
        return versions[:limit]
    except subprocess.CalledProcessError:
        return []


def perform_rollback(
    client: paramiko.SSHClient,
    image: str,
    target_version: str,
) -> bool:
    """Perform the rollback operation."""
    full_image = f"{image}:{target_version}"

    console.print(f"\n[bold]Pulling image: {full_image}[/bold]")
    stdout, stderr, code = ssh_exec(client, f"docker pull {full_image}")
    if code != 0:
        console.print(f"[red]Failed to pull image: {stderr}[/red]")
        return False

    console.print("\n[bold]Updating deployment...[/bold]")

    # Update .env file with new version
    stdout, stderr, code = ssh_exec(
        client,
        f"sed -i 's/APP_VERSION=.*/APP_VERSION={target_version}/' /opt/app/.env",
    )

    # Restart services
    stdout, stderr, code = ssh_exec(
        client, "cd /opt/app && docker compose up -d --remove-orphans"
    )
    if code != 0:
        console.print(f"[red]Failed to restart services: {stderr}[/red]")
        return False

    return True


def verify_health(client: paramiko.SSHClient, port: int, timeout: int) -> bool:
    """Verify application health after rollback."""
    console.print(f"\n[bold]Verifying health (timeout: {timeout}s)...[/bold]")

    import time

    start = time.time()
    while time.time() - start < timeout:
        stdout, stderr, code = ssh_exec(
            client, f"curl -sf http://localhost:{port}/health || exit 1"
        )
        if code == 0:
            console.print("[green]Health check passed![/green]")
            return True
        time.sleep(5)

    console.print("[red]Health check timed out[/red]")
    return False


@click.command()
@click.option("--host", "-h", required=True, help="Target host IP or hostname")
@click.option("--user", "-u", default="deploy", help="SSH user")
@click.option("--key", "-k", type=click.Path(exists=True), help="SSH private key path")
@click.option("--image", "-i", required=True, help="Docker image (without tag)")
@click.option(
    "--version",
    "-v",
    required=True,
    help="Target version to rollback to, or 'previous'",
)
@click.option("--reason", "-r", required=True, help="Reason for rollback (audit trail)")
@click.option(
    "--env",
    "-e",
    type=click.Choice(["staging", "production"]),
    required=True,
    help="Deployment environment",
)
@click.option("--port", "-p", default=8000, help="Application port for health check")
@click.option("--health-timeout", default=120, help="Health check timeout in seconds")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.option("--s3-bucket", help="S3 bucket for audit logs")
def main(
    host: str,
    user: str,
    key: str | None,
    image: str,
    version: str,
    reason: str,
    env: str,
    port: int,
    health_timeout: int,
    force: bool,
    s3_bucket: str | None,
):
    """
    Rollback application to a previous version with audit logging.

    This script handles version rollback with full audit trail for
    SOC2/ISO27001 compliance. All rollback operations are logged
    with reason tracking.
    """
    console.print(
        Panel(
            f"[bold blue]Application Rollback[/bold blue]\n"
            f"Host: [yellow]{host}[/yellow]\n"
            f"Target Version: [green]{version}[/green]\n"
            f"Reason: [dim]{reason}[/dim]",
            title="SOC2/ISO27001 Compliant Rollback",
        )
    )

    audit_log_path = Path(f"./logs/rollback-audit-{env}.json")
    current_version = "unknown"
    target_version = version
    status = "started"

    try:
        # Connect to host
        console.print(f"\n[bold]Connecting to {host}...[/bold]")
        client = ssh_connect(host, user, key)

        # Get current version
        current_version = get_current_version(client) or "unknown"
        console.print(f"Current version: [cyan]{current_version}[/cyan]")

        # Handle 'previous' version
        if version == "previous":
            # Try to get previous version from deploy logs
            stdout, stderr, code = ssh_exec(
                client,
                "cat /opt/app/deploy-history.json 2>/dev/null | jq -r '.[-2].version' 2>/dev/null",
            )
            if code == 0 and stdout.strip() and stdout.strip() != "null":
                target_version = stdout.strip()
            else:
                console.print(
                    "[red]Could not determine previous version. Please specify explicitly.[/red]"
                )
                sys.exit(1)

        console.print(f"Target version: [green]{target_version}[/green]")

        if current_version == target_version:
            console.print(
                "[yellow]Current version is already the target version. Nothing to do.[/yellow]"
            )
            sys.exit(0)

        # Confirmation
        if not force:
            table = Table(title="Rollback Summary")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Host", host)
            table.add_row("From Version", current_version)
            table.add_row("To Version", target_version)
            table.add_row("Environment", env)
            table.add_row("Reason", reason)
            console.print(table)

            if not Confirm.ask("\n[yellow]Proceed with rollback?[/yellow]"):
                console.print("[dim]Rollback cancelled.[/dim]")
                sys.exit(0)

        # Log rollback start
        log_entry = create_audit_log(
            action="rollback_started",
            from_version=current_version,
            to_version=target_version,
            host=host,
            status="started",
            reason=reason,
            details={"environment": env},
        )
        save_audit_log(log_entry, audit_log_path, s3_bucket)

        # Perform rollback
        if not perform_rollback(client, image, target_version):
            status = "rollback_failed"
            raise Exception("Rollback failed")

        # Verify health
        if not verify_health(client, port, health_timeout):
            status = "health_check_failed"
            raise Exception("Health check failed after rollback")

        status = "success"
        client.close()

    except Exception as e:
        console.print(f"[red]Rollback failed: {e}[/red]")
        if status == "started":
            status = "failed"

    finally:
        # Log final status
        log_entry = create_audit_log(
            action="rollback_completed",
            from_version=current_version,
            to_version=target_version,
            host=host,
            status=status,
            reason=reason,
            details={"environment": env, "final_status": status},
        )
        save_audit_log(log_entry, audit_log_path, s3_bucket)

    if status != "success":
        console.print(
            Panel(
                f"[red bold]Rollback failed with status: {status}[/red bold]\n\n"
                "Manual intervention may be required.\n"
                f"Audit log: {audit_log_path}",
                title="Rollback Failed",
            )
        )
        sys.exit(1)

    console.print(
        Panel(
            f"[green bold]Rollback successful![/green bold]\n\n"
            f"Rolled back from {current_version} to {target_version}\n"
            f"Reason: {reason}\n\n"
            "Next steps:\n"
            "1. Verify application functionality\n"
            "2. Investigate root cause of the issue\n"
            "3. Update incident report",
            title="Rollback Complete",
        )
    )


if __name__ == "__main__":
    main()
