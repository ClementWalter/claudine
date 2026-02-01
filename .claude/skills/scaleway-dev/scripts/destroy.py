#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "requests"]
# ///
"""
Infrastructure Destroy Script

Tears down all Scaleway resources.
ALWAYS asks for confirmation - this is destructive!
"""

import subprocess
import sys
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def get_credentials() -> tuple[str, str, str] | None:
    """Get Scaleway credentials. Returns (access_key, secret_key, project_id) or None."""
    # Try environment variables
    access_key = subprocess.run(
        ["gh", "secret", "list", "--json", "name"],
        capture_output=True,
        text=True,
    )

    # For destruction, we need the actual credentials
    # Check if they're in environment
    import os
    access_key = os.environ.get("SCW_ACCESS_KEY")
    secret_key = os.environ.get("SCW_SECRET_KEY")
    project_id = os.environ.get("SCW_PROJECT_ID")

    if access_key and secret_key and project_id:
        return access_key, secret_key, project_id

    return None


def list_resources(secret_key: str, project_id: str) -> dict:
    """List all Scaleway resources in the project."""
    headers = {
        "X-Auth-Token": secret_key,
        "Content-Type": "application/json",
    }

    resources = {
        "servers": [],
        "ips": [],
        "volumes": [],
        "ssh_keys": [],
    }

    # List servers
    servers_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers?project={project_id}"
    resp = requests.get(servers_url, headers=headers)
    if resp.status_code == 200:
        resources["servers"] = resp.json().get("servers", [])

    # List IPs
    ips_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/ips?project={project_id}"
    resp = requests.get(ips_url, headers=headers)
    if resp.status_code == 200:
        resources["ips"] = resp.json().get("ips", [])

    # List volumes
    volumes_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/volumes?project={project_id}"
    resp = requests.get(volumes_url, headers=headers)
    if resp.status_code == 200:
        resources["volumes"] = resp.json().get("volumes", [])

    return resources


def delete_server(secret_key: str, server_id: str) -> bool:
    """Delete a server."""
    headers = {"X-Auth-Token": secret_key}

    # First, power off
    action_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers/{server_id}/action"
    requests.post(action_url, headers=headers, json={"action": "poweroff"})

    # Wait a bit
    import time
    time.sleep(5)

    # Delete
    delete_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers/{server_id}"
    resp = requests.delete(delete_url, headers=headers)
    return resp.status_code in (200, 204)


def delete_ip(secret_key: str, ip_id: str) -> bool:
    """Delete an IP."""
    headers = {"X-Auth-Token": secret_key}
    url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/ips/{ip_id}"
    resp = requests.delete(url, headers=headers)
    return resp.status_code in (200, 204)


def delete_volume(secret_key: str, volume_id: str) -> bool:
    """Delete a volume."""
    headers = {"X-Auth-Token": secret_key}
    url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/volumes/{volume_id}"
    resp = requests.delete(url, headers=headers)
    return resp.status_code in (200, 204)


def clear_github_secrets() -> bool:
    """Remove Scaleway secrets from GitHub."""
    secrets_to_remove = [
        "SCW_SERVER_IP",
        # Keep credentials in case user wants to redeploy
        # "SCW_ACCESS_KEY",
        # "SCW_SECRET_KEY",
        # "SCW_PROJECT_ID",
    ]

    for secret in secrets_to_remove:
        try:
            subprocess.run(
                ["gh", "secret", "delete", secret, "--yes"],
                capture_output=True,
            )
        except Exception:
            pass

    return True


def clear_local_cache():
    """Clear local cache files."""
    cache_dir = Path.home() / ".cache" / "scaleway-deploy"
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)


@click.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation (DANGEROUS)")
@click.option("--keep-credentials", is_flag=True, help="Keep Scaleway credentials in GitHub")
def main(force: bool, keep_credentials: bool):
    """
    Destroy all Scaleway infrastructure.

    This will DELETE your server and all data on it. This cannot be undone!
    """
    console.print(
        Panel(
            "[red bold]WARNING: This will destroy your server![/red bold]\n\n"
            "All data will be permanently deleted.\n"
            "This action cannot be undone.",
            title="Destroy Infrastructure",
            border_style="red",
        )
    )

    if not force:
        if not Confirm.ask("\n[red]Are you sure you want to destroy everything?[/red]"):
            console.print("[dim]Cancelled.[/dim]")
            sys.exit(0)

        # Double confirmation
        console.print("\n[yellow]Type 'destroy' to confirm:[/yellow]")
        confirmation = input("> ").strip().lower()
        if confirmation != "destroy":
            console.print("[dim]Cancelled.[/dim]")
            sys.exit(0)

    # Get credentials
    creds = get_credentials()
    if not creds:
        console.print("[yellow]Credentials not found in environment.[/yellow]")
        console.print("Please provide them:")
        access_key = click.prompt("Access Key")
        secret_key = click.prompt("Secret Key", hide_input=True)
        project_id = click.prompt("Project ID")
        creds = (access_key, secret_key, project_id)

    access_key, secret_key, project_id = creds

    console.print("\n[bold]Finding resources...[/bold]")
    resources = list_resources(secret_key, project_id)

    total = (
        len(resources["servers"])
        + len(resources["ips"])
        + len(resources["volumes"])
    )

    if total == 0:
        console.print("[green]No resources found. Nothing to destroy.[/green]")
        clear_local_cache()
        sys.exit(0)

    console.print(f"Found: {len(resources['servers'])} servers, {len(resources['ips'])} IPs, {len(resources['volumes'])} volumes")

    # Delete servers first
    for server in resources["servers"]:
        console.print(f"  Deleting server: {server['name']}...")
        if delete_server(secret_key, server["id"]):
            console.print(f"  [green]✓[/green] Deleted {server['name']}")
        else:
            console.print(f"  [red]✗[/red] Failed to delete {server['name']}")

    # Delete IPs
    for ip in resources["ips"]:
        if not ip.get("server"):  # Only delete unattached IPs
            console.print(f"  Deleting IP: {ip['address']}...")
            delete_ip(secret_key, ip["id"])

    # Delete volumes
    for volume in resources["volumes"]:
        if not volume.get("server"):  # Only delete unattached volumes
            console.print(f"  Deleting volume: {volume['name']}...")
            delete_volume(secret_key, volume["id"])

    # Clear GitHub secrets
    console.print("\nClearing cached data...")
    clear_github_secrets()
    clear_local_cache()

    console.print("\n[green bold]Done![/green bold] All infrastructure has been destroyed.")

    if keep_credentials:
        console.print("[dim]Credentials kept in GitHub for future deployments.[/dim]")
    else:
        console.print("[dim]Run setup again when you want to redeploy.[/dim]")


if __name__ == "__main__":
    main()
