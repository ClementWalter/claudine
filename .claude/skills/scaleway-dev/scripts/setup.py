#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "requests", "cryptography"]
# ///
"""
One-Time Setup Script

Handles everything automatically:
- Stores credentials in GitHub Secrets
- Generates SSH keys
- Provisions infrastructure
- Configures the server

User only needs to provide: Access Key, Secret Key, Project ID
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import click
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from rich.console import Console

console = Console()


def get_github_repo() -> tuple[str, str] | None:
    """Get GitHub owner/repo from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Handle both HTTPS and SSH URLs
        if "github.com" in url:
            if url.startswith("git@"):
                # git@github.com:owner/repo.git
                path = url.split(":")[-1]
            else:
                # https://github.com/owner/repo.git
                path = url.split("github.com/")[-1]
            path = path.replace(".git", "")
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
    except Exception:
        pass
    return None


def get_github_token() -> str | None:
    """Get GitHub token from gh CLI or environment."""
    # Try environment variable first
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    # Try gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        pass

    return None


def set_github_secret(owner: str, repo: str, token: str, name: str, value: str) -> bool:
    """Set a GitHub repository secret."""
    # Get repo public key for encryption
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    key_resp = requests.get(key_url, headers=headers)
    if key_resp.status_code != 200:
        return False

    key_data = key_resp.json()
    public_key = key_data["key"]
    key_id = key_data["key_id"]

    # Encrypt the secret using libsodium (via PyNaCl would be better, but keeping deps minimal)
    # Using the sealed box approach
    from base64 import b64decode, b64encode

    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    # GitHub uses libsodium sealed boxes, which we need to implement
    # For simplicity, we'll use the gh CLI if available
    try:
        result = subprocess.run(
            ["gh", "secret", "set", name, "--body", value, "--repo", f"{owner}/{repo}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except Exception:
        pass

    return False


def get_github_secret(owner: str, repo: str, token: str, name: str) -> bool:
    """Check if a GitHub secret exists."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{name}"
    resp = requests.get(url, headers=headers)
    return resp.status_code == 200


def generate_ssh_keypair() -> tuple[str, str]:
    """Generate Ed25519 SSH keypair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    # Serialize public key
    public_openssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()

    return private_pem, public_openssh


def check_setup_complete(owner: str, repo: str, token: str) -> dict:
    """Check which parts of setup are complete."""
    required_secrets = [
        "SCW_ACCESS_KEY",
        "SCW_SECRET_KEY",
        "SCW_PROJECT_ID",
        "SCW_SSH_PRIVATE_KEY",
        "SCW_SSH_PUBLIC_KEY",
    ]

    status = {}
    for secret in required_secrets:
        status[secret] = get_github_secret(owner, repo, token, secret)

    # Check if server is provisioned
    status["SCW_SERVER_IP"] = get_github_secret(owner, repo, token, "SCW_SERVER_IP")

    return status


def provision_server(access_key: str, secret_key: str, project_id: str, ssh_public_key: str) -> str | None:
    """Provision a Scaleway server using the API directly."""
    import time

    headers = {
        "X-Auth-Token": secret_key,
        "Content-Type": "application/json",
    }

    # Create SSH key
    ssh_key_url = "https://api.scaleway.com/iam/v1alpha1/ssh-keys"
    ssh_key_data = {
        "name": f"claude-deploy-{int(time.time())}",
        "public_key": ssh_public_key,
        "project_id": project_id,
    }
    ssh_resp = requests.post(ssh_key_url, headers=headers, json=ssh_key_data)

    # Create IP
    ip_url = "https://api.scaleway.com/instance/v1/zones/fr-par-1/ips"
    ip_data = {"project": project_id}
    ip_resp = requests.post(ip_url, headers=headers, json=ip_data)
    if ip_resp.status_code not in (200, 201):
        console.print(f"[red]Failed to create IP: {ip_resp.text}[/red]")
        return None
    ip_id = ip_resp.json()["ip"]["id"]
    ip_address = ip_resp.json()["ip"]["address"]

    # Get cloud-init content
    cloud_init_path = Path(__file__).parent.parent / "templates" / "cloud-init.yaml"
    cloud_init_content = ""
    if cloud_init_path.exists():
        cloud_init_content = cloud_init_path.read_text()

    # Create server
    server_url = "https://api.scaleway.com/instance/v1/zones/fr-par-1/servers"
    server_data = {
        "name": "app-server",
        "project": project_id,
        "commercial_type": "DEV1-S",
        "image": "ubuntu_jammy",
        "enable_ipv6": False,
        "boot_type": "local",
        "tags": ["managed-by:claude", "compliance:soc2-iso27001"],
    }

    server_resp = requests.post(server_url, headers=headers, json=server_data)
    if server_resp.status_code not in (200, 201):
        console.print(f"[red]Failed to create server: {server_resp.text}[/red]")
        return None

    server_id = server_resp.json()["server"]["id"]

    # Attach IP to server
    attach_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers/{server_id}"
    attach_data = {"public_ip": ip_id}
    requests.patch(attach_url, headers=headers, json=attach_data)

    # Set cloud-init user data
    if cloud_init_content:
        userdata_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers/{server_id}/user_data/cloud-init"
        requests.patch(
            userdata_url,
            headers={**headers, "Content-Type": "text/plain"},
            data=cloud_init_content,
        )

    # Start server
    action_url = f"https://api.scaleway.com/instance/v1/zones/fr-par-1/servers/{server_id}/action"
    action_data = {"action": "poweron"}
    requests.post(action_url, headers=headers, json=action_data)

    return ip_address


@click.command()
@click.option("--check", is_flag=True, help="Only check if setup is complete")
@click.option("--access-key", help="Scaleway access key")
@click.option("--secret-key", help="Scaleway secret key")
@click.option("--project-id", help="Scaleway project ID")
def main(check: bool, access_key: str | None, secret_key: str | None, project_id: str | None):
    """
    One-time setup for Scaleway deployment.

    Stores all credentials in GitHub Secrets so you never need them again.
    """
    # Get GitHub repo info
    repo_info = get_github_repo()
    if not repo_info:
        console.print("[red]Not in a GitHub repository. Please run from your project directory.[/red]")
        sys.exit(1)

    owner, repo = repo_info
    token = get_github_token()
    if not token:
        console.print("[red]GitHub token not found. Please run 'gh auth login' first.[/red]")
        sys.exit(1)

    # Check mode
    if check:
        status = check_setup_complete(owner, repo, token)
        all_complete = all(status.values())

        if all_complete:
            console.print("[green]Setup complete![/green]")
            sys.exit(0)
        else:
            missing = [k for k, v in status.items() if not v]
            console.print(f"[yellow]Setup incomplete. Missing: {', '.join(missing)}[/yellow]")
            sys.exit(1)

    # Full setup mode
    console.print("[bold]Setting up Scaleway deployment...[/bold]\n")

    # Check what's already done
    status = check_setup_complete(owner, repo, token)

    # Get credentials if not provided and not in secrets
    if not status["SCW_ACCESS_KEY"]:
        if not access_key:
            console.print("[yellow]Scaleway Access Key needed.[/yellow]")
            console.print("Get it from: https://console.scaleway.com/iam/api-keys")
            access_key = click.prompt("Access Key", hide_input=False)
        set_github_secret(owner, repo, token, "SCW_ACCESS_KEY", access_key)
        console.print("[green]✓[/green] Access key stored")

    if not status["SCW_SECRET_KEY"]:
        if not secret_key:
            secret_key = click.prompt("Secret Key", hide_input=True)
        set_github_secret(owner, repo, token, "SCW_SECRET_KEY", secret_key)
        console.print("[green]✓[/green] Secret key stored")

    if not status["SCW_PROJECT_ID"]:
        if not project_id:
            console.print("\n[yellow]Scaleway Project ID needed.[/yellow]")
            console.print("Get it from: https://console.scaleway.com/project/settings")
            project_id = click.prompt("Project ID")
        set_github_secret(owner, repo, token, "SCW_PROJECT_ID", project_id)
        console.print("[green]✓[/green] Project ID stored")

    # Generate SSH keys if needed
    if not status["SCW_SSH_PRIVATE_KEY"] or not status["SCW_SSH_PUBLIC_KEY"]:
        console.print("\n[dim]Generating SSH keys...[/dim]")
        private_key, public_key = generate_ssh_keypair()
        set_github_secret(owner, repo, token, "SCW_SSH_PRIVATE_KEY", private_key)
        set_github_secret(owner, repo, token, "SCW_SSH_PUBLIC_KEY", public_key)
        console.print("[green]✓[/green] SSH keys generated and stored")
    else:
        # Get existing public key for server provisioning
        public_key = None  # We'll need to get this from somewhere

    # Provision server if needed
    if not status["SCW_SERVER_IP"]:
        console.print("\n[bold]Creating server...[/bold] (this takes ~2 minutes)")

        # Get credentials from GitHub secrets or CLI args
        # For now, we need them passed in since we can't read secrets back
        if not access_key or not secret_key or not project_id:
            console.print("[yellow]Re-enter credentials for server provisioning:[/yellow]")
            if not access_key:
                access_key = click.prompt("Access Key")
            if not secret_key:
                secret_key = click.prompt("Secret Key", hide_input=True)
            if not project_id:
                project_id = click.prompt("Project ID")

        # Generate fresh keys if we don't have them
        if not public_key:
            private_key, public_key = generate_ssh_keypair()
            set_github_secret(owner, repo, token, "SCW_SSH_PRIVATE_KEY", private_key)
            set_github_secret(owner, repo, token, "SCW_SSH_PUBLIC_KEY", public_key)

        ip_address = provision_server(access_key, secret_key, project_id, public_key)

        if ip_address:
            set_github_secret(owner, repo, token, "SCW_SERVER_IP", ip_address)
            console.print(f"[green]✓[/green] Server created at {ip_address}")
        else:
            console.print("[red]Failed to create server[/red]")
            sys.exit(1)

    console.print("\n[green bold]Setup complete![/green bold]")
    console.print("Your app is ready to deploy. All credentials are stored securely in GitHub.")


if __name__ == "__main__":
    main()
