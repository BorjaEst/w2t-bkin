"""Pipeline processing commands.

IMPORTANT: The run() and batch() functions in this module are NOT registered
in the CLI (see cli/__init__.py) because they require heavy processing dependencies
from the [worker] extra (DeepLabCut, Facemap, NWB validation, etc.).

These functions are available for:
- Programmatic API usage: from w2t_bkin.cli.pipeline import run, batch
- Testing and development workflows
- Custom scripts with explicit dependency management

Production Workflow:
    Instead of calling these functions directly, users should:
    1. Install base package: pip install w2t-bkin
    2. Start server: w2t-bkin server start
    3. Install worker environment: pip install w2t-bkin[worker] (or use Docker)
    4. Start worker: w2t-bkin worker start
    5. Submit flows through Prefect UI at http://localhost:4200

    This separation allows:
    - Lightweight orchestration (server/UI) without heavy dependencies
    - Distributed workers with full processing capabilities
    - Proper dependency isolation and version control
"""

import logging
from pathlib import Path
from typing import Optional

import typer

from w2t_bkin.cli.utils import console


def discover(
    experiment_root: Path = typer.Argument(..., exists=True, help="Path to experiment root directory (contains data/raw/)"),
    subject_filter: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by specific subject ID"),
    session_filter: Optional[str] = typer.Option(None, "--session", "-x", help="Filter by specific session ID"),
    raw_root: Optional[Path] = typer.Option(None, "--raw-root", help="Override raw data location (advanced)"),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json, tsv, or plain"),
):
    """Discover available sessions from experiment directory.

    This command scans the raw data directory and lists all valid subject/session
    combinations that can be processed by the pipeline. A valid session must
    have either a session.toml or metadata.toml file.

    The command expects an experiment root directory (created by 'w2t-bkin data init').
    By default, it discovers sessions in <experiment_root>/data/raw/.

    Output formats:
    - json: Detailed JSON with metadata information
    - tsv: Tab-separated values (subject<TAB>session)
    - plain: Human-readable table

    Example:
        $ w2t-bkin discover /path/to/experiment
        $ w2t-bkin discover . --format plain
        $ w2t-bkin discover /path/to/experiment --subject subject-001
        $ w2t-bkin discover . --raw-root /custom/raw/location
        $ w2t-bkin discover . --format tsv | parallel --col-sep '\\t' process-session {1} {2}
    """
    try:
        from w2t_bkin.utils import discover_sessions_in_raw_root

        # Determine raw root directory
        if raw_root:
            # Explicit override
            raw_data_root = raw_root
        elif (experiment_root / "data" / "raw").exists():
            # Standard layout: <root>/data/raw/
            raw_data_root = experiment_root / "data" / "raw"
        elif experiment_root.is_file() and experiment_root.suffix == ".toml":
            # Legacy: config file passed instead of experiment root
            console.print("[yellow]Warning: Passing configuration file is deprecated.[/yellow]")
            console.print("[yellow]Please use experiment root directory instead:[/yellow]")
            console.print(f"[yellow]  w2t-bkin discover {experiment_root.parent}[/yellow]\n")

            # Try to load config for backwards compat
            try:
                from w2t_bkin.config import load_config

                config = load_config(experiment_root)
                if "paths" in config and "raw_root" in config["paths"]:
                    raw_data_root = Path(config["paths"]["raw_root"])
                else:
                    console.print("[red]Error: Config file has no paths.raw_root (deprecated config format)[/red]")
                    console.print("[red]Use: w2t-bkin discover <experiment_root>[/red]")
                    raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Error: Could not load config: {e}[/red]")
                raise typer.Exit(1)
        else:
            # Assume experiment_root IS the raw root (direct path)
            raw_data_root = experiment_root

        if not raw_data_root.exists():
            console.print(f"[red]Error: Raw data directory not found: {raw_data_root}[/red]")
            raise typer.Exit(1)

        # Discover sessions
        sessions = discover_sessions_in_raw_root(
            raw_root=raw_data_root,
            subject_filter=subject_filter,
            session_filter=session_filter,
        )

        if not sessions:
            console.print("[yellow]No sessions found matching filters[/yellow]")
            raise typer.Exit(0)

        output = format_discoveries(sessions, output_format)
        print(output)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def version():
    """Display version information."""
    try:
        from w2t_bkin import __version__

        console.print(f"[bold cyan]w2t-bkin[/bold cyan] version [yellow]{__version__}[/yellow]")
        console.print("\nW2T Body Kinematics Pipeline")
        console.print("Prefect-native NWB processing for behavioral neuroscience")
        console.print("\n[dim]https://github.com/BorjaEst/w2t-bkin[/dim]")
    except ImportError:
        console.print("[yellow]Version information not available[/yellow]")
