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


def _prepare_worker_config(
    workers_env: dict[str, str],
    api_url: Optional[str],
    port: int,
    worker_type: str,
    name_prefix: Optional[str],
) -> dict:
    """Prepare worker configuration from environment and CLI options.

    Args:
        workers_env: Environment variables from .workers/.env
        api_url: User-specified API URL (takes precedence)
        port: Prefect server port
        worker_type: Worker type (docker, process)
        name_prefix: User-specified name prefix

    Returns:
        Configuration dictionary with api_url, name_prefix, docker_image
    """
    # Determine API URL using platform-aware helper
    if api_url is None:
        api_url = workers_env.get("PREFECT_API_URL") or _get_docker_api_url(port)

    # Determine worker name prefix
    if name_prefix is None:
        name_prefix = f"{worker_type}-worker"

    # Get Docker image for docker workers
    docker_image = workers_env.get("W2T_DOCKER_IMAGE", "ghcr.io/borjaest/w2t-bkin:latest")

    return {
        "api_url": api_url,
        "name_prefix": name_prefix,
        "docker_image": docker_image,
    }


def _print_worker_startup_summary(config: dict, worker_type: str, count: int, pool: str) -> None:
    """Print worker startup configuration summary.

    Args:
        config: Worker configuration dictionary
        worker_type: Worker type (docker, process)
        count: Number of workers
        pool: Work pool name
    """
    console.print(f"  Pool: [yellow]{pool}[/yellow] (type: {worker_type})")
    console.print(f"  Workers: [yellow]{count}[/yellow]")
    console.print(f"  API URL: [dim]{config['api_url']}[/dim]")
    if worker_type == "docker":
        console.print(f"  Image: [dim]{config['docker_image']}[/dim]")
    console.print()


def _generate_worker_name(name_prefix: str, index: int, count: int) -> str:
    """Generate worker name based on prefix and count.

    Args:
        name_prefix: Worker name prefix
        index: Current worker index (0-based)
        count: Total number of workers

    Returns:
        Worker name (with suffix if count > 1)
    """
    return f"{name_prefix}-{index+1}" if count > 1 else name_prefix


def _start_workers(
    count: int,
    worker_type: str,
    pool: str,
    config: dict,
    limit: int,
    work_queue: Optional[str],
    workers_env: dict[str, str],
    workers_dir: Path,
    detach: bool,
) -> list[tuple[str, str]]:
    """Start multiple workers and return list of successfully started workers.

    Args:
        count: Number of workers to start
        worker_type: Worker type (docker, process)
        pool: Work pool name
        config: Worker configuration dictionary
        limit: Concurrent flow run limit per worker
        work_queue: Optional work queue name
        workers_env: Environment variables from .workers/.env
        workers_dir: Directory for logs
        detach: Whether to run detached

    Returns:
        List of tuples (worker_name, worker_type) for successfully started workers
    """
    started_workers = []

    for i in range(count):
        worker_name = _generate_worker_name(config["name_prefix"], i, count)

        if worker_type == "docker":
            started = _start_docker_worker(
                worker_name=worker_name,
                pool=pool,
                api_url=config["api_url"],
                docker_image=config["docker_image"],
                limit=limit,
                work_queue=work_queue,
                workers_env=workers_env,
                workers_dir=workers_dir,
                detach=detach,
            )
            if started:
                started_workers.append((worker_name, "docker"))
        else:
            started = _start_process_worker(
                worker_name=worker_name,
                pool=pool,
                worker_type=worker_type,
                api_url=config["api_url"],
                limit=limit,
                work_queue=work_queue,
                workers_dir=workers_dir,
                detach=detach,
            )
            if started:
                started_workers.append((worker_name, "process"))

    if not started_workers:
        console.print("[yellow]No workers started[/yellow]")
        raise typer.Exit(1)

    return started_workers


def _print_worker_start_summary(started_workers: list[tuple[str, str]], workers_dir: Path) -> None:
    """Print summary of successfully started workers.

    Args:
        started_workers: List of (worker_name, worker_type) tuples
        workers_dir: Directory for worker logs
    """
    console.print(f"\n[green]✓ Started {len(started_workers)} worker(s)[/green]")

    for name, wtype in started_workers:
        if wtype == "docker":
            console.print(f"  • {name} (container)")
        else:
            console.print(f"  • {name} (subprocess)")

    # Print log instructions based on worker types
    has_docker = any(wtype == "docker" for _, wtype in started_workers)
    has_process = any(wtype == "process" for _, wtype in started_workers)

    if has_docker:
        console.print(f"\n[dim]Docker worker logs: docker logs <worker-name>[/dim]")
    if has_process:
        console.print(f"\n[dim]Process worker logs: {workers_dir}/<worker-name>.log[/dim]")

    console.print(f"[dim]Stop workers: w2t-bkin worker stop[/dim]")


