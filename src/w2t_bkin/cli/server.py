"""Server management commands for Prefect."""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
from typing import List, Optional, Tuple
import urllib.request
import webbrowser

import typer

from w2t_bkin.api import BatchFlowConfig, SessionFlowConfig
from w2t_bkin.cli.utils import console, setup_logging
from w2t_bkin.flows import batch_process_flow, process_session_flow
from w2t_bkin.utils import read_toml, recursive_dict_update

server_app = typer.Typer(name="server", help="Prefect server management")


@dataclass
class WorkerInfo:
    """Information about a started worker."""

    worker_type: str  # "process" or "docker"
    name: str
    reference: any  # subprocess.Popen for process, container_id for docker


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use.

    Args:
        port: Port number to check

    Returns:
        True if port is in use, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _get_prefect_cmd() -> List[str]:
    """Get the prefect command using the current Python interpreter."""
    return [sys.executable, "-m", "prefect"]


def _is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def _get_api_url(port: int) -> str:
    """Get the Prefect API URL for the given platform.

    Args:
        port: Port number for the Prefect server

    Returns:
        Appropriate API URL based on platform and context
    """
    # For local workers, always use localhost/127.0.0.1
    # For Docker workers on Linux with --network host, use 127.0.0.1
    # For Docker workers on Windows/Mac, use host.docker.internal
    return f"http://127.0.0.1:{port}/api"


def _get_docker_api_url(port: int) -> str:
    """Get the Prefect API URL for Docker workers based on platform.

    Args:
        port: Port number for the Prefect server

    Returns:
        Appropriate API URL for Docker workers
    """
    if _is_windows():
        # Windows: Use host.docker.internal
        return f"http://host.docker.internal:{port}/api"
    else:
        # Linux with --network host: Use 127.0.0.1
        return f"http://127.0.0.1:{port}/api"


