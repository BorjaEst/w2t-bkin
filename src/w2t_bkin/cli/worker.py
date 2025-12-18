"""Worker management commands for Prefect."""

import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Optional

import typer

from w2t_bkin.cli.utils import console

worker_app = typer.Typer(name="worker", help="Prefect worker management")


def _get_prefect_cmd() -> list[str]:
    """Get the prefect command using the current Python interpreter."""
    return [sys.executable, "-m", "prefect"]


def _is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def _is_linux() -> bool:
    """Check if running on Linux (for host networking)."""
    return platform.system() == "Linux"


def _get_docker_api_url(port: int = 4200) -> str:
    """Get the Prefect API URL for Docker workers based on platform.

    Args:
        port: Port number for the Prefect server

    Returns:
        Appropriate API URL for Docker workers
    """
    if _is_windows():
        return f"http://host.docker.internal:{port}/api"
    else:
        # Linux: use host network mode, so localhost works
        return f"http://localhost:{port}/api"


def _load_workers_env() -> dict[str, str]:
    """Load environment variables from .workers/.env if it exists.

    Returns:
        Dictionary of environment variables to pass to workers
    """
    env_file = Path.cwd() / ".workers" / ".env"
    env_vars = {}

    if not env_file.exists():
        return env_vars

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            # Remove quotes if present
            value = value.strip().strip('"').strip("'")
            env_vars[key.strip()] = value

    return env_vars


