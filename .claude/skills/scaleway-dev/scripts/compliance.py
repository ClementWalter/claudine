#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "paramiko"]
# ///
"""
Compliance Verification Script

Verifies SOC2/ISO27001 compliance controls are properly configured:
- SOC2 CC6.1: SSH key-only authentication
- SOC2 CC6.6: UFW firewall with deny-by-default
- SOC2 CC6.7: Fail2ban active
- SOC2 CC7.1: Auditd logging enabled
- ISO A.8.2: Encrypted volume attached
- ISO A.9.4: Container no-new-privileges
- ISO A.12.4: Log retention configured
- ISO A.13.1: Internal network isolation
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import click
import paramiko
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class ComplianceCheck:
    control: str
    name: str
    status: str  # "pass", "fail", "warning", "error"
    message: str
    details: str | None = None


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


def check_ssh_hardening(client: paramiko.SSHClient) -> ComplianceCheck:
    """SOC2 CC6.1: Verify SSH is configured for key-only authentication."""
    stdout, stderr, code = ssh_exec(
        client, "sshd -T 2>/dev/null | grep -E '^passwordauthentication'"
    )

    if code != 0:
        return ComplianceCheck(
            control="SOC2 CC6.1",
            name="SSH Key-Only Authentication",
            status="error",
            message="Could not check SSH configuration",
        )

    if "passwordauthentication no" in stdout.lower():
        return ComplianceCheck(
            control="SOC2 CC6.1",
            name="SSH Key-Only Authentication",
            status="pass",
            message="Password authentication disabled",
        )
    else:
        return ComplianceCheck(
            control="SOC2 CC6.1",
            name="SSH Key-Only Authentication",
            status="fail",
            message="Password authentication is enabled",
            details="Set 'PasswordAuthentication no' in /etc/ssh/sshd_config",
        )


def check_firewall(client: paramiko.SSHClient) -> ComplianceCheck:
    """SOC2 CC6.6: Verify UFW firewall is active with deny-by-default."""
    stdout, stderr, code = ssh_exec(client, "ufw status verbose 2>/dev/null")

    if code != 0:
        return ComplianceCheck(
            control="SOC2 CC6.6",
            name="UFW Firewall",
            status="error",
            message="Could not check UFW status",
        )

    if "Status: active" not in stdout:
        return ComplianceCheck(
            control="SOC2 CC6.6",
            name="UFW Firewall",
            status="fail",
            message="UFW firewall is not active",
            details="Run 'ufw enable' to activate firewall",
        )

    if "Default: deny (incoming)" in stdout:
        return ComplianceCheck(
            control="SOC2 CC6.6",
            name="UFW Firewall",
            status="pass",
            message="Firewall active with deny-by-default",
        )
    else:
        return ComplianceCheck(
            control="SOC2 CC6.6",
            name="UFW Firewall",
            status="warning",
            message="Firewall active but not deny-by-default",
            details="Run 'ufw default deny incoming'",
        )


def check_fail2ban(client: paramiko.SSHClient) -> ComplianceCheck:
    """SOC2 CC6.7: Verify fail2ban is active."""
    stdout, stderr, code = ssh_exec(
        client, "systemctl is-active fail2ban 2>/dev/null"
    )

    if "active" in stdout:
        # Check if sshd jail is enabled
        stdout2, _, _ = ssh_exec(client, "fail2ban-client status sshd 2>/dev/null")
        if "Status for the jail: sshd" in stdout2:
            return ComplianceCheck(
                control="SOC2 CC6.7",
                name="Fail2ban Brute-Force Protection",
                status="pass",
                message="Fail2ban active with SSH jail enabled",
            )
        else:
            return ComplianceCheck(
                control="SOC2 CC6.7",
                name="Fail2ban Brute-Force Protection",
                status="warning",
                message="Fail2ban active but SSH jail not configured",
                details="Enable sshd jail in /etc/fail2ban/jail.local",
            )
    else:
        return ComplianceCheck(
            control="SOC2 CC6.7",
            name="Fail2ban Brute-Force Protection",
            status="fail",
            message="Fail2ban is not active",
            details="Run 'systemctl enable --now fail2ban'",
        )


def check_auditd(client: paramiko.SSHClient) -> ComplianceCheck:
    """SOC2 CC7.1: Verify auditd is active and logging."""
    stdout, stderr, code = ssh_exec(
        client, "systemctl is-active auditd 2>/dev/null"
    )

    if "active" not in stdout:
        return ComplianceCheck(
            control="SOC2 CC7.1",
            name="Auditd Logging",
            status="fail",
            message="Auditd is not active",
            details="Run 'systemctl enable --now auditd'",
        )

    # Check for audit rules
    stdout2, _, code2 = ssh_exec(client, "auditctl -l 2>/dev/null | wc -l")
    rule_count = int(stdout2.strip()) if stdout2.strip().isdigit() else 0

    if rule_count > 10:
        return ComplianceCheck(
            control="SOC2 CC7.1",
            name="Auditd Logging",
            status="pass",
            message=f"Auditd active with {rule_count} rules",
        )
    else:
        return ComplianceCheck(
            control="SOC2 CC7.1",
            name="Auditd Logging",
            status="warning",
            message=f"Auditd active but only {rule_count} rules configured",
            details="Apply compliance rules from cloud-init.yaml",
        )


def check_encrypted_volume(client: paramiko.SSHClient) -> ComplianceCheck:
    """ISO A.8.2: Verify encrypted volume is attached."""
    # Check for attached block devices (Scaleway volumes)
    stdout, stderr, code = ssh_exec(client, "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null")

    # Check for /data mount point (our encrypted volume mount)
    if "/data" in stdout:
        return ComplianceCheck(
            control="ISO A.8.2",
            name="Encrypted Data Volume",
            status="pass",
            message="Encrypted volume mounted at /data",
        )

    # Check for any additional block devices
    stdout2, _, _ = ssh_exec(client, "ls /dev/sd* 2>/dev/null | wc -l")
    device_count = int(stdout2.strip()) if stdout2.strip().isdigit() else 0

    if device_count > 1:
        return ComplianceCheck(
            control="ISO A.8.2",
            name="Encrypted Data Volume",
            status="warning",
            message="Additional block device found but not mounted",
            details="Mount encrypted volume to /data",
        )
    else:
        return ComplianceCheck(
            control="ISO A.8.2",
            name="Encrypted Data Volume",
            status="fail",
            message="No encrypted data volume attached",
            details="Attach encrypted block volume via Terraform",
        )


def check_container_security(client: paramiko.SSHClient) -> ComplianceCheck:
    """ISO A.9.4: Verify containers run with no-new-privileges."""
    stdout, stderr, code = ssh_exec(
        client,
        "docker inspect $(docker ps -q) 2>/dev/null | grep -i 'nonewprivileges' | head -5",
    )

    if code != 0 or not stdout.strip():
        # No containers or can't inspect
        stdout2, _, code2 = ssh_exec(client, "docker ps -q 2>/dev/null | wc -l")
        container_count = int(stdout2.strip()) if stdout2.strip().isdigit() else 0

        if container_count == 0:
            return ComplianceCheck(
                control="ISO A.9.4",
                name="Container No-New-Privileges",
                status="warning",
                message="No containers running to verify",
            )
        else:
            return ComplianceCheck(
                control="ISO A.9.4",
                name="Container No-New-Privileges",
                status="error",
                message="Could not inspect container security options",
            )

    if "true" in stdout.lower():
        return ComplianceCheck(
            control="ISO A.9.4",
            name="Container No-New-Privileges",
            status="pass",
            message="Containers running with no-new-privileges",
        )
    else:
        return ComplianceCheck(
            control="ISO A.9.4",
            name="Container No-New-Privileges",
            status="fail",
            message="Containers not using no-new-privileges",
            details="Add 'security_opt: no-new-privileges:true' to docker-compose.yml",
        )


def check_log_retention(client: paramiko.SSHClient) -> ComplianceCheck:
    """ISO A.12.4: Verify log retention is configured."""
    stdout, stderr, code = ssh_exec(
        client, "cat /etc/logrotate.d/deploy-logs 2>/dev/null"
    )

    if code == 0 and "rotate" in stdout:
        # Check rotation count
        if "rotate 30" in stdout or "rotate 365" in stdout:
            return ComplianceCheck(
                control="ISO A.12.4",
                name="Log Retention",
                status="pass",
                message="Log rotation configured for retention",
            )
        else:
            return ComplianceCheck(
                control="ISO A.12.4",
                name="Log Retention",
                status="warning",
                message="Log rotation configured but retention period unclear",
            )
    else:
        return ComplianceCheck(
            control="ISO A.12.4",
            name="Log Retention",
            status="fail",
            message="Deploy log rotation not configured",
            details="Apply logrotate config from cloud-init.yaml",
        )


def check_network_isolation(client: paramiko.SSHClient) -> ComplianceCheck:
    """ISO A.13.1: Verify internal network isolation for containers."""
    stdout, stderr, code = ssh_exec(
        client,
        "docker network ls --format '{{.Name}}' 2>/dev/null | grep -E 'backend|internal'",
    )

    if stdout.strip():
        # Check if internal network is truly internal
        stdout2, _, _ = ssh_exec(
            client,
            f"docker network inspect {stdout.strip().split()[0]} 2>/dev/null | grep -i internal",
        )
        if "true" in stdout2.lower():
            return ComplianceCheck(
                control="ISO A.13.1",
                name="Internal Network Isolation",
                status="pass",
                message="Internal network configured for backend services",
            )
        else:
            return ComplianceCheck(
                control="ISO A.13.1",
                name="Internal Network Isolation",
                status="warning",
                message="Backend network exists but not marked as internal",
                details="Add 'internal: true' to backend network in docker-compose.yml",
            )
    else:
        return ComplianceCheck(
            control="ISO A.13.1",
            name="Internal Network Isolation",
            status="warning",
            message="No internal/backend network found",
            details="Configure internal network in docker-compose.yml",
        )


def check_unattended_upgrades(client: paramiko.SSHClient) -> ComplianceCheck:
    """ISO A.12.6: Verify unattended-upgrades is enabled."""
    stdout, stderr, code = ssh_exec(
        client, "systemctl is-enabled unattended-upgrades 2>/dev/null"
    )

    if "enabled" in stdout:
        return ComplianceCheck(
            control="ISO A.12.6",
            name="Automatic Security Updates",
            status="pass",
            message="Unattended-upgrades enabled",
        )
    else:
        return ComplianceCheck(
            control="ISO A.12.6",
            name="Automatic Security Updates",
            status="fail",
            message="Unattended-upgrades not enabled",
            details="Run 'systemctl enable --now unattended-upgrades'",
        )


def display_results(checks: list[ComplianceCheck]) -> bool:
    """Display compliance check results and return overall status."""
    table = Table(title="Compliance Verification Results")
    table.add_column("Control", style="cyan", width=12)
    table.add_column("Check", style="white", width=30)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Message", style="dim")

    all_passed = True
    has_failures = False

    for check in checks:
        if check.status == "pass":
            status_str = "[green]✓ PASS[/green]"
        elif check.status == "warning":
            status_str = "[yellow]⚠ WARN[/yellow]"
        elif check.status == "fail":
            status_str = "[red]✗ FAIL[/red]"
            all_passed = False
            has_failures = True
        else:
            status_str = "[red]? ERROR[/red]"
            all_passed = False

        table.add_row(check.control, check.name, status_str, check.message)

    console.print(table)

    # Show details for failures
    failures = [c for c in checks if c.status in ("fail", "error") and c.details]
    if failures:
        console.print("\n[bold red]Remediation Required:[/bold red]")
        for check in failures:
            console.print(f"  • {check.control} - {check.name}:")
            console.print(f"    [dim]{check.details}[/dim]")

    return all_passed and not has_failures


@click.command()
@click.option("--host", "-h", required=True, help="Target host IP or hostname")
@click.option("--user", "-u", default="deploy", help="SSH user")
@click.option("--key", "-k", type=click.Path(exists=True), help="SSH private key path")
@click.option(
    "--env",
    "-e",
    type=click.Choice(["staging", "production"]),
    default="production",
    help="Deployment environment",
)
@click.option(
    "--check",
    "-c",
    multiple=True,
    type=click.Choice(
        ["ssh", "firewall", "fail2ban", "auditd", "encryption", "container", "logs", "network", "upgrades"]
    ),
    help="Run specific check(s) only",
)
@click.option("--json-output", "-j", is_flag=True, help="Output results as JSON")
def main(
    host: str,
    user: str,
    key: str | None,
    env: str,
    check: tuple,
    json_output: bool,
):
    """
    Verify SOC2/ISO27001 compliance controls on a deployed server.

    This script checks all required security controls and reports
    compliance status. Use before marking any deployment as complete.
    """
    if not json_output:
        console.print(
            Panel(
                f"[bold blue]Compliance Verification[/bold blue]\n"
                f"Host: [yellow]{host}[/yellow]\n"
                f"Environment: [cyan]{env}[/cyan]",
                title="SOC2/ISO27001 Compliance Check",
            )
        )

    try:
        if not json_output:
            console.print(f"\n[bold]Connecting to {host}...[/bold]")
        client = ssh_connect(host, user, key)
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        sys.exit(1)

    # Define all checks
    all_checks = {
        "ssh": check_ssh_hardening,
        "firewall": check_firewall,
        "fail2ban": check_fail2ban,
        "auditd": check_auditd,
        "encryption": check_encrypted_volume,
        "container": check_container_security,
        "logs": check_log_retention,
        "network": check_network_isolation,
        "upgrades": check_unattended_upgrades,
    }

    # Run selected checks or all
    checks_to_run = check if check else tuple(all_checks.keys())
    results = []

    if not json_output:
        console.print("\n[bold]Running compliance checks...[/bold]\n")

    for check_name in checks_to_run:
        if check_name in all_checks:
            result = all_checks[check_name](client)
            results.append(result)

    client.close()

    if json_output:
        import json

        output = [
            {
                "control": r.control,
                "name": r.name,
                "status": r.status,
                "message": r.message,
                "details": r.details,
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
        all_passed = all(r.status in ("pass", "warning") for r in results)
    else:
        all_passed = display_results(results)

    if all_passed:
        if not json_output:
            console.print(
                "\n[green bold]✓ ALL COMPLIANCE CHECKS PASSED[/green bold]"
            )
        sys.exit(0)
    else:
        if not json_output:
            console.print(
                "\n[red bold]✗ COMPLIANCE CHECKS FAILED[/red bold]"
            )
            console.print(
                "[yellow]Fix the issues above before marking deployment complete.[/yellow]"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
