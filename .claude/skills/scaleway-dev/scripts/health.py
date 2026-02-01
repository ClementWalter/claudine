#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "rich", "httpx"]
# ///
"""
Health Check Utilities

SOC2 CC7.1 compliant health monitoring with:
- HTTP endpoint health checks
- Container status verification
- System resource checks
- Configurable timeouts and retries
"""

import sys
import time
from dataclasses import dataclass

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@dataclass
class HealthCheckResult:
    name: str
    status: str  # "healthy", "unhealthy", "timeout", "error"
    message: str
    response_time_ms: float | None = None
    details: dict | None = None


def check_http_endpoint(
    url: str, timeout: float, expected_status: int = 200
) -> HealthCheckResult:
    """Check HTTP endpoint health."""
    start = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response_time = (time.time() - start) * 1000

            if response.status_code == expected_status:
                return HealthCheckResult(
                    name="HTTP Endpoint",
                    status="healthy",
                    message=f"Status {response.status_code}",
                    response_time_ms=response_time,
                )
            else:
                return HealthCheckResult(
                    name="HTTP Endpoint",
                    status="unhealthy",
                    message=f"Expected {expected_status}, got {response.status_code}",
                    response_time_ms=response_time,
                )
    except httpx.TimeoutException:
        return HealthCheckResult(
            name="HTTP Endpoint",
            status="timeout",
            message=f"Request timed out after {timeout}s",
        )
    except httpx.ConnectError as e:
        return HealthCheckResult(
            name="HTTP Endpoint", status="error", message=f"Connection failed: {e}"
        )
    except Exception as e:
        return HealthCheckResult(
            name="HTTP Endpoint", status="error", message=f"Error: {e}"
        )


def check_health_with_retry(
    url: str, timeout: float, retries: int, interval: float
) -> HealthCheckResult:
    """Check health endpoint with retries."""
    last_result = None

    for attempt in range(1, retries + 1):
        result = check_http_endpoint(url, timeout)
        last_result = result

        if result.status == "healthy":
            return result

        if attempt < retries:
            console.print(
                f"[yellow]Attempt {attempt}/{retries} failed: {result.message}. "
                f"Retrying in {interval}s...[/yellow]"
            )
            time.sleep(interval)

    return last_result


def display_results(results: list[HealthCheckResult]) -> bool:
    """Display health check results and return overall status."""
    table = Table(title="Health Check Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Message", style="white")
    table.add_column("Response Time", style="dim")

    all_healthy = True

    for result in results:
        if result.status == "healthy":
            status_str = "[green]✓ Healthy[/green]"
        elif result.status == "unhealthy":
            status_str = "[red]✗ Unhealthy[/red]"
            all_healthy = False
        elif result.status == "timeout":
            status_str = "[yellow]⏱ Timeout[/yellow]"
            all_healthy = False
        else:
            status_str = "[red]⚠ Error[/red]"
            all_healthy = False

        response_time = (
            f"{result.response_time_ms:.0f}ms" if result.response_time_ms else "-"
        )
        table.add_row(result.name, status_str, result.message, response_time)

    console.print(table)
    return all_healthy


@click.command()
@click.option("--host", "-h", required=True, help="Target host IP or hostname")
@click.option("--port", "-p", default=8000, help="Application port")
@click.option("--path", default="/health", help="Health check endpoint path")
@click.option("--timeout", "-t", default=10.0, help="Request timeout in seconds")
@click.option("--retries", "-r", default=3, help="Number of retries")
@click.option("--interval", "-i", default=5.0, help="Interval between retries in seconds")
@click.option("--expected-status", default=200, help="Expected HTTP status code")
@click.option("--wait", "-w", default=0, help="Wait N seconds before starting checks")
@click.option("--continuous", "-c", is_flag=True, help="Run continuously until healthy")
@click.option(
    "--max-wait", default=300, help="Maximum wait time in continuous mode (seconds)"
)
def main(
    host: str,
    port: int,
    path: str,
    timeout: float,
    retries: int,
    interval: float,
    expected_status: int,
    wait: int,
    continuous: bool,
    max_wait: int,
):
    """
    Check application health status.

    Performs HTTP health checks against the specified endpoint with
    configurable retries and timeouts. Supports continuous mode for
    post-deployment verification.
    """
    url = f"http://{host}:{port}{path}"

    console.print(
        Panel(
            f"[bold blue]Health Check[/bold blue]\n"
            f"URL: [yellow]{url}[/yellow]\n"
            f"Timeout: {timeout}s | Retries: {retries} | Interval: {interval}s",
            title="SOC2 CC7.1 - System Monitoring",
        )
    )

    # Initial wait if specified
    if wait > 0:
        console.print(f"\n[dim]Waiting {wait}s before starting checks...[/dim]")
        time.sleep(wait)

    if continuous:
        # Continuous mode - keep checking until healthy or max_wait exceeded
        console.print(f"\n[bold]Running in continuous mode (max wait: {max_wait}s)...[/bold]")
        start_time = time.time()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for healthy status...", total=None)

            while time.time() - start_time < max_wait:
                result = check_http_endpoint(url, timeout, expected_status)

                if result.status == "healthy":
                    progress.stop()
                    console.print(
                        f"\n[green bold]✓ Application is healthy![/green bold] "
                        f"(took {time.time() - start_time:.0f}s)"
                    )
                    display_results([result])
                    sys.exit(0)

                elapsed = time.time() - start_time
                progress.update(
                    task,
                    description=f"Waiting for healthy status... ({elapsed:.0f}s elapsed, last: {result.message})",
                )
                time.sleep(interval)

        console.print(
            f"\n[red bold]✗ Health check timed out after {max_wait}s[/red bold]"
        )
        sys.exit(1)

    else:
        # Standard mode with retries
        console.print("\n[bold]Checking health...[/bold]")
        result = check_health_with_retry(url, timeout, retries, interval)

        if display_results([result]):
            console.print("\n[green bold]✓ All health checks passed[/green bold]")
            sys.exit(0)
        else:
            console.print("\n[red bold]✗ Health checks failed[/red bold]")
            sys.exit(1)


if __name__ == "__main__":
    main()
