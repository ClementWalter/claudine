#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "paramiko", "boto3"]
# ///
"""
Application Deployment Script

Simple deployment with --auto mode for zero-config operation.
All the compliance stuff happens silently in the background.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
import click
import paramiko
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def get_server_ip() -> str | None:
    """Get server IP from local cache."""
    cache_file = Path.home() / ".cache" / "scaleway-deploy" / "server_ip"
    if cache_file.exists():
        return cache_file.read_text().strip()
    return None


def get_ssh_key() -> str | None:
    """Get SSH private key path."""
    cache_dir = Path.home() / ".cache" / "scaleway-deploy"
    key_file = cache_dir / "id_ed25519"
    if key_file.exists():
        return str(key_file)
    default_key = Path.home() / ".ssh" / "id_ed25519"
    if default_key.exists():
        return str(default_key)
    return None


def find_dockerfile() -> Path | None:
    """Find Dockerfile in current directory."""
    candidates = ["Dockerfile", "dockerfile", "Dockerfile.prod", "docker/Dockerfile"]
    for name in candidates:
        path = Path(name)
        if path.exists():
            return path
    return None


def find_compose_file() -> Path | None:
    """Find docker-compose file."""
    candidates = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.prod.yml",
        "compose.yml",
        "compose.yaml",
    ]
    for name in candidates:
        path = Path(name)
        if path.exists():
            return path
    return None


def get_app_name() -> str:
    """Get app name from package.json, pyproject.toml, or directory name."""
    if Path("package.json").exists():
        data = json.loads(Path("package.json").read_text())
        if "name" in data:
            return data["name"]

    if Path("pyproject.toml").exists():
        content = Path("pyproject.toml").read_text()
        for line in content.split("\n"):
            if line.startswith("name"):
                return line.split("=")[1].strip().strip('"').strip("'")

    return Path.cwd().name


def get_version() -> str:
    """Get version from git or timestamp."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return datetime.now().strftime("%Y%m%d-%H%M%S")


def ssh_connect(host: str, user: str, key_path: str | None = None) -> paramiko.SSHClient:
    """Create SSH connection."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {"hostname": host, "username": user, "timeout": 30}
    if key_path:
        connect_kwargs["key_filename"] = key_path

    client.connect(**connect_kwargs)
    return client


def ssh_exec(client: paramiko.SSHClient, command: str) -> tuple[str, str, int]:
    """Execute command over SSH."""
    stdin, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return stdout.read().decode(), stderr.read().decode(), exit_code


def docker_login(registry: str, secret_key: str) -> bool:
    """Login to container registry."""
    try:
        subprocess.run(
            ["docker", "login", registry, "-u", "nologin", "--password-stdin"],
            input=secret_key,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except Exception:
        return False


def build_image(dockerfile: Path, image: str, quiet: bool = False) -> bool:
    """Build Docker image."""
    cmd = ["docker", "build", "-t", image, "-f", str(dockerfile), "."]
    try:
        if quiet:
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            subprocess.run(cmd, check=True)
        return True
    except Exception:
        return False


def push_image(image: str, quiet: bool = False) -> bool:
    """Push Docker image."""
    try:
        if quiet:
            subprocess.run(["docker", "push", image], capture_output=True, check=True)
        else:
            subprocess.run(["docker", "push", image], check=True)
        return True
    except Exception:
        return False


def deploy_to_server(
    client: paramiko.SSHClient,
    image: str,
    app_name: str,
    version: str,
    port: int,
) -> bool:
    """Deploy to remote server."""
    # Create app directory
    ssh_exec(client, "mkdir -p /opt/app")

    # Create .env file
    env_content = f"""APP_NAME={app_name}
APP_VERSION={version}
APP_ENV=production
APP_PORT={port}
"""
    ssh_exec(client, f"cat > /opt/app/.env << 'EOF'\n{env_content}EOF")

    # Create minimal docker-compose if none exists
    compose_check, _, _ = ssh_exec(client, "test -f /opt/app/docker-compose.yml && echo exists")
    if "exists" not in compose_check:
        compose_content = f"""version: "3.8"