def _track_process_worker(worker_name: str, pid: int, workers_dir: Path) -> None:
    """Track process worker PID for later stopping.

    Args:
        worker_name: Worker name
        pid: Process ID
        workers_dir: Directory for worker metadata
    """
    pid_file = workers_dir / f"{worker_name}.pid"
    pid_file.write_text(str(pid))


def _get_tracked_process_workers(workers_dir: Path) -> dict[str, int]:
    """Get tracked process workers from PID files.

    Args:
        workers_dir: Directory containing PID files

    Returns:
        Dictionary mapping worker_name -> pid
    """
    workers_dir.mkdir(exist_ok=True)
    tracked = {}

    for pid_file in workers_dir.glob("*.pid"):
        worker_name = pid_file.stem
        try:
            pid = int(pid_file.read_text().strip())
            # Verify process is still running
            if _is_process_running(pid):
                tracked[worker_name] = pid
            else:
                # Clean up stale PID file
                pid_file.unlink(missing_ok=True)
        except (ValueError, OSError):
            # Invalid PID file, clean up
            pid_file.unlink(missing_ok=True)

    return tracked


def _is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID

    Returns:
        True if process exists and is running
    """
    try:
        # Send signal 0 to check if process exists (doesn't actually send a signal)
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _stop_process_worker(worker_name: str, pid: int, force: bool, workers_dir: Path) -> bool:
    """Stop a process worker by PID.

    Args:
        worker_name: Worker name
        pid: Process ID
        force: Whether to force kill (SIGKILL) instead of graceful (SIGTERM)
        workers_dir: Directory containing PID files

    Returns:
        True if stopped successfully
    """
    import signal

    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)

        # Clean up PID file
        pid_file = workers_dir / f"{worker_name}.pid"
        pid_file.unlink(missing_ok=True)

        return True
    except (OSError, ProcessLookupError):
        # Process already dead, clean up PID file
        pid_file = workers_dir / f"{worker_name}.pid"
        pid_file.unlink(missing_ok=True)
        return False


@worker_app.command(name="start")
def start(
    pool: str = typer.Option("docker-pool", "--pool", "-p", help="Work pool name"),
    worker_type: str = typer.Option("docker", "--type", "-t", help="Worker type (docker, process, etc.)"),
    count: int = typer.Option(1, "--count", "-n", help="Number of workers to start"),
    name_prefix: Optional[str] = typer.Option(None, "--name", help="Worker name prefix (default: docker-worker or process-worker)"),
    limit: int = typer.Option(1, "--limit", "-l", help="Concurrent flow runs per worker"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Prefect API URL (auto-detected if not specified)"),
    work_queue: Optional[str] = typer.Option(None, "--work-queue", "-q", help="Work queue name (optional)"),
    detach: bool = typer.Option(True, "--detach/--foreground", help="Run workers in background (detached) or foreground"),
    port: int = typer.Option(4200, "--port", help="Prefect server port (for API URL auto-detection)"),
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

    # Load configuration
    workers_env = _load_workers_env()
    config = _prepare_worker_config(
        workers_env=workers_env,
        api_url=api_url,
        port=port,
        worker_type=worker_type,
        name_prefix=name_prefix,
    )

    _print_worker_startup_summary(config, worker_type, count, pool)

    # Ensure .workers directory exists
    workers_dir = Path.cwd() / ".workers"
    workers_dir.mkdir(exist_ok=True)

    # Start workers
    try:
        started_workers = _start_workers(
            count=count,
            worker_type=worker_type,
            pool=pool,
            config=config,
            limit=limit,
            work_queue=work_queue,
            workers_env=workers_env,
            workers_dir=workers_dir,
            detach=detach,
        )

        _print_worker_start_summary(started_workers, workers_dir)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)


def _build_docker_run_command(
    worker_name: str,
    pool: str,
    api_url: str,
    docker_image: str,
    limit: int,
    work_queue: Optional[str],
    workers_env: dict[str, str],
    detach: bool,
) -> list[str]:
    """Build docker run command for worker container.

    Args:
        worker_name: Name for the worker container
        pool: Work pool name
        api_url: Prefect API URL
        docker_image: Docker image to use
        limit: Concurrent flow run limit
        work_queue: Optional work queue name
        workers_env: Environment variables from .workers/.env
        detach: Whether to run detached

    Returns:
        Docker run command as list of strings
    """
    cmd = ["docker", "run"]

    # Container mode: detached or interactive
    if detach:
        cmd.append("-d")
    else:
        cmd.extend(["-it", "--rm"])

    # Core configuration
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
            "/var/run/docker.sock:/var/run/docker.sock",
        ]
    )

    # Optional work queue
    if work_queue:
        cmd.extend(["-e", f"WORK_QUEUE={work_queue}"])

    # Pass through additional env vars from .workers/.env
    for key, value in workers_env.items():
        if key.startswith("W2T_") or key.startswith("PREFECT_"):
            if key not in ["PREFECT_API_URL", "WORK_POOL", "WORKER_NAME"]:
                cmd.extend(["-e", f"{key}={value}"])

    # Platform-specific networking
    if _is_linux():
        cmd.extend(["--network", "host"])

    # Logging configuration for detached mode
    if detach:
        cmd.extend(
            [
                "--log-driver",
                "json-file",
                "--log-opt",
                "max-size=10m",
                "--log-opt",
                "max-file=3",
            ]
        )

    cmd.append(docker_image)
    return cmd


def _verify_docker_worker_running(worker_name: str) -> bool:
    """Verify that a Docker worker container is running.

    Args:
        worker_name: Name of the worker container

    Returns:
        True if container is running, False otherwise (logs failure details)
    """
    time.sleep(2)
    check_result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", worker_name],
        capture_output=True,
        text=True,
    )

    if check_result.stdout.strip() == "true":
        return True

    # Container exited - show why
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
    cmd = _build_docker_run_command(
        worker_name=worker_name,
        pool=pool,
        api_url=api_url,
        docker_image=docker_image,
        limit=limit,
        work_queue=work_queue,
        workers_env=workers_env,
        detach=detach,
    )

    try:
        if detach:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_id = result.stdout.strip()[:12]
            console.print(f"  [dim]Started container {container_id}...[/dim]")
            return _verify_docker_worker_running(worker_name)
        else:
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
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                # Track PID for later stopping
                _track_process_worker(worker_name, process.pid, workers_dir)
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

    docker_stopped = _stop_docker_workers(name, force)
    process_stopped = _stop_process_workers(name, force)

    total = docker_stopped + process_stopped
    if total > 0:
        console.print(f"\n[green]Stopped {total} worker(s) total[/green]")
    else:
        console.print("\n[dim]No workers found to stop[/dim]")


def _stop_docker_workers(name: Optional[str], force: bool) -> int:
    """Stop Docker worker containers.

    Args:
        name: Specific worker name (or None for all)
        force: Whether to force kill

    Returns:
        Number of workers stopped
    """
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

        if not containers:
            console.print("[dim]No docker workers found[/dim]")
            return 0

        for container in containers:
            stop_cmd = ["docker", "kill" if force else "stop", container]
            subprocess.run(stop_cmd, check=True, capture_output=True)
            subprocess.run(["docker", "rm", container], check=True, capture_output=True)
            console.print(f"  [green]✓[/green] Stopped docker worker: {container}")

        return len(containers)

    except FileNotFoundError:
        console.print("[dim]Docker not available (skipping docker workers)[/dim]")
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Warning (docker workers): {e}[/yellow]")
        return 0


def _stop_process_workers(name: Optional[str], force: bool) -> int:
    """Stop process workers.

    Args:
        name: Specific worker name (or None for all)
        force: Whether to force kill

    Returns:
        Number of workers stopped
    """
    workers_dir = Path.cwd() / ".workers"
    tracked = _get_tracked_process_workers(workers_dir)

    if name:
        tracked = {k: v for k, v in tracked.items() if k == name}

    if not tracked:
        console.print("[dim]No process workers found[/dim]")
        return 0

    stopped = 0
    for worker_name, pid in tracked.items():
        if _stop_process_worker(worker_name, pid, force, workers_dir):
            console.print(f"  [green]✓[/green] Stopped process worker: {worker_name} (PID {pid})")
            stopped += 1
        else:
            console.print(f"  [yellow]![/yellow] Process worker {worker_name} (PID {pid}) not running")

    return stopped


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
