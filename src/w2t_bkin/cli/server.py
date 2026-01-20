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

from w2t_bkin.cli.utils import console, setup_logging
from w2t_bkin.utils import read_toml, recursive_dict_update

server_app = typer.Typer(name="server", help="Prefect server management")


# ============================================================================
# Public CLI Commands
# ============================================================================


@server_app.command(name="start")
def start(
    config_path: Path = typer.Option(Path("configuration.toml"), "--config", "-c", help="Default config file for deployments"),
    dev: bool = typer.Option(False, "--dev", help="Development mode: serve flows with local code changes"),
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    open_browser: bool = typer.Option(True, "--browser/--no-browser", help="Open browser automatically"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging and show server output"),
    env_file: Optional[Path] = typer.Option(None, "--env-file", help="Environment file to load (default: .workers/.env)"),
):
    """Start Prefect server and deploy/serve flows.

    Production Mode (default):
    - Starts Prefect server
    - Creates docker-pool work pool
    - Deploys flows with Docker image reference
    - Start workers separately: w2t-bkin worker start
    - Recommended for reliable, isolated execution

    Development Mode (--dev):
    - Starts Prefect server
    - Serves flows from local installation using Runner
    - No workers needed (flows run in server process)
    - Requires worker extras: pip install -e .[worker]
    - Fast iteration with live code changes

    Example:
        $ w2t-bkin server start                # Production mode
        $ w2t-bkin server start --dev          # Development mode (serve flows)
        $ w2t-bkin server start --debug        # Show server logs
    """
    setup_logging("DEBUG" if debug else log_level)

    # Project root is the current working directory.
    # This follows standard conventions (make, docker-compose, npm, etc.)
    # and matches the documented workflow: cd {experiment_root} && w2t-bkin server start
    project_root = Path.cwd()

    # Development mode: regenerate .env.dev with correct absolute paths
    if dev:
        from w2t_bkin.cli.utils import generate_env_dev_content

        env_dev_path = project_root / ".workers" / ".env.dev"
        env_dev_path.parent.mkdir(parents=True, exist_ok=True)
        env_dev_content = generate_env_dev_content(project_root)
        env_dev_path.write_text(env_dev_content)
        console.print(f"[dim]  Regenerated {env_dev_path.relative_to(project_root.parent)} with absolute paths[/dim]")

    # Load environment files (before any other env setup)
    from w2t_bkin.cli.env import load_project_env

    # In dev mode, load both .env and .env.dev (dev paths win)
    load_project_env(project_root, env_file)
    if dev:
        from w2t_bkin.cli.env import load_env_file

        env_dev_path = project_root / ".workers" / ".env.dev"
        load_env_file(env_dev_path, override=True, silent=False)

    # Validate mode and print banner
    _validate_and_print_mode(dev, port)

    # Setup Prefect environment
    _setup_prefect_env(port, project_root)
    _ensure_prefect_api_config(port)

    # Check port availability
    if _is_port_in_use(port):
        console.print(f"[red]✗ Port {port} is already in use[/red]")
        console.print("[yellow]Tip: Stop the existing server with 'w2t-bkin server stop' or use a different port[/yellow]")
        raise typer.Exit(1)

    # Start server and flows
    try:
        server_process = _start_prefect_server(port, debug)

        # Production: deploy and then just keep the server alive.
        # Development: open UI first, then block in a long-lived serve loop that
        # polls for runs and executes them locally.
        if not dev:
            _handle_prod_mode(config_path, project_root)

        ui_url = _open_ui(port, open_browser)
        _print_ready_summary(ui_url, dev)

        if dev:
            _handle_dev_mode(config_path)
        else:
            _run_server_until_interrupted(server_process)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logging.exception("Failed to start server")
        raise typer.Exit(1)
    finally:
        # Best-effort cleanup if dev serving exits or an exception occurs.
        try:
            if "server_process" in locals() and server_process.poll() is None:
                server_process.terminate()
                server_process.wait(timeout=5)
        except Exception:
            pass


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


# ============================================================================
# Start Workflow Helpers
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


def _print_manual_worker_instructions() -> None:
    """Print OS-specific instructions for manually starting workers."""
    console.print("\n[bold cyan]Start Workers (in a new terminal):[/bold cyan]")

    console.print("  [yellow]# Production - Docker workers (default)[/yellow]")
    console.print("  [dim]w2t-bkin worker start                    # 1 worker, concurrency limit 1[/dim]")
    console.print("  [dim]w2t-bkin worker start --limit 2          # 1 worker, concurrency limit 2[/dim]")

    console.print("\n  [yellow]# Multiple workers - run command multiple times[/yellow]")
    console.print("  [dim]w2t-bkin worker start --name worker-1    # Terminal 1[/dim]")
    console.print("  [dim]w2t-bkin worker start --name worker-2    # Terminal 2[/dim]")

    console.print("\n  [yellow]# Development - process workers (requires [worker] extras)[/yellow]")
    console.print("  [dim]w2t-bkin worker start --type process --limit 1[/dim]")


def _print_ready_summary(ui_url: str, dev: bool) -> None:
    """Print server ready summary.

    Args:
        ui_url: Prefect UI URL
        dev: Development mode flag
    """
    console.print(f"\n[green]✅ W2T-BKIN Server Ready![/green]")
    console.print(f"\n[bold]Prefect UI:[/bold] {ui_url}")

    if not dev:
        console.print("[bold]Work Pool:[/bold] docker-pool")


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


# ============================================================================
# Prefect Environment & Process Lifecycle
# ============================================================================


def _setup_prefect_env(port: int, project_root: Path) -> None:
    """Configure Prefect environment for project isolation.

    Args:
        port: Prefect UI port for API URL
        project_root: Experiment/project root directory (cwd when server starts)
    """
    # Project isolation: Use .prefect in the current working directory.
    # Each experiment initialized via `w2t-bkin data init` gets its own
    # isolated Prefect database, deployments, and run history.
    prefect_home = project_root / ".prefect"
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


def _get_prefect_cmd() -> list[str]:
    """Get the prefect command using the current Python interpreter."""
    return [sys.executable, "-m", "prefect"]


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


def _wait_for_server(process: subprocess.Popen, port: int, timeout: int = 45) -> bool:
    """Wait for Prefect server to be ready.

    Args:
        process: The server subprocess to monitor
        port: Port number for the Prefect server
        timeout: Maximum number of retries (seconds)

    Returns:
        True if server is ready, False if it failed or timed out
    """
    health_url = f"http://localhost:{port}/api/health"

    for i in range(timeout):
        if process.poll() is not None:
            console.print(f"[red]Server process exited with code {process.returncode}[/red]")
            return False

        try:
            urllib.request.urlopen(health_url, timeout=1)
            return True
        except Exception:
            time.sleep(1)

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
# Configuration Loading
# ============================================================================


def _load_and_normalize_config(config_path: Optional[Path], for_container: bool = False) -> Tuple[dict, str]:
    """Load and merge base + project config, normalize paths.

    Args:
        config_path: Optional project config path (merged on top of base)
        for_container: If True, use container-native paths (/data, /models, etc.)
                      instead of host absolute paths. Required for Docker deployments.

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

    # Resolve paths: container-native or host-absolute
    if "paths" in merged_config:
        paths = merged_config["paths"]

        if for_container:
            # Use container-native paths (Docker volumes will mount host paths here)
            # These are fixed paths inside the container that match volume mounts
            container_path_map = {
                "raw_root": "/data/raw",
                "intermediate_root": "/data/interim",
                "output_root": "/data/processed",
                "models_root": "/models",
            }
            for key, container_path in container_path_map.items():
                if key in paths:
                    paths[key] = container_path
            # root_metadata: only set if user explicitly provided it
            if "root_metadata" in paths and paths["root_metadata"]:
                # Assume it's under /configs if specified
                paths["root_metadata"] = "/configs/metadata.toml"
        else:
            # Resolve to host absolute paths (dev mode, local execution)
            for key in ["raw_root", "intermediate_root", "output_root", "models_root", "root_metadata"]:
                if key in paths and paths[key]:
                    resolved = (original_cwd / paths[key]).resolve()
                    paths[key] = str(resolved)

    config_json = json.dumps(merged_config)
    return merged_config, config_json


# ============================================================================
# Flow Management (Dev vs Prod)
# ============================================================================


def _handle_dev_mode(config_path: Optional[Path]) -> None:
    """Handle development mode: serve flows from local code.

    Args:
        config_path: Config file path
    """
    console.print("[cyan]Serving flows from local code...[/cyan]")
    _serve_flows(config_path)
    console.print("[green]✓[/green] Dev serving stopped\n")


def _serve_flows(config_path: Optional[Path]) -> None:
    """Serve flows for development using local code.

    Args:
        config_path: Config file path (configuration.toml)
    """
    from prefect import serve

    from w2t_bkin.config import BatchFlowConfig, SessionConfig
    from w2t_bkin.flows import batch_process_flow, process_session_flow

    package_root = Path(__file__).parent.parent.parent.parent.absolute()

    # Load and normalize config to get both dict and SessionConfig
    merged_config_dict, config_json = _load_and_normalize_config(config_path)

    # Build SessionConfig from the merged dict (excluding paths/project)
    # Paths will come from environment variables at runtime
    session_config_data = {k: v for k, v in merged_config_dict.items() if k not in ("project", "paths")}
    session_config_defaults = SessionConfig(**session_config_data)

    # Set path environment variables for dev mode (only if not already set)
    # This respects .workers/.env and explicit exports
    project_root = Path.cwd()
    os.environ.setdefault("W2T_RAW_ROOT", str(project_root / "data" / "raw"))
    os.environ.setdefault("W2T_INTERMEDIATE_ROOT", str(project_root / "data" / "interim"))
    os.environ.setdefault("W2T_OUTPUT_ROOT", str(project_root / "data" / "processed"))
    os.environ.setdefault("W2T_MODELS_ROOT", str(project_root / "models"))

    original_cwd = Path.cwd()
    try:
        os.chdir(package_root)

        # Create session deployment with config defaults from TOML
        process_session_deployment = process_session_flow.to_deployment(
            name="process-session",
            parameters={
                "subject_id": "subject-001",  # Example default
                "session_id": "session-001",  # Example default
                "config": session_config_defaults.model_dump(mode="json"),  # JSON-safe
            },
            tags=["w2t-bkin", "development"],
            version="dev",
        )
        console.print("[dim]  ✓ process-session deployment created[/dim]")

        # Create batch deployment
        batch_config_defaults = BatchFlowConfig(
            configuration=session_config_defaults,
            subject_filter=None,
            session_filter=None,
            max_parallel=4,
        )
        batch_process_deployment = batch_process_flow.to_deployment(
            name="batch-process",
            parameters={"config": batch_config_defaults.model_dump(mode="json")},
            tags=["w2t-bkin", "development"],
            version="dev",
        )
        console.print("[dim]  ✓ batch-process deployment created[/dim]")

        console.print("[yellow]⚡ Dev deployments are being served (leave this running)[/yellow]")
        console.print("[dim]  Trigger runs from the UI or with 'prefect deployment run ...'[/dim]\n")

        try:
            serve(process_session_deployment, batch_process_deployment)
        except KeyboardInterrupt:
            pass

    finally:
        os.chdir(original_cwd)


def _handle_prod_mode(config_path: Optional[Path], project_root: Path) -> None:
    """Handle production mode: create work pool and deploy flows.

    Args:
        config_path: Config file path
        project_root: Experiment/project root directory (cwd)
    """
    console.print("[cyan]Creating work pool 'docker-pool'...[/cyan]")
    _create_work_pool(project_root)
    console.print("[green]✓[/green] Work pool created\n")

    console.print("[cyan]Deploying flows with Docker image...[/cyan]")
    _deploy_flows(config_path, project_root)
    console.print("[green]✓[/green] Flows deployed\n")

    _print_manual_worker_instructions()


def _create_work_pool(project_root: Path) -> None:
    """Create Prefect Docker work pool with volume mounts.

    Ensures volume mounts are configured even if the pool already exists.
    This function is idempotent and safe to call multiple times.

    Args:
        project_root: Experiment/project root directory (cwd when server starts)
    """
    import json
    import tempfile

    pool_name = "docker-pool"

    # Check if pool already exists
    result = subprocess.run(
        _get_prefect_cmd() + ["work-pool", "inspect", pool_name],
        capture_output=True,
        text=True,
    )

    pool_exists = result.returncode == 0

    if not pool_exists:
        # Create docker-type work pool
        console.print(f"[dim]  Creating work pool '{pool_name}'...[/dim]")
        subprocess.run(
            _get_prefect_cmd() + ["work-pool", "create", pool_name, "--type", "docker"],
            check=True,
            capture_output=True,
        )
    else:
        console.print(f"[dim]  Work pool '{pool_name}' already exists, updating volume configuration...[/dim]")

    # Build volume mount list
    # Mount project data directories into container at fixed paths
    volumes = [
        f"{project_root / 'data'}:/data:rw",
        f"{project_root / 'models'}:/models:ro",
    ]

    # Add config mount if configuration.toml exists
    if (project_root / "configuration.toml").exists():
        volumes.append(f"{project_root / 'configuration.toml'}:/configs/configuration.toml:ro")

    # Get default base job template to avoid clobbering required fields
    default_template_result = subprocess.run(
        _get_prefect_cmd() + ["work-pool", "get-default-base-job-template", "--type", "docker"],
        capture_output=True,
        text=True,
        check=True,
    )
    base_template = json.loads(default_template_result.stdout)

    # Inject volumes into job_configuration
    if "job_configuration" not in base_template:
        base_template["job_configuration"] = {}
    base_template["job_configuration"]["volumes"] = volumes

    # Write to temp file and apply via prefect work-pool set-base-job-template
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(base_template, f)
        temp_path = f.name

    try:
        subprocess.run(
            _get_prefect_cmd() + ["work-pool", "set-base-job-template", pool_name, "--base-job-template", temp_path],
            check=True,
            capture_output=True,
        )
        console.print(f"[dim]  ✓ Configured volume mounts for '{pool_name}'[/dim]")
        console.print(f"[dim]    Volumes: {len(volumes)} mounts[/dim]")
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _deploy_flows(config_path: Optional[Path], project_root: Path) -> None:
    """Deploy flows for production using Docker image.

    Args:
        config_path: Config file path (configuration.toml)
        project_root: Experiment/project root directory (cwd)
    """
    from w2t_bkin.config import BatchFlowConfig, SessionConfig
    from w2t_bkin.flows import batch_process_flow, process_session_flow

    package_root = Path(__file__).parent.parent.parent.parent.absolute()

    # Generate container-native config (uses /data, /models, etc.)
    container_config_dict, config_json = _load_and_normalize_config(config_path, for_container=True)

    # Build SessionConfig from container-normalized dict (excluding paths/project)
    session_config_data = {k: v for k, v in container_config_dict.items() if k not in ("project", "paths")}
    session_config_defaults = SessionConfig(**session_config_data)

    # Get Docker image
    docker_image = _get_docker_image(project_root)
    console.print(f"[dim]  Docker image: {docker_image}[/dim]")
    console.print(f"[dim]  Using container-native paths (/data, /models)[/dim]")

    # Build volume mount list (per-deployment fallback)
    volumes = [
        f"{project_root / 'data'}:/data:rw",
        f"{project_root / 'models'}:/models:ro",
    ]
    if (project_root / "configuration.toml").exists():
        volumes.append(f"{project_root / 'configuration.toml'}:/configs/configuration.toml:ro")

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
                    # Path env vars for container
                    "W2T_RAW_ROOT": "/data/raw",
                    "W2T_INTERMEDIATE_ROOT": "/data/interim",
                    "W2T_OUTPUT_ROOT": "/data/processed",
                    "W2T_MODELS_ROOT": "/models",
                },
                "volumes": volumes,
            },
            "tags": ["w2t-bkin", "production"],
            "version": "1.0.0",
        }

        # Deploy session flow with config defaults from TOML
        process_session_flow.deploy(
            name="process-session",
            parameters={
                "subject_id": "subject-001",  # Example default
                "session_id": "session-001",  # Example default
                "config": session_config_defaults.model_dump(mode="json"),  # JSON-safe
            },
            description="Process a single experimental session through the w2t-bkin pipeline.",
            **common_params,
        )
        console.print("[dim]  ✓ process-session deployed[/dim]")

        # Deploy batch flow
        batch_config_defaults = BatchFlowConfig(
            configuration=session_config_defaults,
            subject_filter=None,
            session_filter=None,
            max_parallel=4,
        )
        batch_process_flow.deploy(
            name="batch-process",
            parameters={"config": batch_config_defaults.model_dump(mode="json")},
            description="Process multiple experimental sessions in parallel.",
            **common_params,
        )
        console.print("[dim]  ✓ batch-process deployed[/dim]")

    finally:
        os.chdir(original_cwd)


# ============================================================================
# Platform Utilities
# ============================================================================


def _get_docker_image(project_root: Path) -> str:
    """Get Docker image for deployments.

    Checks environment variables and .workers/.env for image configuration.
    Falls back to latest tag if not specified.

    Args:
        project_root: Experiment/project root directory (cwd)

    Returns:
        Docker image tag (e.g., "ghcr.io/borjaest/w2t-bkin:latest")
    """
    # Check environment variable first
    if image := os.getenv("W2T_DOCKER_IMAGE"):
        return image

    # Check .workers/.env file in project root
    env_file = project_root / ".workers" / ".env"
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