@server_app.command(name="start")
def start(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Default config file for deployments"),
    work_pool: Optional[str] = typer.Option(None, "--work-pool", "-w", help="Work pool type (docker or local)"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    open_browser: bool = typer.Option(True, "--browser/--no-browser", help="Open browser automatically"),
    workers: int = typer.Option(1, "--workers", help="Number of workers to start (0 to disable auto-start)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging and show server output"),
):
    """Start Prefect server, create deployments, and auto-start workers.

    This command:
    1. Starts the Prefect server
    2. Creates flow deployments automatically
    3. Auto-starts workers (Docker or local based on work pool type)
    4. Opens the Prefect UI in your browser

    Workers are automatically started by default (--workers 1). For Docker pools,
    workers run in containers. For local pools, workers run as subprocesses.

    Example:
        $ w2t-bkin server start                    # Auto-starts 1 worker
        $ w2t-bkin server start --workers 4        # Start with 4 workers
        $ w2t-bkin server start --workers 0        # No auto-start, manual setup
        $ w2t-bkin server start --work-pool local  # Use local workers
        $ w2t-bkin server start --debug            # Show server logs
    """
    setup_logging("DEBUG" if debug else log_level)

    console.print("[cyan]🚀 Starting W2T-BKIN Prefect Server...[/cyan]\n")

    # Project isolation: Use local .prefect directory
    prefect_home = Path.cwd() / ".prefect"
    prefect_home.mkdir(exist_ok=True)
    os.environ["PREFECT_HOME"] = str(prefect_home)
    console.print(f"[dim]  Project isolation: Using {prefect_home}[/dim]")

    # Ensure API URL is set to localhost for local connections
    # This fixes issues where it might default to 0.0.0.0 or other unreachable addresses
    api_url = f"http://127.0.0.1:{port}/api"
    os.environ["PREFECT_API_URL"] = api_url

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

    # Check if port is already in use
    if _is_port_in_use(port):
        console.print(f"[red]✗ Port {port} is already in use[/red]")
        console.print(f"[yellow]Tip: Stop the existing server with 'w2t-bkin server stop' or use a different port[/yellow]")
        raise typer.Exit(1)

    # Start Prefect server in background
    console.print("[cyan]Starting Prefect server...[/cyan]")

    try:
        # Start server process
        server_cmd = _get_prefect_cmd() + ["server", "start", "--host", "0.0.0.0", "--port", str(port)]

        if debug:
            server_cmd.extend(["--log-level", "DEBUG"])
            stdout_dest = None
            stderr_dest = None
        else:
            # Redirect to DEVNULL to avoid hanging due to full pipe buffers
            # We don't use PIPE because we aren't reading from it continuously
            stdout_dest = subprocess.DEVNULL
            stderr_dest = subprocess.DEVNULL

        # Set SQLite timeout to avoid "database is locked" errors
        server_env = os.environ.copy()
        # Increase timeout for SQLite (default is often too low for concurrent ops)
        server_env.setdefault("PREFECT_API_DATABASE_CONNECTION_TIMEOUT", "60.0")
        server_env.setdefault("PREFECT_API_DATABASE_TIMEOUT", "60.0")

        server_process = subprocess.Popen(
            server_cmd,
            stdout=stdout_dest,
            stderr=stderr_dest,
            text=True,
            env=server_env,
        )

        # Wait for server to be ready
        console.print("[dim]Waiting for server to be ready...[/dim]")
        if not _wait_for_server(server_process, port):
            console.print("[red]✗ Server failed to start[/red]")
            server_process.terminate()
            if not debug:
                console.print("[yellow]Tip: Run with --debug to see server logs[/yellow]")
            raise typer.Exit(1)

        console.print("[green]✓[/green] Prefect server started\n")

        # Give the server a moment to settle
        time.sleep(2)

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

        # Start workers if requested
        worker_processes: List[WorkerInfo] = []
        if workers > 0:
            console.print(f"\n[cyan]Starting {workers} worker(s)...[/cyan]")

            for i in range(workers):
                worker_name = f"{work_pool}-worker-{i+1}"

                if work_pool == "docker":
                    worker_info = _start_docker_worker(worker_name, work_pool, port)
                    if worker_info:
                        worker_processes.append(worker_info)
                else:  # local
                    worker_info = _start_local_worker(worker_name, work_pool, port)
                    if worker_info:
                        worker_processes.append(worker_info)

            # Wait for workers to connect
            _verify_workers(worker_processes, workers, work_pool)

        else:
            # No auto-start - show manual instructions
            if work_pool == "docker":
                console.print("\n[bold cyan]📋 To start Docker workers:[/bold cyan]")
                console.print("[dim]  Run in a new terminal:[/dim]")
                console.print(f"[yellow]     prefect worker start --pool docker-pool[/yellow]")
                console.print("\n[dim]  Or use Docker container:[/dim]")
                console.print(f"[yellow]     docker run -d --name w2t-worker \\[/yellow]")
                console.print(f"[yellow]       -e PREFECT_API_URL=http://host.docker.internal:{port}/api \\[/yellow]")
                console.print(f"[yellow]       -v /var/run/docker.sock:/var/run/docker.sock \\[/yellow]")
                console.print(f"[yellow]       --network host \\[/yellow]")
                console.print(f"[yellow]       ghcr.io/borjaest/w2t-bkin:latest \\[/yellow]")
                console.print(f"[yellow]       prefect worker start --pool docker-pool[/yellow]")
            else:
                console.print("\n[bold cyan]📋 To start local workers:[/bold cyan]")
                console.print("[dim]  Run in a new terminal:[/dim]")
                console.print(f"[yellow]     prefect worker start --pool local-pool[/yellow]")
                console.print("\n[dim]  Or restart with --workers flag:[/dim]")
                console.print(f"[yellow]     w2t-bkin server start --workers 1[/yellow]")

        console.print("\n[dim]Press Ctrl+C to stop the server[/dim]\n")

        # Keep server running
        try:
            server_process.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping server...[/yellow]")
            server_process.terminate()
            server_process.wait(timeout=5)

            # Stop workers
            if worker_processes:
                console.print("[yellow]Stopping workers...[/yellow]")
                for worker_info in worker_processes:
                    _stop_worker(worker_info)

            console.print("[green]✓[/green] Server stopped")

    except typer.Exit:
        raise
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


@server_app.command(name="reset")
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm reset without prompt"),
):
    """Reset the Prefect database.

    WARNING: This will delete all flow run history and deployments.
    Use this if the database is locked or corrupted.

    Example:
        $ w2t-bkin server reset
    """
    if not yes:
        confirm = typer.confirm("Are you sure you want to reset the Prefect database? This will delete all history.")
        if not confirm:
            raise typer.Abort()

    console.print("[cyan]Resetting Prefect database...[/cyan]")

    try:
        # Stop server first
        stop()
        time.sleep(1)

        # Run prefect server database reset
        subprocess.run(
            _get_prefect_cmd() + ["server", "database", "reset", "-y"],
            check=True,
            capture_output=True,
        )
        console.print("[green]✓[/green] Database reset successfully")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to reset database[/red]")
        console.print(f"[dim]  Error: {e.stderr}[/dim]")
        raise typer.Exit(1)
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