@worker_app.command(name="start")
def start(
    pool: str = typer.Option("docker-pool", "--pool", "-p", help="Work pool name"),
    worker_type: str = typer.Option("docker", "--type", "-t", help="Worker type (docker, process, etc.)"),
    count: int = typer.Option(1, "--count", "-n", help="Number of workers to start"),
    name_prefix: Optional[str] = typer.Option(None, "--name", help="Worker name prefix (default: docker-worker or process-worker)"),
    limit: int = typer.Option(1, "--limit", "-l", help="Concurrent flow runs per worker"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Prefect API URL (default: from .workers/.env or localhost:4200)"),
    work_queue: Optional[str] = typer.Option(None, "--work-queue", "-q", help="Work queue name (optional)"),
    detach: bool = typer.Option(True, "--detach/--foreground", help="Run workers in background (detached) or foreground"),
):
    """Start Prefect worker(s) to execute flow runs.

    This command starts one or more Prefect workers that poll the specified work pool
    and execute flow runs. Workers can run in the foreground (blocking) or background (detached).

    For Docker workers (default), each worker runs in a separate container with access
    to the Docker daemon. For process workers, each worker runs as a local subprocess.

    Configuration is read from .workers/.env if present (W2T_DOCKER_IMAGE, PREFECT_API_URL, etc.).

    Examples:
        # Start 1 docker worker (default)
        $ w2t-bkin worker start

        # Start 3 docker workers
        $ w2t-bkin worker start --count 3

        # Start process worker for local testing
        $ w2t-bkin worker start --type process --pool local-pool

        # Start worker in foreground (blocking, shows logs)
        $ w2t-bkin worker start --foreground

        # Custom work queue
        $ w2t-bkin worker start --work-queue high-priority
    """
    console.print("[cyan]Starting Prefect worker(s)...[/cyan]")

    # Load environment from .workers/.env
    workers_env = _load_workers_env()

    # Determine API URL
    if api_url is None:
        api_url = workers_env.get("PREFECT_API_URL") or "http://localhost:4200/api"

    # Determine worker name prefix
    if name_prefix is None:
        name_prefix = f"{worker_type}-worker"

    # Get Docker image for docker workers
    docker_image = workers_env.get("W2T_DOCKER_IMAGE", "ghcr.io/borjaest/w2t-bkin:latest")

    console.print(f"  Pool: [yellow]{pool}[/yellow] (type: {worker_type})")
    console.print(f"  Workers: [yellow]{count}[/yellow]")
    console.print(f"  API URL: [dim]{api_url}[/dim]")
    if worker_type == "docker":
        console.print(f"  Image: [dim]{docker_image}[/dim]")
    console.print()

    # Ensure .workers directory exists for logs
    workers_dir = Path.cwd() / ".workers"
    workers_dir.mkdir(exist_ok=True)

    started_workers = []

    try:
        for i in range(count):
            worker_name = f"{name_prefix}-{i+1}" if count > 1 else name_prefix

            if worker_type == "docker":
                # Start Docker worker
                started = _start_docker_worker(
                    worker_name=worker_name,
                    pool=pool,
                    api_url=api_url,
                    docker_image=docker_image,
                    limit=limit,
                    work_queue=work_queue,
                    workers_env=workers_env,
                    workers_dir=workers_dir,
                    detach=detach,
                )
                if started:
                    started_workers.append((worker_name, "docker"))
            else:
                # Start process worker (local subprocess)
                started = _start_process_worker(
                    worker_name=worker_name,
                    pool=pool,
                    worker_type=worker_type,
                    api_url=api_url,
                    limit=limit,
                    work_queue=work_queue,
                    workers_dir=workers_dir,
                    detach=detach,
                )
                if started:
                    started_workers.append((worker_name, "process"))

        # Summary
        if started_workers:
            console.print(f"\n[green]✓ Started {len(started_workers)} worker(s)[/green]")
            for name, wtype in started_workers:
                if wtype == "docker":
                    console.print(f"  • {name} (container)")
                else:
                    console.print(f"  • {name} (subprocess)")

            # Different log instructions for docker vs process workers
            has_docker = any(wtype == "docker" for _, wtype in started_workers)
            has_process = any(wtype == "process" for _, wtype in started_workers)

            if has_docker:
                console.print(f"\n[dim]Docker worker logs: docker logs <worker-name>[/dim]")
            if has_process:
                console.print(f"\n[dim]Process worker logs: {workers_dir}/<worker-name>.log[/dim]")

            console.print(f"[dim]Stop workers: w2t-bkin worker stop[/dim]")
        else:
            console.print("[yellow]No workers started[/yellow]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)


def _start_docker_worker(
    worker_name: str,
    pool: str,
    api_url: str,
    docker_image: str,
    limit: int,
    work_queue: Optional[str],
    workers_env: dict[str, str],
    workers_dir: Path,
    detach: bool,
) -> bool:
    """Start a Docker worker container.

    Args:
        worker_name: Name for the worker container
        pool: Work pool name
        api_url: Prefect API URL
        docker_image: Docker image to use
        limit: Concurrent flow run limit
        work_queue: Optional work queue name
        workers_env: Environment variables from .workers/.env
        workers_dir: Directory for logs
        detach: Whether to run detached

    Returns:
        True if started successfully
    """
    # Build docker run command
    cmd = ["docker", "run"]

    if detach:
        cmd.append("-d")
    else:
        cmd.extend(["-it", "--rm"])

    cmd.extend(
        [
            "--name",
            worker_name,
            "-e",
            f"PREFECT_API_URL={api_url}",
            "-e",
            f"WORK_POOL={pool}",
            "-e",
            f"WORKER_NAME={worker_name}",
            "-e",
            f"LIMIT={limit}",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",  # Docker socket access
        ]
    )

    # Add work queue if specified
    if work_queue:
        cmd.extend(["-e", f"WORK_QUEUE={work_queue}"])

    # Pass through W2T_* and PREFECT_* env vars from .workers/.env
    for key, value in workers_env.items():
        if key.startswith("W2T_") or key.startswith("PREFECT_"):
            # Skip if already set above
            if key not in ["PREFECT_API_URL", "WORK_POOL", "WORKER_NAME"]:
                cmd.extend(["-e", f"{key}={value}"])

    # Linux: use host networking for easier localhost access
    if _is_linux():
        cmd.extend(["--network", "host"])

    # Set log file paths
    if detach:
        log_file = workers_dir / f"{worker_name}.log"
        cmd.extend(
            [
                "--log-driver",
                "json-file",
                "--log-opt",
                f"max-size=10m",
                "--log-opt",
                "max-file=3",
            ]
        )

    cmd.append(docker_image)

    # Note: Using image's default ENTRYPOINT (/usr/local/bin/start-worker.sh)
    # Configuration is passed via environment variables above

    try:
        if detach:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_id = result.stdout.strip()[:12]
            console.print(f"  [dim]Started container {container_id}...[/dim]")

            # Verify container is still running after a short delay
            time.sleep(2)
            check_result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", worker_name],
                capture_output=True,
                text=True,
            )
            if check_result.stdout.strip() != "true":
                # Container exited - fetch logs to show why
                logs_result = subprocess.run(
                    ["docker", "logs", worker_name],
                    capture_output=True,
                    text=True,
                )
                console.print(f"  [red]Container exited immediately:[/red]")
                console.print(f"  [dim]{logs_result.stdout}{logs_result.stderr}[/dim]")
                # Clean up dead container
                subprocess.run(["docker", "rm", worker_name], capture_output=True)
                return False
        else:
            # Foreground: user sees live logs
            console.print(f"  [dim]Running in foreground (Ctrl+C to stop)...[/dim]")
            subprocess.run(cmd, check=True)

        return True

    except subprocess.CalledProcessError as e:
        console.print(f"  [red]Failed to start {worker_name}: {e.stderr}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]Error: Docker not found. Install Docker to use docker workers.[/red]")
        raise typer.Exit(1)


def _start_process_worker(
    worker_name: str,
    pool: str,
    worker_type: str,
    api_url: str,
    limit: int,
    work_queue: Optional[str],
    workers_dir: Path,
    detach: bool,
) -> bool:
    """Start a process worker as a local subprocess.

    Args:
        worker_name: Name for the worker
        pool: Work pool name
        worker_type: Worker type (process, etc.)
        api_url: Prefect API URL
        limit: Concurrent flow run limit
        work_queue: Optional work queue name
        workers_dir: Directory for logs
        detach: Whether to run detached

    Returns:
        True if started successfully
    """
    cmd = _get_prefect_cmd() + [
        "worker",
        "start",
        "--pool",
        pool,
        "--type",
        worker_type,
        "--name",
        worker_name,
        "--limit",
        str(limit),
    ]

    if work_queue:
        cmd.extend(["--work-queue", work_queue])

    env = os.environ.copy()
    env["PREFECT_API_URL"] = api_url

    try:
        if detach:
            log_file = workers_dir / f"{worker_name}.log"
            console.print(f"  [dim]Logging to {log_file}...[/dim]")

            with open(log_file, "w") as log:
                subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from parent
                )
        else:
            console.print(f"  [dim]Running in foreground (Ctrl+C to stop)...[/dim]")
            subprocess.run(cmd, env=env, check=True)

        return True

    except subprocess.CalledProcessError as e:
        console.print(f"  [red]Failed to start {worker_name}: {e}[/red]")
        return False