services:
  app:
    image: {image}
    container_name: {app_name}
    restart: unless-stopped
    ports:
      - "{port}:{port}"
    environment:
      - APP_ENV=production
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "5"
"""
        ssh_exec(client, f"cat > /opt/app/docker-compose.yml << 'EOF'\n{compose_content}EOF")

    # Pull and deploy
    stdout, stderr, code = ssh_exec(client, f"docker pull {image}")
    if code != 0:
        return False

    stdout, stderr, code = ssh_exec(client, "cd /opt/app && docker compose up -d --remove-orphans")
    return code == 0


def wait_for_health(client: paramiko.SSHClient, port: int, timeout: int = 120) -> bool:
    """Wait for app to be healthy."""
    start = time.time()
    while time.time() - start < timeout:
        stdout, stderr, code = ssh_exec(
            client, f"curl -sf http://localhost:{port}/health || curl -sf http://localhost:{port}/ || exit 1"
        )
        if code == 0:
            return True
        time.sleep(5)
    return False


def save_audit_log(host: str, image: str, version: str, status: str):
    """Save deployment audit log (silently, for compliance)."""
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "deploy",
        "host": host,
        "image": image,
        "version": version,
        "status": status,
        "user": os.environ.get("USER", "unknown"),
    }

    log_file = log_dir / "deploy-audit.json"
    logs = []
    if log_file.exists():
        try:
            logs = json.loads(log_file.read_text())
        except Exception:
            pass
    logs.append(log_entry)
    log_file.write_text(json.dumps(logs, indent=2))


@click.command()
@click.option("--auto", is_flag=True, help="Auto-detect everything, minimal output")
@click.option("--host", "-h", help="Server IP (auto-detected if not provided)")
@click.option("--image", "-i", help="Docker image name")
@click.option("--version", "-v", help="Version tag")
@click.option("--port", "-p", default=8000, help="App port")
@click.option("--skip-build", is_flag=True, help="Skip build, just deploy existing image")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
def main(
    auto: bool,
    host: str | None,
    image: str | None,
    version: str | None,
    port: int,
    skip_build: bool,
    quiet: bool,
):
    """
    Deploy your application.

    With --auto flag, everything is detected automatically.
    Just run: uv run deploy.py --auto
    """
    if auto:
        quiet = True

    # Auto-detect host
    if not host:
        host = get_server_ip()
        if not host:
            if not quiet:
                console.print("[red]Server not found. Run setup first.[/red]")
            sys.exit(1)

    # Auto-detect app name and version
    app_name = get_app_name()
    if not version:
        version = get_version()

    # Auto-detect image name
    if not image:
        registry = os.environ.get("SCW_REGISTRY_ENDPOINT", "rg.fr-par.scw.cloud")
        namespace = os.environ.get("SCW_REGISTRY_NAMESPACE", app_name)
        image = f"{registry}/{namespace}/{app_name}:{version}"

    # Find Dockerfile
    dockerfile = find_dockerfile()

    if not quiet:
        console.print(f"[bold]Deploying {app_name} v{version}[/bold]")
        console.print(f"[dim]To: {host}[/dim]")

    ssh_key = get_ssh_key()
    final_status = "failed"

    try:
        # Build if Dockerfile exists and not skipped
        if dockerfile and not skip_build:
            if not quiet:
                console.print("Building...")
            else:
                console.print("Deploying...", end=" ", flush=True)

            # Login to registry
            secret_key = os.environ.get("SCW_SECRET_KEY")
            if secret_key:
                registry = os.environ.get("SCW_REGISTRY_ENDPOINT", "rg.fr-par.scw.cloud")
                docker_login(registry, secret_key)

            if not build_image(dockerfile, image, quiet):
                if not quiet:
                    console.print("[red]Build failed[/red]")
                sys.exit(1)

            if not push_image(image, quiet):
                if not quiet:
                    console.print("[red]Push failed[/red]")
                sys.exit(1)

        # Connect and deploy
        if not quiet:
            console.print("Deploying to server...")

        client = ssh_connect(host, "root", ssh_key)

        if not deploy_to_server(client, image, app_name, version, port):
            if not quiet:
                console.print("[red]Deployment failed[/red]")
            client.close()
            sys.exit(1)

        # Wait for health
        if not quiet:
            console.print("Waiting for app to start...")

        if wait_for_health(client, port):
            final_status = "success"
            if quiet:
                console.print(f"[green]Done![/green] http://{host}:{port}")
            else:
                console.print(
                    Panel(
                        f"[green bold]Deployed successfully![/green bold]\n\n"
                        f"Your app is live at: http://{host}:{port}",
                        title="Success",
                    )
                )
        else:
            if not quiet:
                console.print("[yellow]App deployed but health check timed out.[/yellow]")
                console.print(f"Check logs: uv run .claude/skills/scaleway-dev/scripts/logs.py --ip {host}")
            final_status = "deployed_unhealthy"

        client.close()

    except Exception as e:
        if not quiet:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    finally:
        # Silent audit logging for compliance
        save_audit_log(host, image, version, final_status)

    if final_status != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
