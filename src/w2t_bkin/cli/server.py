"""Server management commands for Prefect."""

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Optional
import urllib.request
import webbrowser

import typer

from ..api import BatchFlowConfig, SessionFlowConfig
from ..flows import batch_process_flow, process_session_flow
from .utils import console, setup_logging

server_app = typer.Typer(name="server", help="Prefect server management")


@server_app.command(name="start")
def start(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Default config file for deployments"),
    work_pool: Optional[str] = typer.Option(None, "--work-pool", "-w", help="Work pool type (docker or local)"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    open_browser: bool = typer.Option(True, "--browser/--no-browser", help="Open browser automatically"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
):
    """Start Prefect server, create deployments, and open UI.

    This command:
    1. Starts the Prefect server
    2. Creates flow deployments automatically
    3. Opens the Prefect UI in your browser

    The deployments are created with a work pool that can execute flows either:
    - Using Docker containers (default, recommended)
    - Using local Python if you installed w2t-bkin[worker]

    Example:
        $ w2t-bkin server start
        $ w2t-bkin server start --config configs/standard.toml
        $ w2t-bkin server start --work-pool local --port 4200
    """
    setup_logging(log_level)

    console.print("[cyan]🚀 Starting W2T-BKIN Prefect Server...[/cyan]\n")

    # Detect if worker extras are installed
    has_worker_extras = _check_worker_extras()

    # Determine work pool type
    if work_pool is None:
        if has_worker_extras:
            work_pool = "local"
            console.print("[green]✓[/green] Worker extras detected, using local work pool")
        else:
            work_pool = "docker"
            console.print("[yellow]![/yellow] Worker extras not installed, using Docker work pool (recommended)")
            console.print("[dim]  For local workers: pip install -e .[worker] (~630 MB with ML dependencies)[/dim]")

    console.print(f"[dim]  Work pool: {work_pool}[/dim]")
    console.print(f"[dim]  Port: {port}[/dim]\n")

    # Start Prefect server in background
    console.print("[cyan]Starting Prefect server...[/cyan]")

    try:
        # Start server process
        server_process = subprocess.Popen(
            ["prefect", "server", "start", "--host", "0.0.0.0", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for server to be ready
        console.print("[dim]Waiting for server to be ready...[/dim]")
        if not _wait_for_server(port):
            console.print("[red]✗ Server failed to start[/red]")
            server_process.terminate()
            raise typer.Exit(1)

        console.print("[green]✓[/green] Prefect server started\n")

        # Create work pool
        console.print(f"[cyan]Creating work pool '{work_pool}-pool'...[/cyan]")
        _create_work_pool(work_pool)
        console.print("[green]✓[/green] Work pool created\n")

        # Create deployments
        console.print("[cyan]Creating flow deployments...[/cyan]")
        _create_deployments(work_pool, config_path)
        console.print("[green]✓[/green] Deployments created\n")

        # Open browser
        ui_url = f"http://localhost:{port}"
        if open_browser:
            console.print(f"[cyan]Opening browser to {ui_url}...[/cyan]")
            webbrowser.open(ui_url)

        console.print(f"\n[green]✅ W2T-BKIN Server Ready![/green]")
        console.print(f"\n[bold]Prefect UI:[/bold] {ui_url}")
        console.print(f"[bold]Work Pool:[/bold] {work_pool}-pool")
        console.print("\n[dim]Press Ctrl+C to stop the server[/dim]\n")

        # Keep server running
        try:
            server_process.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping server...[/yellow]")
            server_process.terminate()
            server_process.wait(timeout=5)
            console.print("[green]✓[/green] Server stopped")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logging.exception("Failed to start server")
        raise typer.Exit(1)


@server_app.command(name="stop")
def stop():
    """Stop the running Prefect server.

    Example:
        $ w2t-bkin server stop
    """
    console.print("[cyan]Stopping Prefect server...[/cyan]")

    try:
        # Find and kill prefect server processes
        result = subprocess.run(
            ["pkill", "-f", "prefect server start"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Prefect server stopped")
        else:
            console.print("[yellow]![/yellow] No running server found")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(name="status")
def status(port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port")):
    """Check if Prefect server is running.

    Example:
        $ w2t-bkin server status
        $ w2t-bkin server status --port 4200
    """
    console.print("[cyan]Checking Prefect server status...[/cyan]\n")

    try:

        health_url = f"http://localhost:{port}/api/health"

        try:
            urllib.request.urlopen(health_url, timeout=2)
            console.print(f"[green]✓[/green] Server is running at http://localhost:{port}")
            console.print(f"[dim]  UI: http://localhost:{port}[/dim]")
        except Exception:
            console.print(f"[red]✗[/red] Server is not running on port {port}")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(name="restart")
def restart(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Default config file for deployments"),
    work_pool: Optional[str] = typer.Option(None, "--work-pool", "-w", help="Work pool type (docker or local)"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
):
    """Restart Prefect server.

    Example:
        $ w2t-bkin server restart
        $ w2t-bkin server restart --work-pool docker
    """
    console.print("[cyan]Restarting Prefect server...[/cyan]\n")

    # Stop existing server
    stop()
    time.sleep(2)

    # Start new server
    start(
        config_path=config_path,
        work_pool=work_pool,
        port=port,
        open_browser=False,
        log_level=log_level,
    )


# Helper functions


def _check_worker_extras() -> bool:
    """Check if worker extras are installed."""
    try:
        import deeplabcut

        return True
    except ImportError:
        return False


def _wait_for_server(port: int, max_retries: int = 30) -> bool:
    """Wait for Prefect server to be ready."""

    health_url = f"http://localhost:{port}/api/health"

    for i in range(max_retries):
        try:
            urllib.request.urlopen(health_url, timeout=1)
            return True
        except Exception:
            time.sleep(1)

    return False


def _create_work_pool(pool_type: str):
    """Create Prefect work pool."""
    pool_name = f"{pool_type}-pool"

    # Check if pool already exists
    result = subprocess.run(["prefect", "work-pool", "inspect", pool_name], capture_output=True, text=True)

    if result.returncode == 0:
        console.print(f"[dim]  Work pool '{pool_name}' already exists[/dim]")
        return

    # Create pool
    pool_type_arg = "process" if pool_type == "local" else "docker"
    subprocess.run(
        ["prefect", "work-pool", "create", pool_name, "--type", pool_type_arg],
        check=True,
        capture_output=True,
    )


def _create_deployments(pool_type: str, config_path: Optional[Path]):
    """Create Prefect deployments using Python API."""

    pool_name = f"{pool_type}-pool"

    # Default config path
    if config_path is None:
        config_path = Path("configs/standard.toml")

    default_config_path = str(config_path.absolute())

    console.print(f"[dim]  Using config: {default_config_path}[/dim]")

    # Get package root directory (where flows are located)
    # This ensures deployments work regardless of current working directory
    package_root = Path(__file__).parent.parent.parent.parent.absolute()
    original_cwd = Path.cwd()

    try:
        # Change to package root for deployment creation
        os.chdir(package_root)

        # Deploy session flow
        session_config = SessionFlowConfig(
            config_path=default_config_path,
            subject_id="subject-001",  # Example placeholder
            session_id="session-001",  # Example placeholder
        )

        if pool_type == "docker":
            # Docker work pool requires an image
            console.print("[dim]  Using Docker image: ghcr.io/borjaest/w2t-bkin:latest[/dim]")
            process_session_flow.deploy(
                name="process-session",
                work_pool_name=pool_name,
                parameters={"config": session_config.model_dump()},
                tags=["w2t-bkin", "session"],
                description="Process a single experimental session through the w2t-bkin pipeline.",
                version="1.0.0",
                image="ghcr.io/borjaest/w2t-bkin:latest",
            )
        else:
            # Process work pool - use cwd as storage (assumes code is available locally)
            console.print(f"[dim]  Using local code from: {package_root}[/dim]")
            process_session_flow.from_source(
                source=str(package_root),
                entrypoint="src/w2t_bkin/flows/session.py:process_session_flow",
            ).deploy(
                name="process-session",
                work_pool_name=pool_name,
                parameters={"config": session_config.model_dump()},
                tags=["w2t-bkin", "session"],
                description="Process a single experimental session through the w2t-bkin pipeline.",
                version="1.0.0",
                ignore_warnings=True,
            )
        console.print("[dim]  ✓ process-session deployment created[/dim]")

        # Deploy batch flow
        batch_config = BatchFlowConfig(
            config_path=default_config_path,
            max_parallel=4,
        )

        if pool_type == "docker":
            batch_process_flow.deploy(
                name="batch-process",
                work_pool_name=pool_name,
                parameters={"config": batch_config.model_dump()},
                tags=["w2t-bkin", "batch"],
                description="Process multiple experimental sessions in parallel.",
                version="1.0.0",
                image="ghcr.io/borjaest/w2t-bkin:latest",
            )
        else:
            batch_process_flow.from_source(
                source=str(package_root),
                entrypoint="src/w2t_bkin/flows/batch.py:batch_process_flow",
            ).deploy(
                name="batch-process",
                work_pool_name=pool_name,
                parameters={"config": batch_config.model_dump()},
                tags=["w2t-bkin", "batch"],
                description="Process multiple experimental sessions in parallel.",
                version="1.0.0",
                ignore_warnings=True,
            )
        console.print("[dim]  ✓ batch-process deployment created[/dim]")
    finally:
        # Restore original working directory
        os.chdir(original_cwd)