@worker_app.command(name="stop")
def stop(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Specific worker name to stop (default: all)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop (kill) instead of graceful shutdown"),
):
    """Stop running workers.

    For Docker workers, stops and removes containers.
    For process workers, sends termination signal.

    Examples:
        # Stop all workers
        $ w2t-bkin worker stop

        # Stop specific worker
        $ w2t-bkin worker stop --name docker-worker-1

        # Force stop
        $ w2t-bkin worker stop --force
    """
    console.print("[cyan]Stopping worker(s)...[/cyan]")

    # Find running docker worker containers
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=worker", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        containers = [c for c in result.stdout.strip().split("\n") if c]

        if name:
            containers = [c for c in containers if c == name]

        if containers:
            for container in containers:
                stop_cmd = ["docker", "stop"] if not force else ["docker", "kill"]
                stop_cmd.append(container)
                subprocess.run(stop_cmd, check=True, capture_output=True)
                subprocess.run(["docker", "rm", container], check=True, capture_output=True)
                console.print(f"  [green]✓[/green] Stopped {container}")

            console.print(f"\n[green]Stopped {len(containers)} docker worker(s)[/green]")
        else:
            console.print("[dim]No docker workers found[/dim]")

    except FileNotFoundError:
        console.print("[dim]Docker not available (skipping docker workers)[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Warning: {e}[/yellow]")

    # TODO: Add process worker stop logic (track PIDs in .workers/)
    console.print("[dim]Process worker stop: not yet implemented[/dim]")


@worker_app.command(name="status")
def status():
    """Show status of running workers.

    Lists Docker worker containers and their status.

    Example:
        $ w2t-bkin worker status
    """
    console.print("[cyan]Worker Status[/cyan]\n")

    # Check docker workers
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=worker", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stdout.strip():
            console.print("[bold]Docker Workers:[/bold]")
            console.print(result.stdout)
        else:
            console.print("[dim]No docker workers running[/dim]")

    except FileNotFoundError:
        console.print("[dim]Docker not available[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Error checking docker workers: {e}[/yellow]")