def _wait_for_server(process: subprocess.Popen, port: int, max_retries: int = 30) -> bool:
    """Wait for Prefect server to be ready.

    Args:
        process: The server subprocess to monitor
        port: Port number for the Prefect server
        max_retries: Maximum number of retries (seconds)

    Returns:
        True if server is ready, False if it failed or timed out
    """
    health_url = f"http://localhost:{port}/api/health"

    for i in range(max_retries):
        # Check if process crashed
        if process.poll() is not None:
            console.print(f"[red]Server process exited with code {process.returncode}[/red]")
            return False

        try:
            urllib.request.urlopen(health_url, timeout=1)
            return True
        except Exception:
            time.sleep(1)

    return False


def _create_work_pool(pool_type: str):
    """Create Prefect work pool.

    Note: Both local and docker pools use 'process' type.
    Docker workers run process-type workers inside containers.
    """
    pool_name = f"{pool_type}-pool"

    # Check if pool already exists
    result = subprocess.run(_get_prefect_cmd() + ["work-pool", "inspect", pool_name], capture_output=True, text=True)

    if result.returncode == 0:
        console.print(f"[dim]  Work pool '{pool_name}' already exists[/dim]")
        return

    # Create pool - both local and docker use process type
    # Docker workers run process workers inside containers (not nested Docker)
    subprocess.run(
        _get_prefect_cmd() + ["work-pool", "create", pool_name, "--type", "process"],
        check=True,
        capture_output=True,
    )


