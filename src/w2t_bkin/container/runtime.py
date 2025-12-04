"""Container runtime detection and management."""

from enum import Enum
import shutil
import subprocess
import sys
from typing import Optional


class ContainerRuntime(Enum):
    """
    Available container runtimes in priority order.

    Priority: podman > docker > apptainer > singularity
    """

    PODMAN = "podman"
    DOCKER = "docker"
    APPTAINER = "apptainer"
    SINGULARITY = "singularity"
    NONE = None

    def __str__(self) -> str:
        """String representation of runtime."""
        return self.value if self.value else "none"


def detect_runtime() -> ContainerRuntime:
    """
    Detect available container runtime.

    Checks for container runtimes in priority order:
    1. Podman (preferred for open-source, rootless execution)
    2. Docker (common, but has licensing restrictions)
    3. Apptainer (HPC standard)
    4. Singularity (older name for Apptainer)

    Returns:
        ContainerRuntime enum indicating detected runtime.

    Example:
        >>> runtime = detect_runtime()
        >>> if runtime == ContainerRuntime.NONE:
        ...     print("No container runtime found")
        >>> else:
        ...     print(f"Using {runtime}")
    """
    # Check Podman (priority 1)
    if shutil.which("podman"):
        return ContainerRuntime.PODMAN

    # Check Docker (priority 2)
    # Verify daemon is running, not just binary present
    if shutil.which("docker"):
        try:
            result = subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=5, text=True)
            if result.returncode == 0:
                return ContainerRuntime.DOCKER
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            # Docker binary exists but daemon not running
            pass

    # Check Apptainer (priority 3)
    if shutil.which("apptainer"):
        return ContainerRuntime.APPTAINER

    # Check Singularity (priority 4, older name)
    if shutil.which("singularity"):
        return ContainerRuntime.SINGULARITY

    return ContainerRuntime.NONE


def get_runtime_version(runtime: ContainerRuntime) -> Optional[str]:
    """
    Get version string for a container runtime.

    Args:
        runtime: Container runtime to check

    Returns:
        Version string (e.g., "4.8.0") or None if unavailable.

    Example:
        >>> runtime = detect_runtime()
        >>> version = get_runtime_version(runtime)
        >>> print(f"{runtime} version: {version}")
    """
    if runtime == ContainerRuntime.NONE:
        return None

    try:
        result = subprocess.run([runtime.value, "--version"], capture_output=True, timeout=5, text=True, check=True)
        # Parse version from output
        # Format varies: "podman version 4.8.0" or "Docker version 24.0.7"
        output = result.stdout.strip()
        return output
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def check_compose_support(runtime: ContainerRuntime) -> bool:
    """
    Check if runtime supports docker-compose commands.

    Args:
        runtime: Container runtime to check

    Returns:
        True if 'compose' subcommand is supported.

    Note:
        Podman and Docker support 'compose' subcommand.
        Apptainer/Singularity do not.
    """
    if runtime not in [ContainerRuntime.PODMAN, ContainerRuntime.DOCKER]:
        return False

    try:
        result = subprocess.run([runtime.value, "compose", "--version"], capture_output=True, timeout=5, text=True, check=True)
        return result.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def print_runtime_info(runtime: ContainerRuntime) -> None:
    """
    Print information about detected runtime to stdout.

    Args:
        runtime: Detected container runtime
    """
    if runtime == ContainerRuntime.NONE:
        print("❌ No container runtime detected.", file=sys.stderr)
        print("\nPlease install one of the following:", file=sys.stderr)
        print("  • Podman Desktop (recommended): https://podman-desktop.io/", file=sys.stderr)
        print("  • Docker: https://docs.docker.com/get-docker/", file=sys.stderr)
        print("  • Apptainer: https://apptainer.org/", file=sys.stderr)
        return

    version = get_runtime_version(runtime)
    version_str = f" ({version})" if version else ""
    print(f"🔧 Using {runtime}{version_str}")

    # Warn if using Docker
    if runtime == ContainerRuntime.DOCKER:
        print("ℹ️  Note: Docker Desktop requires paid license for large organizations")
        print("   Consider switching to Podman Desktop (free & open-source)")


def get_compose_command(runtime: ContainerRuntime) -> list[str]:
    """
    Get the compose command for a runtime.

    Args:
        runtime: Container runtime

    Returns:
        List of command parts (e.g., ["podman", "compose"])

    Raises:
        ValueError: If runtime doesn't support compose
    """
    if not check_compose_support(runtime):
        raise ValueError(f"{runtime} does not support docker-compose commands")

    return [runtime.value, "compose"]
