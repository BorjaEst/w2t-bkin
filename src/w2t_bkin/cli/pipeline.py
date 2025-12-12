"""Pipeline processing commands."""

import logging
from pathlib import Path
from typing import Optional

import typer

from ..api import BatchFlowConfig, SessionFlowConfig
from .utils import console, display_batch_result, display_session_result, format_discoveries, setup_logging


def run(
    config_path: Path = typer.Argument(..., help="Path to config.toml file"),
    subject_id: str = typer.Argument(..., help="Subject identifier (e.g., 'subject-001')"),
    session_id: str = typer.Argument(..., help="Session identifier (e.g., 'session-001')"),
    skip_bpod: bool = typer.Option(False, "--skip-bpod", help="Skip Bpod processing"),
    skip_pose: bool = typer.Option(False, "--skip-pose", help="Skip pose estimation"),
    skip_ttl: bool = typer.Option(False, "--skip-ttl", help="Skip TTL processing"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip NWB validation"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
):
    """Run the pipeline for a single session via Prefect flow.

    This command executes all phases of the Prefect-native pipeline:
    1. Initialization - Load config and create NWBFile
    2. Discovery - Find and verify files
    3. Artifact Generation - Generate pose estimation (optional)
    4. Ingestion - Process Bpod, Pose, and TTL data
    5. Assembly - Build NWB behavior tables
    6. Finalization - Write and validate NWB file

    The pipeline uses Prefect for orchestration, providing automatic retry
    logic, parallel execution, and comprehensive error handling.

    Example:
        $ w2t-bkin run config.toml subject-001 session-001
        $ w2t-bkin run config.toml subject-001 session-001 --skip-pose
        $ w2t-bkin run config.toml subject-001 session-001 --skip-validation
    """
    setup_logging(log_level)

    if not config_path.exists():
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        raise typer.Exit(1)

    try:
        from ..flows import process_session_flow

        console.print("[cyan]Starting session processing...[/cyan]")
        console.print(f"  Config: [dim]{config_path}[/dim]")
        console.print(f"  Subject: [yellow]{subject_id}[/yellow]")
        console.print(f"  Session: [yellow]{session_id}[/yellow]")
        console.print()

        # Create Pydantic config model (flow expects this, not individual kwargs)
        flow_config = SessionFlowConfig(
            config_path=str(config_path),
            subject_id=subject_id,
            session_id=session_id,
            skip_bpod=skip_bpod,
            skip_pose=skip_pose,
            skip_nwb_validation=skip_validation,
        )

        # Run flow with Pydantic model
        result = process_session_flow(config=flow_config)

        display_session_result(result)
        raise typer.Exit(0 if result.success else 1)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logging.exception("Pipeline execution failed")
        raise typer.Exit(1)


def batch(
    config_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Path to configuration TOML file"),
    subject_filter: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by specific subject ID"),
    session_filter: Optional[str] = typer.Option(None, "--session", "-x", help="Filter by specific session ID"),
    max_parallel: int = typer.Option(4, "--max-workers", "-j", help="Maximum concurrent sessions (default: 4)"),
    skip_bpod: bool = typer.Option(False, "--skip-bpod", help="Skip Bpod processing"),
    skip_pose: bool = typer.Option(False, "--skip-pose", help="Skip pose estimation"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip NWB validation"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
):
    """Process multiple sessions in parallel via Prefect flow.

    This command discovers sessions from the raw data directory and processes
    them in parallel using the Prefect batch flow. Failed sessions do not stop
    the batch - all sessions are attempted and results are aggregated.

    Features:
    - Automatic session discovery
    - Parallel execution with configurable concurrency
    - Graceful error handling (partial failures)
    - Aggregated statistics and reporting

    Example:
        $ w2t-bkin batch config.toml --max-workers 4
        $ w2t-bkin batch config.toml --subject subject-001 --max-workers 2
        $ w2t-bkin batch config.toml --session session-001
    """
    setup_logging(log_level)

    try:
        from ..flows import batch_process_flow

        console.print("[cyan]Starting batch processing...[/cyan]")
        console.print(f"  Config: [dim]{config_path}[/dim]")
        if subject_filter:
            console.print(f"  Subject filter: [yellow]{subject_filter}[/yellow]")
        if session_filter:
            console.print(f"  Session filter: [yellow]{session_filter}[/yellow]")
        console.print(f"  Max parallel: [yellow]{max_parallel}[/yellow]")
        console.print()

        # Create Pydantic config model (flow expects this, not individual kwargs)
        flow_config = BatchFlowConfig(
            config_path=str(config_path),
            subject_filter=subject_filter,
            session_filter=session_filter,
            max_parallel=max_parallel,
            skip_bpod=skip_bpod,
            skip_pose=skip_pose,
            skip_nwb_validation=skip_validation,
        )

        # Run batch flow with Pydantic model
        result = batch_process_flow(config=flow_config)

        display_batch_result(result)
        raise typer.Exit(0 if result.failed == 0 else 1)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logging.exception("Batch processing failed")
        raise typer.Exit(1)


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
        from ..utils import discover_sessions

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
        from .. import __version__

        console.print(f"[bold cyan]w2t-bkin[/bold cyan] version [yellow]{__version__}[/yellow]")
        console.print("\nW2T Body Kinematics Pipeline")
        console.print("Prefect-native NWB processing for behavioral neuroscience")
        console.print("\n[dim]https://github.com/BorjaEst/w2t-bkin[/dim]")
    except ImportError:
        console.print("[yellow]Version information not available[/yellow]")
