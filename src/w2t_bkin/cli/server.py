"""Server management commands for Prefect."""

import json
import logging
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple
import urllib.request
import webbrowser

import typer

from w2t_bkin.api import BatchFlowConfig, SessionFlowConfig
from w2t_bkin.cli.utils import console, setup_logging
from w2t_bkin.flows import batch_process_flow, process_session_flow
from w2t_bkin.utils import read_toml, recursive_dict_update

server_app = typer.Typer(name="server", help="Prefect server management")


# ============================================================================
# Commands
# ============================================================================


@server_app.command(name="start")
def start(
    config_path: Path = typer.Option(Path("configuration.toml"), "--config", "-c", help="Default config file for deployments"),
    dev: bool = typer.Option(False, "--dev", help="Development mode: serve flows with local code changes"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    open_browser: bool = typer.Option(True, "--browser/--no-browser", help="Open browser automatically"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Number of workers to start (0 to disable auto-start, default: 1 for prod, 0 for dev)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging and show server output"),
):
    """Start Prefect server and deploy/serve flows.

    Production Mode (default):
    - Starts Prefect server
    - Creates docker-pool work pool
    - Deploys flows with Docker image reference
    - Optionally auto-starts Docker workers (use --workers N)
    - Recommended for reliable, isolated execution

    Development Mode (--dev):
    - Starts Prefect server
    - Serves flows from local installation using Runner
    - No workers needed (flows run in server process)
    - Requires worker extras: pip install -e .[worker]
    - Fast iteration with live code changes

    Example:
        $ w2t-bkin server start                # Production mode (no workers)
        $ w2t-bkin server start --workers 2    # Production with 2 Docker workers
        $ w2t-bkin server start --dev          # Development mode (serve flows)
        $ w2t-bkin server start --debug        # Show server logs
    """
    setup_logging("DEBUG" if debug else log_level)

    # Set worker defaults based on mode
    if workers is None:
        workers = 0 if dev else 1

    # Validate mode and print banner
    _validate_and_print_mode(dev, port)

    # Setup Prefect environment
    _setup_prefect_env(port)
    _ensure_prefect_api_config(port)

    # Check port availability
    if _is_port_in_use(port):
        console.print(f"[red]✗ Port {port} is already in use[/red]")
        console.print("[yellow]Tip: Stop the existing server with 'w2t-bkin server stop' or use a different port[/yellow]")
        raise typer.Exit(1)

    # Start server and flows
    try:
        server_process = _start_prefect_server(port, debug)

        # Deploy or serve flows based on mode
        if dev:
            _handle_dev_mode(config_path)
        else:
            _handle_prod_mode(config_path, workers, port)

        # Open UI and print summary
        ui_url = _open_ui(port, open_browser)
        _print_ready_summary(ui_url, dev, workers)

        # Keep server running
        _run_server_until_interrupted(server_process)

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
        stop()
        time.sleep(1)

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
    dev: bool = typer.Option(False, "--dev", help="Development mode"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
):
    """Restart Prefect server.

    Example:
        $ w2t-bkin server restart
        $ w2t-bkin server restart --dev
    """
    console.print("[cyan]Restarting Prefect server...[/cyan]\n")

    stop()
    time.sleep(2)

    start(config_path=config_path, dev=dev, port=port, open_browser=False, log_level=log_level)


# ============================================================================
# Configuration Loading
# ============================================================================


def _load_and_normalize_config(config_path: Optional[Path]) -> Tuple[dict, str]:
    """Load and merge base + project config, normalize paths to absolute.

    Args:
        config_path: Optional project config path (merged on top of base)

    Returns:
        Tuple of (merged_config_dict, config_json_string)
    """
    package_root = Path(__file__).parent.parent.parent.parent.absolute()
    base_config_path = package_root / "configs" / "standard.toml"
    project_config_path = config_path.resolve() if config_path else None

    console.print(f"[dim]  Base config: {base_config_path}[/dim]")
    if project_config_path:
        console.print(f"[dim]  Project config: {project_config_path}[/dim]")

    merged_config = {}
    original_cwd = Path.cwd()

    # Merge base config
    if base_config_path.exists():
        base_dict = read_toml(base_config_path)
        recursive_dict_update(merged_config, base_dict)

    # Merge project config
    if project_config_path and project_config_path.exists():
        project_dict = read_toml(project_config_path)
        recursive_dict_update(merged_config, project_dict)

    # Resolve paths to absolute paths
    if "paths" in merged_config:
        paths = merged_config["paths"]
        for key in ["raw_root", "intermediate_root", "output_root", "models_root", "root_metadata"]:
            if key in paths and paths[key]:
                resolved = (original_cwd / paths[key]).resolve()
                paths[key] = str(resolved)

    config_json = json.dumps(merged_config)
    return merged_config, config_json


# ============================================================================
# Prefect Environment Setup
# ============================================================================


def _setup_prefect_env(port: int) -> None:
    """Configure Prefect environment for project isolation.

    Args:
        port: Prefect UI port for API URL
    """
    # Project isolation: Use local .prefect directory
    prefect_home = Path.cwd() / ".prefect"
    prefect_home.mkdir(exist_ok=True)
    os.environ["PREFECT_HOME"] = str(prefect_home)
    os.environ["PREFECT_PROFILES_PATH"] = str(prefect_home / "profiles.toml")
    console.print(f"[dim]  Project isolation: Using {prefect_home}[/dim]")

    # Set API URL for local connections
    api_url = f"http://127.0.0.1:{port}/api"
    os.environ["PREFECT_API_URL"] = api_url


def _ensure_prefect_api_config(port: int) -> None:
    """Persist PREFECT_API_URL to profile non-interactively.

    Args:
        port: Prefect UI port
    """
    api_url = f"http://127.0.0.1:{port}/api"
    try:
        subprocess.run(
            _get_prefect_cmd() + ["config", "set", f"PREFECT_API_URL={api_url}"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
    except Exception:
        # Best-effort; env var is still set for this process
        pass


# ============================================================================
# Server Lifecycle
# ============================================================================


def _start_prefect_server(port: int, debug: bool) -> subprocess.Popen:
    """Start Prefect server subprocess.

    Args:
        port: Port for Prefect UI
        debug: Whether to show server output

    Returns:
        Server subprocess

    Raises:
        typer.Exit: If server fails to start or become ready
    """
    console.print("[cyan]Starting Prefect server...[/cyan]")

    server_cmd = _get_prefect_cmd() + ["server", "start", "--host", "0.0.0.0", "--port", str(port)]

    if debug:
        server_cmd.extend(["--log-level", "DEBUG"])
        stdout_dest = None
        stderr_dest = None
    else:
        stdout_dest = subprocess.DEVNULL
        stderr_dest = subprocess.DEVNULL

    # Set SQLite timeout to avoid "database is locked" errors
    server_env = os.environ.copy()
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
    time.sleep(2)
    return server_process


def _open_ui(port: int, open_browser: bool) -> str:
    """Open browser to Prefect UI if requested.

    Args:
        port: Prefect UI port
        open_browser: Whether to open browser

    Returns:
        UI URL
    """
    ui_url = f"http://localhost:{port}"
    if open_browser:
        console.print(f"[cyan]Opening browser to {ui_url}...[/cyan]")
        webbrowser.open(ui_url)
    return ui_url


# ============================================================================
# Flow Deployment (Production)
# ============================================================================


def _handle_prod_mode(config_path: Optional[Path], workers: int, port: int) -> None:
    """Handle production mode: create work pool, deploy flows, start workers.

    Args:
        config_path: Config file path
        workers: Number of workers to auto-start (0 = manual)
        port: Prefect server port
    """
    console.print("[cyan]Creating work pool 'docker-pool'...[/cyan]")
    _create_work_pool()
    console.print("[green]✓[/green] Work pool created\n")

    console.print("[cyan]Deploying flows with Docker image...[/cyan]")
    _deploy_flows(config_path)
    console.print("[green]✓[/green] Flows deployed\n")

    # Worker auto-start
    if workers > 0:
        _auto_start_workers(workers, port)
    else:
        _print_manual_worker_instructions()


def _create_work_pool() -> None:
    """Create Prefect Docker work pool idempotently."""
    pool_name = "docker-pool"

    # Check if pool already exists
    result = subprocess.run(
        _get_prefect_cmd() + ["work-pool", "inspect", pool_name],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print(f"[dim]  Work pool '{pool_name}' already exists[/dim]")
        return

    # Create docker-type work pool
    subprocess.run(
        _get_prefect_cmd() + ["work-pool", "create", pool_name, "--type", "docker"],
        check=True,
        capture_output=True,
    )


def _deploy_flows(config_path: Optional[Path]) -> None:
    """Deploy flows for production using Docker image.

    Args:
        config_path: Config file path
    """
    package_root = Path(__file__).parent.parent.parent.parent.absolute()
    _, config_json = _load_and_normalize_config(config_path)

    # Get Docker image
    docker_image = _get_docker_image()
    console.print(f"[dim]  Docker image: {docker_image}[/dim]")

    original_cwd = Path.cwd()
    try:
        os.chdir(package_root)

        # Common deployment parameters
        common_params = {
            "work_pool_name": "docker-pool",
            "image": docker_image,
            "build": False,
            "push": False,
            "job_variables": {
                "env": {
                    "W2T_RUNTIME_CONFIG_JSON": config_json,
                }
            },
            "tags": ["w2t-bkin", "production"],
            "version": "1.0.0",
        }

        # Deploy session flow
        session_config = SessionFlowConfig(
            subject_id="subject-001",
            session_id="session-001",
        )
        process_session_flow.deploy(
            name="process-session",
            parameters={"config": session_config.model_dump()},
            description="Process a single experimental session through the w2t-bkin pipeline.",
            **common_params,
        )
        console.print("[dim]  ✓ process-session deployed[/dim]")

        # Deploy batch flow
        batch_config = BatchFlowConfig(max_parallel=4)
        batch_process_flow.deploy(
            name="batch-process",
            parameters={"config": batch_config.model_dump()},
            description="Process multiple experimental sessions in parallel.",
            **common_params,
        )
        console.print("[dim]  ✓ batch-process deployed[/dim]")

    finally:
        os.chdir(original_cwd)


# ============================================================================
# Flow Serving (Development)
# ============================================================================


def _handle_dev_mode(config_path: Optional[Path]) -> None:
    """Handle development mode: serve flows from local code.

    Args:
        config_path: Config file path
    """
    console.print("[cyan]Serving flows from local code...[/cyan]")
    _serve_flows(config_path)
    console.print("[green]✓[/green] Flows served\n")


def _serve_flows(config_path: Optional[Path]) -> None:
    """Serve flows for development using local code.

    Args:
        config_path: Config file path
    """
    from prefect.runner import Runner

    package_root = Path(__file__).parent.parent.parent.parent.absolute()
    _, config_json = _load_and_normalize_config(config_path)

    # Inject runtime config into environment for dev mode
    os.environ["W2T_RUNTIME_CONFIG_JSON"] = config_json

    original_cwd = Path.cwd()
    try:
        os.chdir(package_root)

        # Use Runner to serve multiple flows
        runner = Runner(name="w2t-dev-runner")

        # Add session flow
        session_config = SessionFlowConfig(
            subject_id="subject-001",
            session_id="session-001",
        )
        runner.add_flow(
            process_session_flow,
            name="process-session",
            parameters={"config": session_config.model_dump()},
            tags=["w2t-bkin", "development"],
        )
        console.print("[dim]  ✓ process-session added to runner[/dim]")

        # Add batch flow
        batch_config = BatchFlowConfig(max_parallel=4)
        runner.add_flow(
            batch_process_flow,
            name="batch-process",
            parameters={"config": batch_config.model_dump()},
            tags=["w2t-bkin", "development"],
        )
        console.print("[dim]  ✓ batch-process added to runner[/dim]")

        # Start runner (non-blocking)
        runner.start()
        console.print("[dim]  ✓ Runner started in background[/dim]")

    finally:
        os.chdir(original_cwd)


# ============================================================================
# Worker Management
# ============================================================================


def _auto_start_workers(count: int, port: int) -> None:
    """Auto-start Docker workers and verify pool readiness.

    Args:
        count: Number of workers to start
        port: Prefect server port
    """
    console.print(f"\n[cyan]Starting {count} worker(s) via w2t-bkin worker start...[/cyan]")

    api_url = f"http://127.0.0.1:{port}/api"
    worker_cmd = [
        sys.executable,
        "-m",
        "w2t_bkin.cli",
        "worker",
        "start",
        "--count",
        str(count),
        "--api-url",
        api_url,
    ]

    try:
        worker_result = subprocess.run(
            worker_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        console.print(worker_result.stdout)
        _verify_work_pool_readiness(api_url)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to start workers[/red]")
        if e.stdout:
            console.print(f"[dim]Output: {e.stdout}[/dim]")
        if e.stderr:
            console.print(f"[dim]Error: {e.stderr}[/dim]")
        console.print("[yellow]Continuing without workers...[/yellow]")


def _verify_work_pool_readiness(api_url: str) -> None:
    """Verify work pool status and show troubleshooting if needed.

    Args:
        api_url: Prefect API URL
    """
    console.print("\n[cyan]Verifying work pool readiness...[/cyan]")
    time.sleep(3)  # Give workers time to poll

    try:
        inspect_cmd = _get_prefect_cmd() + ["work-pool", "inspect", "docker-pool", "--output", "json"]
        inspect_result = subprocess.run(
            inspect_cmd,
            capture_output=True,
            text=True,
            env={**os.environ, "PREFECT_API_URL": api_url},
        )

        if inspect_result.returncode != 0:
            raise RuntimeError(inspect_result.stderr.strip() or "work-pool inspect failed")

        pool_info = json.loads(inspect_result.stdout)
        pool_status = str(pool_info.get("status", "")).upper()

        if pool_status == "READY":
            console.print("[green]✓ Work pool is READY[/green]")
        else:
            console.print(f"[yellow]⚠ Work pool status: {pool_status or 'UNKNOWN'}[/yellow]")
            last_polled = pool_info.get("last_polled")
            if last_polled:
                console.print(f"  last_polled: {last_polled}")
            _print_troubleshooting_tips(api_url)

    except Exception as e:
        console.print(f"[yellow]Could not verify pool status: {e}[/yellow]")


def _print_troubleshooting_tips(api_url: str) -> None:
    """Print worker troubleshooting guidance.

    Args:
        api_url: Prefect API URL
    """
    console.print("\n[yellow]Troubleshooting:[/yellow]")
    console.print("  • Check worker logs: docker logs docker-worker")
    console.print(f"  • Verify API URL: {api_url}")
    console.print("  • Run in foreground: w2t-bkin worker start --foreground")


def _print_manual_worker_instructions() -> None:
    """Print manual worker start instructions."""
    console.print("\n[bold cyan]📋 To start Docker workers:[/bold cyan]")
    console.print("[dim]  Run in a new terminal:[/dim]")
    console.print("[yellow]     w2t-bkin worker start[/yellow]")
    console.print("[dim]  Or with more workers:[/dim]")
    console.print("[yellow]     w2t-bkin worker start --count 4[/yellow]")


# ============================================================================
# Platform Utilities
# ============================================================================


def _get_docker_image() -> str:
    """Get Docker image for deployments.

    Checks environment variables and .workers/.env for image configuration.
    Falls back to latest tag if not specified.

    Returns:
        Docker image tag (e.g., "ghcr.io/borjaest/w2t-bkin:latest")
    """
    # Check environment variable first
    if image := os.getenv("W2T_DOCKER_IMAGE"):
        return image

    # Check .workers/.env file
    env_file = Path.cwd() / ".workers" / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("W2T_DOCKER_IMAGE="):
                        return line.split("=", 1)[1].strip("\"'")
        except Exception:
            pass  # Fall through to default

    # Default to latest tag (stable release)
    return "ghcr.io/borjaest/w2t-bkin:latest"


def _check_worker_extras() -> bool:
    """Check if worker extras are installed."""
    try:
        import deeplabcut

        return True
    except ImportError:
        return False


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use.

    Args:
        port: Port number to check

    Returns:
        True if port is in use, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


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
        if process.poll() is not None:
            console.print(f"[red]Server process exited with code {process.returncode}[/red]")
            return False

        try:
            urllib.request.urlopen(health_url, timeout=1)
            return True
        except Exception:
            time.sleep(1)

    return False


def _get_prefect_cmd() -> list[str]:
    """Get the prefect command using the current Python interpreter."""
    return [sys.executable, "-m", "prefect"]


def _is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def _is_wsl() -> bool:
    """Check if running under WSL.

    WSL reports platform.system() == 'Linux', but Docker containers started via
    Docker Desktop cannot reach services on WSL via --network host/127.0.0.1.
    """
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


def _get_docker_api_url(port: int) -> str:
    """Get the Prefect API URL for Docker workers based on platform.

    Args:
        port: Port number for the Prefect server

    Returns:
        Appropriate API URL for Docker workers
    """
    if _is_windows() or _is_wsl():
        return f"http://host.docker.internal:{port}/api"
    else:
        # Linux with --network host
        return f"http://127.0.0.1:{port}/api"


# ============================================================================
# Commands
# ============================================================================


def _validate_and_print_mode(dev: bool, port: int) -> None:
    """Validate mode requirements and print mode banner.

    Args:
        dev: Development mode flag
        port: Server port

    Raises:
        typer.Exit: If dev mode requirements not met
    """
    if dev:
        if not _check_worker_extras():
            console.print("[red]✗ Development mode requires worker extras[/red]")
            console.print("[yellow]Install with: pip install -e .[worker] (~630 MB with ML dependencies)[/yellow]")
            raise typer.Exit(1)
        console.print("[yellow]⚡ Development Mode[/yellow]")
        console.print("[dim]  Using local code with live updates[/dim]")
        console.print("[dim]  Flows run in server process (no workers needed)[/dim]")
    else:
        console.print("[green]🚀 Production Mode[/green]")
        console.print("[dim]  Using Docker workers for reliable execution[/dim]")

    console.print(f"[dim]  Port: {port}[/dim]\n")


def _print_ready_summary(ui_url: str, dev: bool, workers: int) -> None:
    """Print server ready summary.

    Args:
        ui_url: Prefect UI URL
        dev: Development mode flag
        workers: Number of workers (for dev mode warning)
    """
    console.print(f"\n[green]✅ W2T-BKIN Server Ready![/green]")
    console.print(f"\n[bold]Prefect UI:[/bold] {ui_url}")

    if not dev:
        console.print("[bold]Work Pool:[/bold] docker-pool")
    elif workers > 0:
        console.print("\n[yellow]⚠ Workers ignored in dev mode (flows run in server process)[/yellow]")


def _run_server_until_interrupted(server_process: subprocess.Popen) -> None:
    """Keep server running until user interrupts.

    Args:
        server_process: Server subprocess
    """
    console.print("\n[dim]Press Ctrl+C to stop the server[/dim]\n")

    try:
        server_process.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)
        console.print("[green]✓[/green] Server stopped")
