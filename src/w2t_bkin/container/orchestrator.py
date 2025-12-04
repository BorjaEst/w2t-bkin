"""Container orchestration functions for managing w2t-bkin services."""

from pathlib import Path
import subprocess
import sys
from typing import Optional

from .runtime import ContainerRuntime, check_compose_support, get_compose_command, print_runtime_info


def _get_compose_file() -> Path:
    """Get path to docker-compose.yml file."""
    # Assume we're in installed package, look for compose file in repo root
    # Try common locations
    possible_paths = [
        Path.cwd() / "docker-compose.yml",
        Path(__file__).parent.parent.parent.parent / "docker-compose.yml",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # If not found, return default (let compose fail with helpful error)
    return Path("docker-compose.yml")


def start_server(
    runtime: ContainerRuntime,
    port: int = 4200,
    detach: bool = True,
    compose_file: Optional[Path] = None,
) -> None:
    """
    Start Prefect server stack (database + server).

    Args:
        runtime: Container runtime to use (must support compose)
        port: Port for Prefect UI (default: 4200)
        detach: Run in background (default: True)
        compose_file: Path to docker-compose.yml (auto-detected if None)

    Raises:
        ValueError: If runtime doesn't support compose
        SystemExit: If compose command fails

    Example:
        >>> from w2t_bkin.container import detect_runtime, start_server
        >>> runtime = detect_runtime()
        >>> start_server(runtime, port=4200, detach=True)
    """
    if not check_compose_support(runtime):
        print(f"❌ {runtime} does not support docker-compose", file=sys.stderr)
        print("   Please use Podman or Docker for orchestration", file=sys.stderr)
        sys.exit(1)

    print_runtime_info(runtime)

    if compose_file is None:
        compose_file = _get_compose_file()

    if not compose_file.exists():
        print(f"❌ Compose file not found: {compose_file}", file=sys.stderr)
        print("   Please run this command from the w2t-bkin repository root", file=sys.stderr)
        sys.exit(1)

    # Build compose command
    cmd = get_compose_command(runtime)
    cmd.extend(["-f", str(compose_file), "-p", "w2t-bkin", "up"])

    if detach:
        cmd.append("-d")

    # Start only server services (postgres + server)
    cmd.extend(["postgres", "server"])

    print(f"🚀 Starting Prefect server stack...")
    print(f"   Compose file: {compose_file}")
    print(f"   Port: {port}")

    # Set environment variable for port
    env = {"PREFECT_UI_PORT": str(port)}

    try:
        subprocess.run(cmd, check=True, env={**subprocess.os.environ, **env})

        if detach:
            print(f"\n✅ Server started successfully")
            print(f"📊 Web UI: http://localhost:{port}")
            print(f"\nView logs: {runtime} logs -f w2t-bkin-server")
            print(f"Stop server: w2t-bkin container stop")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)


def start_workers(
    runtime: ContainerRuntime,
    count: int = 1,
    config_path: Optional[str] = None,
    compose_file: Optional[Path] = None,
) -> None:
    """
    Start worker container(s).

    Args:
        runtime: Container runtime to use
        count: Number of worker replicas (default: 1)
        config_path: Path to config.toml (optional)
        compose_file: Path to docker-compose.yml (auto-detected if None)

    Raises:
        ValueError: If runtime doesn't support compose
        SystemExit: If compose command fails

    Example:
        >>> from w2t_bkin.container import detect_runtime, start_workers
        >>> runtime = detect_runtime()
        >>> start_workers(runtime, count=4)
    """
    if not check_compose_support(runtime):
        print(f"❌ {runtime} does not support docker-compose", file=sys.stderr)
        sys.exit(1)

    print_runtime_info(runtime)

    if compose_file is None:
        compose_file = _get_compose_file()

    if not compose_file.exists():
        print(f"❌ Compose file not found: {compose_file}", file=sys.stderr)
        sys.exit(1)

    # Build compose command
    cmd = get_compose_command(runtime)
    cmd.extend(["-f", str(compose_file), "-p", "w2t-bkin", "up", "-d", "--scale", f"worker={count}"])

    print(f"🚀 Starting {count} worker(s)...")

    # Set environment variables
    env = {"WORKER_REPLICAS": str(count)}
    if config_path:
        env["CONFIG_PATH"] = config_path

    try:
        subprocess.run(cmd, check=True, env={**subprocess.os.environ, **env})

        print(f"\n✅ Started {count} worker(s)")
        print(f"\nView logs: {runtime} logs -f w2t-bkin-worker-1")
        print(f"View status: w2t-bkin container status")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to start workers: {e}", file=sys.stderr)
        sys.exit(1)


def stop_all(runtime: ContainerRuntime, compose_file: Optional[Path] = None) -> None:
    """
    Stop all w2t-bkin containers.

    Args:
        runtime: Container runtime to use
        compose_file: Path to docker-compose.yml (auto-detected if None)

    Raises:
        ValueError: If runtime doesn't support compose
        SystemExit: If compose command fails

    Example:
        >>> from w2t_bkin.container import detect_runtime, stop_all
        >>> runtime = detect_runtime()
        >>> stop_all(runtime)
    """
    if not check_compose_support(runtime):
        print(f"❌ {runtime} does not support docker-compose", file=sys.stderr)
        sys.exit(1)

    print_runtime_info(runtime)

    if compose_file is None:
        compose_file = _get_compose_file()

    # Build compose command
    cmd = get_compose_command(runtime)
    cmd.extend(["-f", str(compose_file), "-p", "w2t-bkin", "down"])

    print("🛑 Stopping all w2t-bkin containers...")

    try:
        subprocess.run(cmd, check=True)
        print("✅ All containers stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to stop containers: {e}", file=sys.stderr)
        sys.exit(1)


def show_status(runtime: ContainerRuntime) -> None:
    """
    Show status of all w2t-bkin containers.

    Args:
        runtime: Container runtime to use

    Example:
        >>> from w2t_bkin.container import detect_runtime, show_status
        >>> runtime = detect_runtime()
        >>> show_status(runtime)
    """
    if not check_compose_support(runtime):
        print(f"❌ {runtime} does not support docker-compose", file=sys.stderr)
        sys.exit(1)

    print_runtime_info(runtime)
    print()

    # Build compose command
    cmd = get_compose_command(runtime)
    cmd.extend(["-p", "w2t-bkin", "ps"])

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get status: {e}", file=sys.stderr)
        sys.exit(1)


def logs(
    runtime: ContainerRuntime,
    service: str = "server",
    follow: bool = False,
    tail: Optional[int] = None,
) -> None:
    """
    Show logs for a specific service.

    Args:
        runtime: Container runtime to use
        service: Service name (server, worker, postgres)
        follow: Follow log output (default: False)
        tail: Number of lines to show (default: all)

    Example:
        >>> from w2t_bkin.container import detect_runtime, logs
        >>> runtime = detect_runtime()
        >>> logs(runtime, service="worker", follow=True, tail=100)
    """
    if not check_compose_support(runtime):
        print(f"❌ {runtime} does not support docker-compose", file=sys.stderr)
        sys.exit(1)

    # Build compose command
    cmd = get_compose_command(runtime)
    cmd.extend(["-p", "w2t-bkin", "logs"])

    if follow:
        cmd.append("-f")

    if tail:
        cmd.extend(["--tail", str(tail)])

    cmd.append(service)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get logs: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Stopped following logs")