def _create_deployments(pool_type: str, config_path: Optional[Path]):
    """Create Prefect deployments using Python API."""

    pool_name = f"{pool_type}-pool"

    # Get package root directory (where flows are located)
    # This ensures deployments work regardless of current working directory
    package_root = Path(__file__).parent.parent.parent.parent.absolute()

    # Base config always comes from package root
    base_config_path = package_root / "configs" / "standard.toml"

    # Project config from user (optional)
    project_config_path = config_path.resolve() if config_path else None

    console.print(f"[dim]  Base config: {base_config_path}[/dim]")
    if project_config_path:
        console.print(f"[dim]  Project config: {project_config_path}[/dim]")

    # Load and merge configuration to bake into deployment
    merged_config = {}

    # Store original CWD for path resolution
    original_cwd = Path.cwd()

    # 1. Base config
    if base_config_path.exists():
        base_dict = read_toml(base_config_path)
        recursive_dict_update(merged_config, base_dict)

    # 2. Project config (has priority - resolve relative paths from project directory)
    if project_config_path and project_config_path.exists():
        project_dict = read_toml(project_config_path)
        recursive_dict_update(merged_config, project_dict)

    # 3. Resolve all paths to absolute paths NOW (at deployment time)
    #    This ensures paths are resolved relative to the CWD where server was started
    #    For Docker deployments, these absolute paths will be ignored and container
    #    paths from container.toml will be used instead
    if "paths" in merged_config:
        paths = merged_config["paths"]
        for key in ["raw_root", "intermediate_root", "output_root", "models_root", "root_metadata"]:
            if key in paths and paths[key]:
                # Resolve relative to original CWD (where user started server)
                resolved = (original_cwd / paths[key]).resolve()
                paths[key] = str(resolved)  # Convert to string for JSON serialization

    # Serialize to JSON string for env var
    config_json = json.dumps(merged_config)

    try:
        # Change to package root for deployment creation
        os.chdir(package_root)

        # Deploy session flow
        session_config = SessionFlowConfig(
            subject_id="subject-001",  # Example placeholder
            session_id="session-001",  # Example placeholder
        )

        # Deploy session flow
        # Use from_source pointing to local package root
        # Docker workers will have this code mounted at /app
        console.print(f"[dim]  Using code from: {package_root}[/dim]")

        process_session_flow.from_source(
            source=str(package_root),
            entrypoint="src/w2t_bkin/flows/session.py:process_session_flow",
        ).deploy(
            name="process-session",
            work_pool_name=pool_name,
            parameters={"config": session_config.model_dump()},
            job_variables={
                "env": {
                    "W2T_RUNTIME_CONFIG_JSON": config_json,
                }
            },
            tags=["w2t-bkin", "session", pool_type],
            description="Process a single experimental session through the w2t-bkin pipeline.",
            version="1.0.0",
            ignore_warnings=True,
        )
        console.print("[dim]  ✓ process-session deployment created[/dim]")

        # Deploy batch flow
        batch_config = BatchFlowConfig(
            max_parallel=4,
        )

        # Deploy batch flow
        batch_process_flow.from_source(
            source=str(package_root),
            entrypoint="src/w2t_bkin/flows/batch.py:batch_process_flow",
        ).deploy(
            name="batch-process",
            work_pool_name=pool_name,
            parameters={"config": batch_config.model_dump()},
            job_variables={
                "env": {
                    "W2T_RUNTIME_CONFIG_JSON": config_json,
                }
            },
            tags=["w2t-bkin", "batch", pool_type],
            description="Process multiple experimental sessions in parallel.",
            version="1.0.0",
            ignore_warnings=True,
        )
        console.print("[dim]  ✓ batch-process deployment created[/dim]")
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def _start_docker_worker(worker_name: str, work_pool: str, port: int) -> Optional[WorkerInfo]:
    """Start a Docker worker container.

    Args:
        worker_name: Name for the worker container
        work_pool: Work pool type (should be "docker")
        port: Prefect server port

    Returns:
        WorkerInfo if successful, None if failed
    """
    # Clean up any existing container with the same name
    try:
        subprocess.run(
            ["docker", "rm", "-f", worker_name],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass  # Container might not exist

    api_url = _get_docker_api_url(port)

    # Get package root to mount code into container
    package_root = Path(__file__).parent.parent.parent.parent.absolute()

    # Build Docker command based on platform
    docker_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        worker_name,
        "-e",
        f"PREFECT_API_URL={api_url}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
    ]

    # Mount code based on platform
    if _is_windows():
        # Windows: Mount to /workspace (absolute paths won't work cross-platform anyway)
        docker_cmd.extend(["-v", f"{package_root}:/workspace:ro"])
    else:
        # Linux: Mount to same path as host to support absolute paths
        docker_cmd.extend(["-v", f"{package_root}:{package_root}:ro"])

    if not _is_windows():
        # Linux: Use host network mode for simplicity
        docker_cmd.extend(["--network", "host"])
    else:
        # Windows: Publish port (host network mode not supported)
        docker_cmd.extend(["-p", f"{port}:{port}"])

    # Add image and worker command
    # Override entrypoint to run prefect worker directly with bash
    docker_cmd.extend(
        [
            "ghcr.io/borjaest/w2t-bkin:latest",
            "/bin/bash",
            "-c",
            f"prefect worker start --pool {work_pool}-pool --name {worker_name}",
        ]
    )

    try:
        result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()
        console.print(f"[green]✓[/green] Started Docker worker: {worker_name}")
        return WorkerInfo("docker", worker_name, container_id)
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]![/yellow] Failed to start Docker worker {worker_name}")
        console.print(f"[dim]  Error: {e.stderr.strip()[:200]}[/dim]")
        console.print(f"[dim]  Make sure Docker is running and the image is available[/dim]")
        return None


