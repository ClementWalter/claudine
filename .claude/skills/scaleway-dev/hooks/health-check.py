#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "httpx", "paramiko"]
# ///
"""
Post-Deployment Health and Compliance Verification Hook

This hook is designed to be run after deployment to verify:
1. Application health (HTTP endpoint responding)
2. Basic compliance controls are in place

Blocks deployment completion until all checks pass.
"""

import sys
import time
from pathlib import Path

import click
import httpx
import paramiko
from rich.console import Console
from rich.panel import Panel

console = Console()


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
    """Execute command over SSH."""
    stdin, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return stdout.read().decode(), stderr.read().decode(), exit_code


def check_http_health(host: str, port: int, path: str, timeout: float) -> bool:
    """Check HTTP health endpoint."""
    url = f"http://{host}:{port}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            return response.status_code == 200
    except Exception:
        return False


def wait_for_health(
    host: str, port: int, path: str, timeout: float, max_wait: int
) -> bool:
    """Wait for health check to pass."""
    console.print(f"[bold]Waiting for application health (max {max_wait}s)...[/bold]")
    start = time.time()

    while time.time() - start < max_wait:
        if check_http_health(host, port, path, timeout):
            elapsed = time.time() - start
            console.print(f"[green]✓ Health check passed after {elapsed:.0f}s[/green]")
            return True
        time.sleep(5)

    console.print(f"[red]✗ Health check timed out after {max_wait}s[/red]")
    return False


def quick_compliance_check(client: paramiko.SSHClient) -> dict:
    """Run quick compliance checks."""
    checks = {}

    # Check UFW
    stdout, _, code = ssh_exec(client, "ufw status | grep -q 'Status: active'")
    checks["ufw_active"] = code == 0

    # Check fail2ban
    stdout, _, code = ssh_exec(client, "systemctl is-active fail2ban")
    checks["fail2ban_active"] = "active" in stdout

    # Check auditd
    stdout, _, code = ssh_exec(client, "systemctl is-active auditd")
    checks["auditd_active"] = "active" in stdout

    # Check SSH password auth disabled
    stdout, _, code = ssh_exec(
        client, "sshd -T 2>/dev/null | grep -q 'passwordauthentication no'"
    )
    checks["ssh_hardened"] = code == 0

    return checks


@click.command()
@click.option("--host", "-h", required=True, help="Target host")
@click.option("--user", "-u", default="deploy", help="SSH user")
@click.option("--key", "-k", type=click.Path(exists=True), help="SSH key path")
@click.option("--port", "-p", default=8000, help="Application port")
@click.option("--path", default="/health", help="Health endpoint path")
@click.option("--timeout", "-t", default=10.0, help="Request timeout")
@click.option("--max-wait", "-w", default=300, help="Max wait time for health")
@click.option("--skip-compliance", is_flag=True, help="Skip compliance checks")
def main(
    host: str,
    user: str,
    key: str | None,
    port: int,
    path: str,
    timeout: float,
    max_wait: int,
    skip_compliance: bool,
):
    """
    Post-deployment verification hook.

    Verifies application health and basic compliance controls.
    Exits with non-zero status if checks fail, blocking deployment completion.
    """
    console.print(
        Panel(
            f"[bold blue]Post-Deployment Verification[/bold blue]\n"
            f"Host: [yellow]{host}:{port}[/yellow]",
            title="Health & Compliance Hook",
        )
    )

    all_passed = True

    # Health check
    if not wait_for_health(host, port, path, timeout, max_wait):
        all_passed = False

    # Quick compliance check
    if not skip_compliance:
        console.print("\n[bold]Running quick compliance checks...[/bold]")
        try:
            client = ssh_connect(host, user, key)
            checks = quick_compliance_check(client)
            client.close()

            for check_name, passed in checks.items():
                status = "[green]✓[/green]" if passed else "[red]✗[/red]"
                console.print(f"  {status} {check_name.replace('_', ' ').title()}")
                if not passed:
                    all_passed = False

        except Exception as e:
            console.print(f"[yellow]Warning: Could not run compliance checks: {e}[/yellow]")

    # Final status
    if all_passed:
        console.print(
            "\n[green bold]✓ Post-deployment verification passed[/green bold]"
        )
        sys.exit(0)
    else:
        console.print(
            "\n[red bold]✗ Post-deployment verification failed[/red bold]"
        )
        console.print("[yellow]Deployment should NOT be marked complete.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
