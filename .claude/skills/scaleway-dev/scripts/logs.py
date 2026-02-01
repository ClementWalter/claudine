#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "paramiko"]
# ///
"""
Log Viewer Script

Fetches and displays application logs from the server.
Simple interface - just shows the logs.
"""

import subprocess
import sys
from pathlib import Path

import click
import paramiko
from rich.console import Console
from rich.syntax import Syntax

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
    # Try default
    default_key = Path.home() / ".ssh" / "id_ed25519"
    if default_key.exists():
        return str(default_key)
    return None


def ssh_exec(ip: str, key_path: str | None, command: str) -> tuple[str, int]:
    """Execute command over SSH."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {"hostname": ip, "username": "root", "timeout": 10}
        if key_path:
            connect_kwargs["key_filename"] = key_path

        client.connect(**connect_kwargs)
        stdin, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode() + stderr.read().decode()
        client.close()
        return output, exit_code
    except Exception as e:
        return str(e), 1


@click.command()
@click.option("--ip", help="Server IP (auto-detected if not provided)")
@click.option("--tail", "-n", default=100, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output (Ctrl+C to stop)")
@click.option("--service", "-s", help="Specific service name (default: all)")
@click.option("--since", help="Show logs since (e.g., '1h', '30m', '2023-01-01')")
def main(ip: str | None, tail: int, follow: bool, service: str | None, since: str | None):
    """
    View application logs.

    Shows the most recent logs from your deployed application.
    """
    if not ip:
        ip = get_server_ip()

    if not ip:
        console.print("[red]Server IP not found. Is your app deployed?[/red]")
        sys.exit(1)

    key_path = get_ssh_key()

    # Build docker compose logs command
    cmd = "cd /opt/app && docker compose logs"

    if service:
        cmd += f" {service}"

    if tail and not follow:
        cmd += f" --tail={tail}"

    if since:
        cmd += f" --since={since}"

    if follow:
        cmd += " -f"
        console.print(f"[dim]Streaming logs from {ip}... (Ctrl+C to stop)[/dim]\n")

        # For follow mode, we need to stream
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {"hostname": ip, "username": "root", "timeout": 10}
            if key_path:
                connect_kwargs["key_filename"] = key_path

            client.connect(**connect_kwargs)
            stdin, stdout, stderr = client.exec_command(cmd)

            try:
                for line in iter(stdout.readline, ""):
                    if line:
                        console.print(line, end="")
            except KeyboardInterrupt:
                console.print("\n[dim]Stopped.[/dim]")

            client.close()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    else:
        output, code = ssh_exec(ip, key_path, cmd)

        if code != 0:
            console.print(f"[red]Error getting logs:[/red]\n{output}")
            sys.exit(1)

        if output.strip():
            console.print(output)
        else:
            console.print("[yellow]No logs found. Is your app running?[/yellow]")
            console.print("[dim]Tip: Run 'status' to check if containers are running.[/dim]")


if __name__ == "__main__":
    main()
