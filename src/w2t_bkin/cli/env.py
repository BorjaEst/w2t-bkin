"""Environment file loading utilities.

Provides simple .env file parsing without external dependencies.
Follows explicit precedence model for configuration.
"""

import os
from pathlib import Path
from typing import Dict, Optional

from w2t_bkin.cli.utils import console


def load_env_file(path: Path, override: bool = False, silent: bool = False) -> Dict[str, str]:
    """Load environment variables from a file.

    Supports basic .env format:
    - KEY=VALUE (with optional quotes around value)
    - Comments starting with #
    - Blank lines (ignored)

    Args:
        path: Path to environment file
        override: If True, overwrites existing env vars; if False, only sets unset vars
        silent: If True, don't print warnings for missing files

    Returns:
        Dictionary of loaded variables (whether or not they were set in os.environ)

    Example:
        >>> load_env_file(Path(".workers/.env"))
        {'W2T_DOCKER_IMAGE': 'ghcr.io/borjaest/w2t-bkin:latest'}
        >>>
        >>> # With override
        >>> os.environ['TEST'] = 'old'
        >>> load_env_file(Path(".env"), override=True)  # Will replace 'old'
        >>> load_env_file(Path(".env"), override=False)  # Will keep 'old'
    """
    if not path.exists():
        if not silent:
            console.print(f"[dim]  Environment file not found: {path}[/dim]")
        return {}

    loaded_vars: Dict[str, str] = {}

    try:
        with open(path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()

                # Skip blank lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" not in line:
                    console.print(f"[yellow]Warning: Skipping malformed line {line_num} in {path}[/yellow]")
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove surrounding quotes
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]

                # Validate key (basic alphanumeric + underscore check)
                if not key or not all(c.isalnum() or c == "_" for c in key):
                    console.print(f"[yellow]Warning: Invalid variable name '{key}' at line {line_num} in {path}[/yellow]")
                    continue

                loaded_vars[key] = value

                # Set in environment
                if override or key not in os.environ:
                    os.environ[key] = value

    except Exception as e:
        console.print(f"[yellow]Warning: Error reading {path}: {e}[/yellow]")
        return {}

    if loaded_vars:
        console.print(f"[dim]  Loaded {len(loaded_vars)} variable(s) from {path}[/dim]")

    return loaded_vars


def load_project_env(project_root: Path, env_file: Optional[Path] = None) -> Dict[str, str]:
    """Load environment for a project (CLI convenience wrapper).

    Precedence (highest to lowest):
    1. Explicit process environment (not modified)
    2. Custom env_file (if provided)
    3. <project_root>/.workers/.env (default)
    4. (Caller sets dev defaults via setdefault after this)

    Args:
        project_root: Project/experiment root directory
        env_file: Optional custom environment file (overrides default .workers/.env)

    Returns:
        Dictionary of loaded variables

    Example:
        >>> # Load default .workers/.env
        >>> load_project_env(Path.cwd())
        >>>
        >>> # Load custom env file
        >>> load_project_env(Path.cwd(), env_file=Path("/tmp/prod.env"))
    """
    if env_file:
        # Explicit env file: must exist or warn
        if not env_file.exists():
            console.print(f"[yellow]Warning: Env file not found: {env_file}[/yellow]")
            console.print("[dim]  Continuing without env file...[/dim]")
            return {}
        return load_env_file(env_file, override=False)

    # Default: .workers/.env (silent if missing)
    default_env = project_root / ".workers" / ".env"
    if default_env.exists():
        console.print(f"[dim]  Loading environment from {default_env.relative_to(project_root.parent)}[/dim]")
    return load_env_file(default_env, override=False, silent=True)
