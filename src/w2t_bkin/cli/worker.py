"""Worker management commands for Prefect."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

import typer

from w2t_bkin.cli.utils import console, setup_logging

worker_app = typer.Typer(name="worker", help="Prefect worker management")


# ============================================================================
# Public CLI Commands
# ============================================================================


@worker_app.command(name="start")
def start(
    pool: str = typer.Option("docker-pool", "--pool", "-p", help="Work pool name"),
    worker_type: str = typer.Option("docker", "--type", "-t", help="Worker type (docker, process)"),
    limit: int = typer.Option(1, "--limit", "-l", help="Concurrent flow run limit"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Worker name (auto-generated if not provided)"),
    port: int = typer.Option(4200, "--port", help="Prefect server port (for API URL)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    env_file: Optional[Path] = typer.Option(None, "--env-file", help="Environment file to load (default: .workers/.env)"),
):
    """Start a Prefect worker to execute flow runs.

    A worker connects to a work pool and executes flow runs by creating
    execution environments (e.g., Docker containers for docker-type workers).

    Workers must run separately from the server. For production, start one
    or more workers after starting the server.

    Worker Types:
    - docker: Executes flows in Docker containers (production, requires Docker)
    - process: Executes flows in local subprocesses (development, requires [worker] extras)

    Concurrency:
    - --limit controls how many flows this worker will run simultaneously
    - Each worker can handle multiple runs up to its limit
    - Start multiple worker processes to scale horizontally

    Example:
        $ w2t-bkin server start                           # Start server first
        $ w2t-bkin worker start                            # 1 Docker worker, limit 1
        $ w2t-bkin worker start --limit 2                  # 1 Docker worker, limit 2
        $ w2t-bkin worker start --type process --limit 1   # 1 process worker (dev)
        $ w2t-bkin worker start --name "worker-gpu-1"      # Named worker

    Multiple Workers:
        Run this command multiple times in separate terminals to start
        multiple workers (e.g., for parallel processing across machines).
    """
    setup_logging(log_level)

    # Validate worker type
    if worker_type == "process":
        if not _check_worker_extras():
            console.print("[red]✗ Process workers require worker extras[/red]")
            console.print("[yellow]Install with: pip install -e .[worker][/yellow]")
            console.print("[yellow]Or use Docker workers: --type docker[/yellow]")
            raise typer.Exit(1)

    # Project root is the current working directory.
    # This matches server behavior for consistent project isolation.
    project_root = Path.cwd()

    # Process workers (dev mode): regenerate .env.dev with correct absolute paths
    if worker_type == "process":
        from w2t_bkin.cli.utils import generate_env_dev_content

        env_dev_path = project_root / ".workers" / ".env.dev"
        env_dev_path.parent.mkdir(parents=True, exist_ok=True)
        env_dev_content = generate_env_dev_content(project_root)
        env_dev_path.write_text(env_dev_content)
        console.print(f"[dim]  Regenerated {env_dev_path.relative_to(project_root.parent)} with absolute paths[/dim]")

    # Load environment files (before any other env setup)
    from w2t_bkin.cli.env import load_project_env

    # In process mode, load both .env and .env.dev (dev paths win)
    load_project_env(project_root, env_file)
    if worker_type == "process":
        from w2t_bkin.cli.env import load_env_file

        env_dev_path = project_root / ".workers" / ".env.dev"
        load_env_file(env_dev_path, override=True, silent=False)

    # Setup Prefect environment (same as server for project isolation)
    _setup_prefect_env(port, project_root)
    _ensure_prefect_api_config(port)

    # Build worker command
    worker_cmd = _get_prefect_cmd() + ["worker", "start", "--pool", pool, "--type", worker_type, "--limit", str(limit)]

    if name:
        worker_cmd.extend(["--name", name])

    # Print startup info
    console.print(f"[green]🔧 Starting Prefect Worker[/green]")
    console.print(f"[dim]  Pool: {pool}[/dim]")
    console.print(f"[dim]  Type: {worker_type}[/dim]")
    console.print(f"[dim]  Concurrency Limit: {limit}[/dim]")
    if name:
        console.print(f"[dim]  Name: {name}[/dim]")
    console.print(f"[dim]  Project: {project_root}[/dim]")
    console.print()

    try:
        # Run worker (blocking) - inherits environment with PREFECT_HOME/API_URL
        console.print("[cyan]Worker is running (press Ctrl+C to stop)...[/cyan]\n")
        subprocess.run(worker_cmd, env=os.environ.copy(), check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping worker...[/yellow]")
        console.print("[green]✓[/green] Worker stopped")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]✗ Worker failed with exit code {e.returncode}[/red]")
        raise typer.Exit(e.returncode)
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# Helper Functions (shared with server.py logic)
# ============================================================================


def _setup_prefect_env(port: int, project_root: Path) -> None:
    """Configure Prefect environment for project isolation.

    Args:
        port: Prefect UI port for API URL
        project_root: Experiment/project root directory (cwd when worker starts)
    """
    # Project isolation: Use .prefect in the current working directory.
    # Each experiment initialized via `w2t-bkin data init` gets its own
    # isolated Prefect database, deployments, and run history.
    prefect_home = project_root / ".prefect"
    prefect_home.mkdir(exist_ok=True)
    os.environ["PREFECT_HOME"] = str(prefect_home)
    os.environ["PREFECT_PROFILES_PATH"] = str(prefect_home / "profiles.toml")

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


def _check_worker_extras() -> bool:
    """Check if worker extras are installed."""
    try:
        import deeplabcut

        return True
    except ImportError:
        return False