def _start_local_worker(worker_name: str, work_pool: str, port: int) -> Optional[WorkerInfo]:
    """Start a local worker subprocess.

    Args:
        worker_name: Name for the worker process
        work_pool: Work pool type (should be "local")
        port: Prefect server port

    Returns:
        WorkerInfo if successful, None if failed
    """
    # Workers need PREFECT_API_URL to connect to the server
    worker_env = os.environ.copy()
    worker_env["PREFECT_API_URL"] = _get_api_url(port)

    try:
        worker_proc = subprocess.Popen(
            _get_prefect_cmd() + ["worker", "start", "--pool", f"{work_pool}-pool", "--name", worker_name],
            env=worker_env,
            # Don't capture stdout/stderr - let worker print its logs
        )
        console.print(f"[green]✓[/green] Started local worker: {worker_name} (PID: {worker_proc.pid})")
        return WorkerInfo("process", worker_name, worker_proc)
    except Exception as e:
        console.print(f"[yellow]![/yellow] Failed to start local worker {worker_name}")
        console.print(f"[dim]  Error: {str(e)[:200]}[/dim]")
        return None


def _is_worker_running(worker_info: WorkerInfo) -> bool:
    """Check if a worker is still running.

    Args:
        worker_info: Worker information

    Returns:
        True if worker is running, False otherwise
    """
    if worker_info.worker_type == "process":
        # Check if process is still alive
        return worker_info.reference.poll() is None
    else:  # docker
        # Check if Docker container is running
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", worker_info.name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "true" in result.stdout


def _verify_workers(worker_processes: List[WorkerInfo], expected_count: int, work_pool: str) -> None:
    """Verify that workers are running and connected.

    Args:
        worker_processes: List of started workers
        expected_count: Expected number of workers
        work_pool: Work pool type
    """
    console.print(f"\\n[cyan]Waiting for {expected_count} worker(s) to connect...[/cyan]")
    time.sleep(5)  # Give workers time to connect

    # Verify workers are still running
    active_workers = 0
    for worker_info in worker_processes:
        if _is_worker_running(worker_info):
            active_workers += 1
        else:
            console.print(f"[yellow]![/yellow] Worker {worker_info.name} exited unexpectedly")

    if active_workers >= expected_count:
        console.print(f"[green]✓[/green] {active_workers} worker(s) running and connected")
    else:
        console.print(f"[yellow]![/yellow] Only {active_workers}/{expected_count} workers are running")
        console.print(f"[dim]  Check worker status with: {sys.executable} -m prefect work-pool inspect {work_pool}-pool[/dim]")
        if work_pool == "docker":
            console.print(f"[dim]  View worker logs with: docker logs {work_pool}-worker-1[/dim]")


def _stop_worker(worker_info: WorkerInfo) -> None:
    """Stop a worker process or container.

    Args:
        worker_info: Worker information
    """
    try:
        if worker_info.worker_type == "process":
            worker_info.reference.terminate()
            worker_info.reference.wait(timeout=5)
        else:  # docker
            subprocess.run(
                ["docker", "stop", worker_info.name],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["docker", "rm", worker_info.name],
                capture_output=True,
            )
    except Exception:
        pass  # Best effort cleanup
