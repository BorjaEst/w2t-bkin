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
    config_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Path to configuration TOML file"),
    subject_filter: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by specific subject ID"),
    session_filter: Optional[str] = typer.Option(None, "--session", "-x", help="Filter by specific session ID"),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json, tsv, or plain"),
):
    """Discover available sessions from raw data directory.

    This command scans the raw_root directory and lists all valid subject/session
    combinations that can be processed by the pipeline. A valid session must
    have either a session.toml or metadata.toml file.

    Output formats:
    - json: Detailed JSON with metadata information
    - tsv: Tab-separated values (subject<TAB>session)
    - plain: Human-readable table

    Example:
        $ w2t-bkin discover config.toml
        $ w2t-bkin discover config.toml --format plain
        $ w2t-bkin discover config.toml --subject subject-001
        $ w2t-bkin discover config.toml --format tsv | parallel --col-sep '\\t' w2t-bkin run config.toml {1} {2}
    """
    try:
        from w2t_bkin.utils import discover_sessions

        sessions = discover_sessions(
            config_path=config_path,
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
