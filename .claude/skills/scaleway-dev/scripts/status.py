#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "paramiko", "httpx"]
# ///
"""
Status Check Script

Checks if everything is running properly.
For Claude to use silently - only show results if there's a problem.
"""

import subprocess
import sys
from pathlib import Path

import click
import httpx
import paramiko
from rich.console import Console
from rich.table import Table

console = Console()


def get_server_ip() -> str | None:
    """Get server IP from GitHub secrets via gh CLI."""
    try:
        # We can't read secret values, so check environment or local cache
        result = subprocess.run(
            ["gh", "secret", "list", "--json", "name"],
            capture_output=True,
            text=True,
            check=True,
        )
        import json
        secrets = json.loads(result.stdout)
        secret_names = [s["name"] for s in secrets]

        if "SCW_SERVER_IP" in secret_names:
            # Try to get from local cache file
            cache_file = Path.home() / ".cache" / "scaleway-deploy" / "server_ip"
            if cache_file.exists():
                return cache_file.read_text().strip()

        return None
    except Exception:
        return None


def get_ssh_key() -> str | None:
    """Get SSH private key path."""
    cache_dir = Path.home() / ".cache" / "scaleway-deploy"
    key_file = cache_dir / "id_ed25519"
    if key_file.exists():
        return str(key_file)
    return None


def check_server_reachable(ip: str) -> bool:
    """Check if server responds to ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", ip],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_ssh_access(ip: str, key_path: str | None) -> bool:
    """Check if SSH access works."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {"hostname": ip, "username": "root", "timeout": 10}
        if key_path:
            connect_kwargs["key_filename"] = key_path
        else:
            # Try default keys
            default_key = Path.home() / ".ssh" / "id_ed25519"
            if default_key.exists():
                connect_kwargs["key_filename"] = str(default_key)

        client.connect(**connect_kwargs)
        client.close()
        return True
    except Exception:
        return False


def check_docker_running(ip: str, key_path: str | None) -> tuple[bool, list[str]]:
    """Check if Docker containers are running."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {"hostname": ip, "username": "root", "timeout": 10}
        if key_path:
            connect_kwargs["key_filename"] = key_path

        client.connect(**connect_kwargs)
        stdin, stdout, stderr = client.exec_command("docker ps --format '{{.Names}}: {{.Status}}'")
        output = stdout.read().decode().strip()
        client.close()

        if output:
            containers = output.split("\n")
            return True, containers
        return True, []
    except Exception as e:
        return False, [str(e)]


def check_app_health(ip: str, port: int = 8000) -> bool:
    """Check if app health endpoint responds."""
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"http://{ip}:{port}/health")
            return response.status_code == 200
    except Exception:
        return False


@click.command()
@click.option("--ip", help="Server IP (auto-detected if not provided)")
@click.option("--port", default=8000, help="App port")
@click.option("--quiet", "-q", is_flag=True, help="Only output if there's a problem")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def main(ip: str | None, port: int, quiet: bool, json_output: bool):
    """
    Check deployment status.

    Returns exit code 0 if everything is OK, 1 if there's a problem.
    """
    if not ip:
        ip = get_server_ip()

    if not ip:
        if json_output:
            print('{"status": "error", "message": "Server IP not found"}')
        elif not quiet:
            console.print("[red]Server IP not found. Run setup first.[/red]")
        sys.exit(1)

    key_path = get_ssh_key()
    results = {}

    # Run checks
    results["server_reachable"] = check_server_reachable(ip)
    results["ssh_access"] = check_ssh_access(ip, key_path) if results["server_reachable"] else False

    if results["ssh_access"]:
        docker_ok, containers = check_docker_running(ip, key_path)
        results["docker_running"] = docker_ok
        results["containers"] = containers
    else:
        results["docker_running"] = False
        results["containers"] = []

    results["app_healthy"] = check_app_health(ip, port) if results["server_reachable"] else False

    # Determine overall status
    all_ok = all([
        results["server_reachable"],
        results["ssh_access"],
        results["docker_running"],
        results["app_healthy"],
    ])

    if json_output:
        import json
        print(json.dumps({"status": "ok" if all_ok else "error", "checks": results}))
        sys.exit(0 if all_ok else 1)

    if quiet and all_ok:
        sys.exit(0)

    # Display results
    table = Table(title=f"Status: {ip}")
    table.add_column("Check", style="cyan")
    table.add_column("Status")

    checks = [
        ("Server Reachable", results["server_reachable"]),
        ("SSH Access", results["ssh_access"]),
        ("Docker Running", results["docker_running"]),
        ("App Healthy", results["app_healthy"]),
    ]

    for name, ok in checks:
        status = "[green]✓ OK[/green]" if ok else "[red]✗ FAIL[/red]"
        table.add_row(name, status)

    console.print(table)

    if results.get("containers"):
        console.print("\n[bold]Containers:[/bold]")
        for c in results["containers"]:
            console.print(f"  {c}")

    if all_ok:
        console.print(f"\n[green]Everything is running![/green] http://{ip}:{port}")
    else:
        console.print("\n[red]Some checks failed.[/red]")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
