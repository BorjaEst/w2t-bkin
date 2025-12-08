"""Command-line interface for W2T Body Kinematics Pipeline.

This module provides a Typer-based CLI with commands for running the pipeline,
validating NWB files, inspecting session outputs, and batch processing automation.

Commands:
    run: Execute pipeline for a single subject/session
    validate: Validate an existing NWB file
    inspect: Display NWB file contents and metadata
    discover: Find all available subject/session combinations for batch processing
    batch: Process multiple sessions in parallel using multiprocessing
    version: Display version information

Batch Processing:
    The batch command provides parallel batch processing using multiprocessing:
    - Automatic retries (2 attempts) with exponential backoff
    - Parallel execution with configurable worker count
    - Graceful error handling (partial failures)
    - Simple and dependency-free (no external services required)
    
    The discover command enables shell-based batch processing with GNU Parallel:
    - Scans raw_root directory for valid session metadata
    - Outputs in JSON, TSV, or plain format
    - Supports filtering by subject or session

Example:
    # Single session processing
    $ python -m w2t_bkin.cli run config.toml subject-001 session-001
    
    # Batch processing with multiprocessing
    $ python -m w2t_bkin.cli batch config.toml --max-workers 4
    
    # Filter specific subject or session
    $ python -m w2t_bkin.cli batch config.toml --subject SNA-144233 --max-workers 2
    
    # Shell-based batch processing (GNU Parallel - for advanced users)
    $ python -m w2t_bkin.cli discover config.toml --format tsv | \
        parallel --bar --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
    
    # Validation and inspection
    $ python -m w2t_bkin.cli validate output/session-001/session-001.nwb
    $ python -m w2t_bkin.cli inspect output/session-001/session-001.nwb

See Also:
    - docs/batch-processing.md: Comprehensive batch processing guide
    - docs/quick-start-batch.md: Quick start guide for batch operations
    - w2t_bkin.utils.discover_sessions: Programmatic discovery API
    - w2t_bkin.prefect: Prefect orchestration module
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pynwb import NWBHDF5IO
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from .config import load_config
from .data_manager import (
    ExperimentConfig,
    SessionConfig,
    SubjectConfig,
    ValidationResult,
    add_session,
    add_subject,
    import_raw_data,
    init_experiment,
    validate_experiment_structure,
)
from .flows import batch_process_flow, process_session_flow

app = typer.Typer(
    name="w2t-bkin",
    help="W2T Body Kinematics Pipeline - Process behavioral and kinematic data into NWB format",
    add_completion=True,
)
console = Console()


@app.command()
def run(
    config_path: Path = typer.Argument(..., help="Path to config.toml file"),
    subject_id: str = typer.Argument(..., help="Subject identifier (e.g., 'subject-001')"),
    session_id: str = typer.Argument(..., help="Session identifier (e.g., 'session-001')"),
    skip_bpod: bool = typer.Option(False, "--skip-bpod", help="Skip Bpod processing"),
    skip_pose: bool = typer.Option(False, "--skip-pose", help="Skip pose estimation"),
    skip_ttl: bool = typer.Option(False, "--skip-ttl", help="Skip TTL processing"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip NWB validation"),
    no_verification: bool = typer.Option(False, "--no-verification", help="Disable all verification checks"),
    no_frame_count: bool = typer.Option(False, "--no-frame-count", help="Skip video frame counting (faster)"),
    no_sync_check: bool = typer.Option(False, "--no-sync-check", help="Skip frame/TTL synchronization check"),
    tolerance: Optional[int] = typer.Option(None, "--tolerance", help="Override verification tolerance (frames)"),
    warn_on_mismatch: Optional[bool] = typer.Option(None, "--warn-on-mismatch", help="Warn instead of fail on mismatch"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing outputs"),
    no_figures: bool = typer.Option(False, "--no-figures", help="Skip generating diagnostic figures"),
    video_frame_timeout: Optional[int] = typer.Option(None, "--video-timeout", help="Video frame counting timeout in seconds (overrides config)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
):
    """Run the pipeline for a single session.

    This command executes all 6 phases of the Prefect-native pipeline:
    1. Initialization - Load config and create NWBFile
    2. Discovery - Find and verify files
    3. Artifact Generation - Generate pose estimation (optional)
    4. Ingestion - Process Bpod, Pose, and TTL data
    5. Assembly - Build NWB behavior tables
    6. Finalization - Write and validate NWB file

    The pipeline uses Prefect for orchestration, providing automatic retry
    logic, parallel execution, and comprehensive error handling.

    Example:
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001 --skip-pose
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001 --skip-validation
    """
    # Set logging level
    logging.getLogger().setLevel(log_level.upper())

    if not config_path.exists():
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        raise typer.Exit(1)

    try:
        console.print("[cyan]Starting session processing...[/cyan]")
        console.print(f"  Config: [dim]{config_path}[/dim]")
        console.print(f"  Subject: [yellow]{subject_id}[/yellow]")
        console.print(f"  Session: [yellow]{session_id}[/yellow]")
        console.print()

        # Run flow
        result = process_session_flow(
            config_path=config_path,
            subject_id=subject_id,
            session_id=session_id,
            skip_bpod=skip_bpod,
            skip_pose=skip_pose,
            skip_nwb_validation=skip_validation,
        )

        if result.success:
            console.print(f"\n[green]✓ Success![/green] NWB file: {result.nwb_path}")
            console.print(f"  Duration: [dim]{result.duration_seconds:.2f}s[/dim]")

            if result.validation:
                critical = sum(1 for r in result.validation if r.get("severity") == "CRITICAL")
                errors = sum(1 for r in result.validation if r.get("severity") == "ERROR")
                warnings = sum(1 for r in result.validation if r.get("severity") == "WARNING")

                if critical > 0 or errors > 0:
                    console.print(f"[yellow]⚠ Validation issues: {critical} critical, {errors} errors, {warnings} warnings[/yellow]")
                else:
                    console.print(f"[green]✓ Validation passed ({warnings} warnings)[/green]")

            raise typer.Exit(0)
        else:
            console.print(f"\n[red]✗ Failed: {result.error}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logging.exception("Pipeline execution failed")
        raise typer.Exit(1)


@app.command()
def validate(
    nwb_path: Path = typer.Argument(..., help="Path to NWB file to validate"),
    show_warnings: bool = typer.Option(True, help="Show warnings in output"),
    output_json: Optional[Path] = typer.Option(None, "--output", help="Save results to JSON file"),
):
    """Validate an NWB file using nwbinspector.

    Runs comprehensive validation checks on an NWB file and reports
    any issues found (critical errors, errors, and warnings).

    Example:
        $ python -m w2t_bkin.cli validate output/session-001/session-001.nwb
        $ python -m w2t_bkin.cli validate file.nwb --output validation.json
    """
    if not nwb_path.exists():
        console.print(f"[red]Error: NWB file not found: {nwb_path}[/red]")
        raise typer.Exit(1)

    try:
        from nwbinspector import inspect_nwbfile

        console.print(f"Validating: [cyan]{nwb_path}[/cyan]")

        with console.status("[bold yellow]Running validation..."):
            results = list(inspect_nwbfile(nwbfile_path=str(nwb_path)))

        if not results:
            console.print("[green]✓ No issues found - file is valid![/green]")
            raise typer.Exit(0)

        # Categorize results
        critical = [r for r in results if r.severity.name == "CRITICAL"]
        errors = [r for r in results if r.severity.name == "ERROR"]
        warnings = [r for r in results if r.severity.name == "WARNING"]

        # Display summary
        table = Table(title="Validation Summary")
        table.add_column("Severity", style="bold")
        table.add_column("Count", justify="right")

        if critical:
            table.add_row("CRITICAL", str(len(critical)), style="red bold")
        if errors:
            table.add_row("ERROR", str(len(errors)), style="red")
        if warnings:
            table.add_row("WARNING", str(len(warnings)), style="yellow")

        console.print(table)

        # Display details
        if critical or errors or (warnings and show_warnings):
            console.print("\n[bold]Details:[/bold]")

            for result in critical + errors:
                console.print(f"\n[red]●[/red] [{result.severity.name}] {result.check_function_name}")
                console.print(f"  {result.message}")
                console.print(f"  Location: {result.location}")

            if show_warnings:
                for result in warnings:
                    console.print(f"\n[yellow]●[/yellow] [WARNING] {result.check_function_name}")
                    console.print(f"  {result.message}")

        # Save to JSON if requested
        if output_json:
            validation_data = [
                {
                    "severity": r.severity.name,
                    "check_name": r.check_function_name,
                    "message": r.message,
                    "object_type": r.object_type,
                    "object_name": r.object_name,
                    "location": r.location,
                }
                for r in results
            ]

            output_json.write_text(json.dumps(validation_data, indent=2))
            console.print(f"\n[dim]Results saved to: {output_json}[/dim]")

        # Exit with appropriate code
        if critical or errors:
            raise typer.Exit(1)
        else:
            raise typer.Exit(0)

    except ImportError:
        console.print("[red]Error: nwbinspector not installed[/red]")
        console.print("Install with: pip install nwbinspector")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error during validation: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def inspect(
    nwb_path: Path = typer.Argument(..., help="Path to NWB file to inspect"),
    show_acquisition: bool = typer.Option(True, help="Show acquisition data"),
    show_trials: bool = typer.Option(True, help="Show trials table"),
    show_devices: bool = typer.Option(True, help="Show devices"),
):
    """Inspect NWB file contents and metadata.

    Displays a summary of the NWB file structure including:
    - Session metadata (identifier, description, timestamps)
    - Subject information
    - Devices
    - Acquisition data (videos, TTL, etc.)
    - Processing modules
    - Trials table

    Example:
        $ python -m w2t_bkin.cli inspect output/session-001/session-001.nwb
    """
    if not nwb_path.exists():
        console.print(f"[red]Error: NWB file not found: {nwb_path}[/red]")
        raise typer.Exit(1)

    try:
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()

            # File info
            console.print(
                Panel.fit(
                    f"[bold cyan]NWB File Inspection[/bold cyan]\n" f"File: [yellow]{nwb_path.name}[/yellow]\n" f"Size: [dim]{nwb_path.stat().st_size / (1024*1024):.1f} MB[/dim]",
                    border_style="cyan",
                )
            )

            # Session metadata
            table = Table(title="Session Metadata", show_header=False)
            table.add_column("Property", style="bold")
            table.add_column("Value")

            table.add_row("Identifier", nwbfile.identifier)
            table.add_row("Session Description", nwbfile.session_description or "N/A")
            table.add_row("Session Start", str(nwbfile.session_start_time))
            table.add_row("Timestamps Reference", str(nwbfile.timestamps_reference_time))

            console.print(table)

            # Subject info
            if nwbfile.subject:
                table = Table(title="Subject", show_header=False)
                table.add_column("Property", style="bold")
                table.add_column("Value")

                table.add_row("Subject ID", nwbfile.subject.subject_id or "N/A")
                table.add_row("Species", nwbfile.subject.species or "N/A")
                table.add_row("Sex", nwbfile.subject.sex or "N/A")
                table.add_row("Age", nwbfile.subject.age or "N/A")

                console.print(table)

            # Devices
            if show_devices and nwbfile.devices:
                table = Table(title="Devices")
                table.add_column("Name", style="cyan")
                table.add_column("Description")

                for name, device in nwbfile.devices.items():
                    table.add_row(name, device.description or "N/A")

                console.print(table)

            # Acquisition
            if show_acquisition and nwbfile.acquisition:
                table = Table(title="Acquisition")
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="yellow")
                table.add_column("Details")

                for name, obj in nwbfile.acquisition.items():
                    obj_type = type(obj).__name__

                    details = ""
                    if hasattr(obj, "rate"):
                        details = f"Rate: {obj.rate} Hz"
                    elif hasattr(obj, "external_file"):
                        files = obj.external_file if isinstance(obj.external_file, list) else [obj.external_file]
                        details = f"{len(files)} file(s)"

                    table.add_row(name, obj_type, details)

                console.print(table)

            # Trials
            if show_trials and nwbfile.trials is not None:
                n_trials = len(nwbfile.trials)
                console.print(f"\n[bold]Trials Table:[/bold] {n_trials} trials")

                if n_trials > 0:
                    columns = list(nwbfile.trials.colnames)
                    console.print(f"Columns: {', '.join(columns[:10])}")
                    if len(columns) > 10:
                        console.print(f"  ... and {len(columns) - 10} more")

            # Processing modules
            if nwbfile.processing:
                console.print(f"\n[bold]Processing Modules:[/bold] {len(nwbfile.processing)}")
                for name in nwbfile.processing.keys():
                    console.print(f"  • {name}")

            # Lab metadata
            if nwbfile.lab_meta_data:
                console.print(f"\n[bold]Lab Metadata:[/bold] {len(nwbfile.lab_meta_data)} container(s)")
                for name in nwbfile.lab_meta_data.keys():
                    console.print(f"  • {name}")

        raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error reading NWB file: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def discover(
    config_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to configuration TOML file",
    ),
    subject_filter: Optional[str] = typer.Option(
        None,
        "--subject",
        "-s",
        help="Filter by specific subject ID",
    ),
    session_filter: Optional[str] = typer.Option(
        None,
        "--session",
        "-x",
        help="Filter by specific session ID",
    ),
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, tsv, or plain",
    ),
):
    """Discover all available subject/session combinations in the raw data directory.
    
    Scans the raw_root directory specified in the config file and outputs all
    valid subject/session combinations that can be processed by the pipeline.
    
    Examples:
        # List all sessions as JSON (default)
        python -m w2t_bkin.cli discover config.toml
        
        # List sessions as TSV for piping to parallel
        python -m w2t_bkin.cli discover config.toml --format tsv
        
        # Filter by subject
        python -m w2t_bkin.cli discover config.toml --subject subject-001
        
        # Process all sessions in parallel (GNU Parallel)
        python -m w2t_bkin.cli discover config.toml --format tsv | \\
            parallel --col-sep '\\t' python -m w2t_bkin.cli run config.toml {1} {2}
    """
    import json as json_module

    from w2t_bkin.utils import discover_sessions

    try:
        # Use programmatic API
        discoveries = discover_sessions(
            config_path=config_path,
            subject_filter=subject_filter,
            session_filter=session_filter,
        )

        # Output results
        if not discoveries:
            if subject_filter or session_filter:
                console.print("[yellow]No matching sessions found with the specified filters[/yellow]")
            else:
                console.print("[yellow]No sessions found in raw_root[/yellow]")
            raise typer.Exit(0)

        if output_format == "json":
            # JSON format (for programmatic use)
            output = json_module.dumps(discoveries, indent=2)
            console.print(output)

        elif output_format == "tsv":
            # TSV format (for piping to parallel)
            for item in discoveries:
                console.print(f"{item['subject']}\t{item['session']}")

        elif output_format == "plain":
            # Human-readable format
            console.print(f"[bold]Found {len(discoveries)} session(s):[/bold]\n")
            for item in discoveries:
                console.print(f"  {item['subject']:20s} / {item['session']:30s} ({item['metadata_file']})")

        else:
            console.print(f"[bold red]Error:[/bold red] Unknown format '{output_format}'. Use json, tsv, or plain.")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[bold red]Error during discovery:[/bold red] {e}")
        logging.exception("Discovery failed")
        raise typer.Exit(1)


@app.command()
def batch(
    config_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to configuration TOML file",
    ),
    subject_filter: Optional[str] = typer.Option(
        None,
        "--subject",
        "-s",
        help="Filter by specific subject ID",
    ),
    session_filter: Optional[str] = typer.Option(
        None,
        "--session",
        "-x",
        help="Filter by specific session ID",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        "-j",
        help="Maximum concurrent sessions (default: 4)",
    ),
):
    """Process multiple sessions in parallel using Prefect flows.

    This command uses the new Prefect-native batch_process_flow for parallel
    execution with automatic retries, graceful error handling, and progress tracking.

    Examples:
        # Process all sessions with 3 parallel workers
        python -m w2t_bkin.cli batch config.toml --max-workers 3

        # Process specific subject
        python -m w2t_bkin.cli batch config.toml --subject subject-001

        # Process with 8 workers (adjust based on CPU cores)
        python -m w2t_bkin.cli batch config.toml --max-workers 8

    Features:
        - Prefect-native orchestration with automatic retries
        - Parallel execution with configurable concurrency
        - Graceful error handling (continues on partial failures)
        - Comprehensive logging and error tracking
        - Resource management via max_workers

    See Also:
        - discover: Find available sessions
        - run: Process single session
        - docs/batch-processing.md: Full batch processing guide
    """
    try:
        console.print("[cyan]╭─────────────────────────────────────────────╮[/cyan]")
        console.print("[cyan]│  Batch Processing (Prefect)                 │[/cyan]")
        console.print("[cyan]╰─────────────────────────────────────────────╯[/cyan]")
        console.print()
        console.print(f"  Config: [dim]{config_path}[/dim]")
        console.print(f"  Max workers: [yellow]{max_workers}[/yellow]")
        if subject_filter:
            console.print(f"  Subject filter: [yellow]{subject_filter}[/yellow]")
        if session_filter:
            console.print(f"  Session filter: [yellow]{session_filter}[/yellow]")
        console.print()

        # Run batch processing using new flow
        result = batch_process_flow(
            config_path=config_path,
            subject_filter=subject_filter,
            session_filter=session_filter,
            max_parallel=max_workers,
            skip_bpod=False,
            skip_pose=False,
            skip_nwb_validation=False,
        )

        # Display results
        console.print()
        console.print("[cyan]╭─────────────────────────────────────────────╮[/cyan]")
        console.print("[cyan]│  Batch Processing Complete                  │[/cyan]")
        console.print("[cyan]╰─────────────────────────────────────────────╯[/cyan]")
        console.print()
        console.print(f"  Total sessions: [bold]{result.total}[/bold]")
        console.print(f"  Successful: [bold green]{result.successful}[/bold green]")
        console.print(f"  Failed: [bold {'red' if result.failed > 0 else 'dim'}]{result.failed}[/bold {'red' if result.failed > 0 else 'dim'}]")

        if result.failed > 0:
            console.print()
            console.print("[yellow]Failed sessions:[/yellow]")
            for r in result.session_results:
                if not r.success:
                    console.print(f"  [red]✗[/red] {r.subject_id:15s} / {r.session_id:30s}")
                    if r.error:
                        console.print(f"    [dim]{r.error}[/dim]")
            console.print()
            console.print("[yellow]💡 Check logs for detailed error information[/yellow]")
            raise typer.Exit(1)

        console.print()
        console.print("[bold green]✓ All sessions processed successfully![/bold green]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print()
        console.print(f"[bold red]Batch processing failed:[/bold red] {e}")
        logging.exception("Batch processing error")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    try:
        from . import __version__

        version_str = __version__
    except ImportError:
        version_str = "unknown"

    console.print(f"[bold cyan]W2T Body Kinematics Pipeline[/bold cyan]")
    console.print(f"Version: {version_str}")
    console.print(f"Python NWB: pynwb")
    console.print(f"CLI: typer + rich")


# =============================================================================
# Container Commands
# =============================================================================

container_app = typer.Typer(
    name="container",
    help="Container orchestration commands for containerized deployment",
)
app.add_typer(container_app, name="container")


@container_app.command(name="start-server")
def container_start_server(
    port: int = typer.Option(4200, "--port", "-p", help="Prefect UI port"),
    detach: bool = typer.Option(True, "--detach/--follow", "-d", help="Run in background"),
):
    """Start Prefect server and database.

    This starts the orchestration server with a web UI for monitoring pipeline runs.
    The server will be available at http://localhost:<port> (default: 4200).

    Example:
        $ w2t-bkin container start-server
        $ w2t-bkin container start-server --port 4201
        $ w2t-bkin container start-server --follow  # Watch logs in foreground
    """
    try:
        from .container import detect_runtime, start_server
    except ImportError:
        console.print("[red]❌ Container module not available[/red]")
        console.print("Install with: pip install w2t-bkin[prefect]")
        raise typer.Exit(1)

    runtime = detect_runtime()

    # Import moved inside function to avoid import errors
    from .container.runtime import ContainerRuntime

    if runtime == ContainerRuntime.NONE:
        console.print("[red]❌ No container runtime detected.[/red]")
        console.print("\n[yellow]Please install one of the following:[/yellow]")
        console.print("  • [cyan]Podman Desktop[/cyan] (recommended): https://podman-desktop.io/")
        console.print("  • [cyan]Docker[/cyan]: https://docs.docker.com/get-docker/")
        console.print("  • [cyan]Apptainer[/cyan]: https://apptainer.org/")
        raise typer.Exit(1)

    start_server(runtime, port=port, detach=detach)


@container_app.command(name="start-worker")
def container_start_worker(
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker instances"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.toml"),
):
    """Start worker container(s) to execute pipeline tasks.

    Workers connect to the Prefect server and execute pipeline runs in parallel.
    Start as many workers as you have CPU cores available.

    Example:
        $ w2t-bkin container start-worker --workers 4
        $ w2t-bkin container start-worker -w 2 --config ./configs/config.toml
    """
    try:
        from .container import detect_runtime, start_workers
    except ImportError:
        console.print("[red]❌ Container module not available[/red]")
        raise typer.Exit(1)

    runtime = detect_runtime()

    from .container.runtime import ContainerRuntime

    if runtime == ContainerRuntime.NONE:
        console.print("[red]❌ No container runtime detected.[/red]")
        raise typer.Exit(1)

    config_str = str(config) if config else None
    start_workers(runtime, count=workers, config_path=config_str)


@container_app.command(name="stop")
def container_stop():
    """Stop all w2t-bkin containers.

    This stops the server, workers, and database containers.

    Example:
        $ w2t-bkin container stop
    """
    try:
        from .container import detect_runtime, stop_all
    except ImportError:
        console.print("[red]❌ Container module not available[/red]")
        raise typer.Exit(1)

    runtime = detect_runtime()

    from .container.runtime import ContainerRuntime

    if runtime == ContainerRuntime.NONE:
        console.print("[red]❌ No container runtime detected.[/red]")
        raise typer.Exit(1)

    stop_all(runtime)


@container_app.command(name="status")
def container_status():
    """Show status of all w2t-bkin containers.

    Displays which containers are running and their current state.

    Example:
        $ w2t-bkin container status
    """
    try:
        from .container import detect_runtime, show_status
    except ImportError:
        console.print("[red]❌ Container module not available[/red]")
        raise typer.Exit(1)

    runtime = detect_runtime()

    from .container.runtime import ContainerRuntime

    if runtime == ContainerRuntime.NONE:
        console.print("[red]❌ No container runtime detected.[/red]")
        raise typer.Exit(1)

    show_status(runtime)


@container_app.command(name="logs")
def container_logs(
    service: str = typer.Argument("server", help="Service name (server, worker, postgres)"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: Optional[int] = typer.Option(None, "--tail", "-n", help="Number of lines to show"),
):
    """Show logs for a container service.

    Example:
        $ w2t-bkin container logs server
        $ w2t-bkin container logs worker --follow
        $ w2t-bkin container logs postgres --tail 100
    """
    try:
        from .container import detect_runtime
        from .container.orchestrator import logs
    except ImportError:
        console.print("[red]❌ Container module not available[/red]")
        raise typer.Exit(1)

    runtime = detect_runtime()

    from .container.runtime import ContainerRuntime

    if runtime == ContainerRuntime.NONE:
        console.print("[red]❌ No container runtime detected.[/red]")
        raise typer.Exit(1)

    logs(runtime, service=service, follow=follow, tail=tail)


# =============================================================================
# Data Management Commands
# =============================================================================

data_app = typer.Typer(
    name="data",
    help="Data management commands for experiment setup and organization",
)
app.add_typer(data_app, name="data")


@data_app.command(name="init")
def data_init(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    lab: Optional[str] = typer.Option(None, "--lab", help="Lab name"),
    institution: Optional[str] = typer.Option(None, "--institution", help="Institution name"),
    experimenters: Optional[str] = typer.Option(None, "--experimenters", help="Comma-separated experimenter names"),
    protocol: Optional[str] = typer.Option(None, "--protocol", help="Protocol ID (e.g., IACUC number)"),
    description: Optional[str] = typer.Option(None, "--description", help="Experiment description"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Initialize a new experiment folder structure.

    Creates the standard directory layout:
    - raw/          (raw data storage)
    - interim/      (intermediate processing artifacts)
    - processed/    (final outputs)
    - models/       (trained models)

    Also creates:
    - raw/metadata.toml  (NWB metadata)
    - config.toml        (pipeline configuration)

    Example:
        $ w2t-bkin data init /data/my-experiment \\
            --lab "Larkum Lab" \\
            --institution "Humboldt University" \\
            --experimenters "Alice,Bob"

        $ w2t-bkin data init /data/my-experiment -y  # Skip prompts
    """
    # Interactive mode if parameters not provided
    if not lab:
        lab = typer.prompt("Lab name")
    if not institution:
        institution = typer.prompt("Institution name")
    if not experimenters:
        experimenters = typer.prompt("Experimenter names (comma-separated)")

    experimenter_list = [e.strip() for e in experimenters.split(",")]

    success = init_experiment(
        root_path=experiment_root,
        lab=lab,
        institution=institution,
        experimenters=experimenter_list,
        protocol=protocol,
        experiment_description=description,
        interactive=not yes,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="add-subject")
def data_add_subject(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject_id: str = typer.Argument(..., help="Subject identifier (e.g., 'subject-001')"),
    species: str = typer.Option("Mus musculus", "--species", help="Species name"),
    sex: str = typer.Option("U", "--sex", help="Sex (F|M|U|O)"),
    age: Optional[str] = typer.Option(None, "--age", help="Age in ISO 8601 duration (e.g., P84D)"),
    genotype: Optional[str] = typer.Option(None, "--genotype", help="Genotype"),
    strain: Optional[str] = typer.Option(None, "--strain", help="Strain"),
    date_of_birth: Optional[str] = typer.Option(None, "--date-of-birth", help="Date of birth (ISO 8601)"),
    weight: Optional[str] = typer.Option(None, "--weight", help="Weight"),
    description: Optional[str] = typer.Option(None, "--description", help="Subject description"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Add a new subject to the experiment.

    Creates:
    - raw/{subject_id}/
    - raw/{subject_id}/subject.toml

    Example:
        $ w2t-bkin data add-subject /data/my-experiment subject-001 \\
            --species "Mus musculus" \\
            --sex M \\
            --age P84D

        $ w2t-bkin data add-subject /data/my-experiment subject-002 -y
    """
    subject_config = SubjectConfig(
        subject_id=subject_id,
        species=species,
        sex=sex,
        age=age,
        genotype=genotype,
        strain=strain,
        date_of_birth=date_of_birth,
        weight=weight,
        description=description,
    )

    success = add_subject(
        experiment_root=experiment_root,
        subject_config=subject_config,
        interactive=not yes,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="add-session")
def data_add_session(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject_id: str = typer.Argument(..., help="Subject identifier"),
    session_id: str = typer.Argument(..., help="Session identifier (e.g., 'session-001')"),
    date: Optional[str] = typer.Option(None, "--date", help="Session date (ISO 8601, e.g., 2024-01-15)"),
    description: Optional[str] = typer.Option(None, "--description", help="Session description"),
    experimenter: Optional[str] = typer.Option(None, "--experimenter", help="Experimenter name"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Session start time (ISO 8601)"),
    no_subdirs: bool = typer.Option(False, "--no-subdirs", help="Don't create Video/TTLs/Bpod folders"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Add a new session for a subject.

    Creates:
    - raw/{subject_id}/{session_id}/
    - raw/{subject_id}/{session_id}/session.toml
    - raw/{subject_id}/{session_id}/Video/  (optional)
    - raw/{subject_id}/{session_id}/TTLs/   (optional)
    - raw/{subject_id}/{session_id}/Bpod/   (optional)

    Example:
        $ w2t-bkin data add-session /data/my-experiment subject-001 session-001 \\
            --date 2024-01-15 \\
            --description "Baseline recording" \\
            --experimenter "Alice"

        $ w2t-bkin data add-session /data/my-experiment subject-001 session-002 -y
    """
    # Interactive mode
    if not date:
        from datetime import date as date_cls

        date = str(date_cls.today())
    if not description:
        description = typer.prompt("Session description", default="Behavioral session")
    if not experimenter:
        experimenter = typer.prompt("Experimenter name")

    session_config = SessionConfig(
        session_id=session_id,
        session_date=date,
        session_description=description,
        experimenter=experimenter,
        session_start_time=start_time,
    )

    success = add_session(
        experiment_root=experiment_root,
        subject_id=subject_id,
        session_config=session_config,
        create_subdirs=not no_subdirs,
        interactive=not yes,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="import-raw")
def data_import_raw(
    source: Path = typer.Argument(..., help="Source directory containing raw data"),
    experiment_root: Path = typer.Option(..., "--experiment", "-e", help="Experiment root directory"),
    subject_id: str = typer.Option(..., "--subject", "-s", help="Target subject ID"),
    session_id: str = typer.Option(..., "--session", help="Target session ID"),
    no_detect: bool = typer.Option(False, "--no-detect", help="Skip automatic file pattern detection"),
    confirm: bool = typer.Option(False, "--confirm", help="Execute import (required for actual operation)"),
):
    """Import existing raw data using symbolic links (SAFE - preserves originals).

    This command NEVER moves or deletes original data. It creates symbolic links
    in the target session directory that point to your original files.

    Process:
    1. Scans source directory for recognizable files (videos, TTLs, Bpod .mat)
    2. Auto-detects file patterns and camera/TTL IDs
    3. Shows preview of what will be imported
    4. Creates symbolic links in target session (only if --confirm)

    Dry-run by default:
    - Without --confirm: Shows preview only (safe)
    - With --confirm: Creates symbolic links

    Example:
        # Preview import (dry-run)
        $ w2t-bkin data import-raw /raw-data/2024-01-15 \\
            --experiment /data/my-experiment \\
            --subject subject-001 \\
            --session session-001

        # Execute import (creates symlinks)
        $ w2t-bkin data import-raw /raw-data/2024-01-15 \\
            --experiment /data/my-experiment \\
            --subject subject-001 \\
            --session session-001 \\
            --confirm

    Safety features:
    - Uses symbolic links (preserves originals)
    - Dry-run by default
    - Explicit --confirm required for execution
    - Auto-updates session.toml with detected cameras/TTLs
    """
    success = import_raw_data(
        source_dir=source,
        experiment_root=experiment_root,
        subject_id=subject_id,
        session_id=session_id,
        auto_detect=not no_detect,
        dry_run=not confirm,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="validate")
def data_validate(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject ID"),
    session: Optional[str] = typer.Option(None, "--session", help="Filter by session ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed validation info"),
):
    """Validate experiment folder structure and metadata.

    Checks:
    - Required folders exist (raw/, interim/, processed/)
    - Root metadata.toml is valid
    - Subject folders have subject.toml
    - Session folders have session.toml with required fields
    - Camera/TTL file patterns match actual files
    - TOML syntax is correct

    Example:
        # Validate entire experiment
        $ w2t-bkin data validate /data/my-experiment

        # Validate specific subject
        $ w2t-bkin data validate /data/my-experiment --subject subject-001

        # Validate specific session
        $ w2t-bkin data validate /data/my-experiment \\
            --subject subject-001 \\
            --session session-001 \\
            --verbose
    """
    result: ValidationResult = validate_experiment_structure(
        experiment_root=experiment_root,
        subject_filter=subject,
        session_filter=session,
        verbose=verbose,
    )

    # Display results
    console.print(f"\n[bold]Validation Results[/bold]")
    console.print(f"Experiment: [cyan]{experiment_root}[/cyan]\n")

    if result.errors:
        console.print(f"[red]✗ {len(result.errors)} Error(s):[/red]")
        for error in result.errors:
            console.print(f"  • {error}")
        console.print()

    if result.warnings:
        console.print(f"[yellow]⚠ {len(result.warnings)} Warning(s):[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")
        console.print()

    if verbose and result.info:
        console.print(f"[dim]ℹ Info:[/dim]")
        for info in result.info:
            console.print(f"  {info}")
        console.print()

    if result.valid:
        console.print(f"[bold green]✓ Validation passed![/bold green]")
        if result.warnings:
            console.print(f"  ({len(result.warnings)} warning(s) - review recommended)")
    else:
        console.print(f"[bold red]✗ Validation failed ({len(result.errors)} error(s))[/bold red]")
        raise typer.Exit(1)


@data_app.command(name="generate-env")
def data_generate_env(
    output: Path = typer.Option(".env", "--output", "-o", help="Output file path (default: .env)"),
    data_root: Path = typer.Option("./data", "--data-root", help="Path to data directory"),
    models_root: Path = typer.Option("./models", "--models-root", help="Path to models directory"),
    config_root: Path = typer.Option("./configs", "--config-root", help="Path to configs directory"),
    max_workers: int = typer.Option(4, "--max-workers", help="Default number of parallel workers"),
    worker_replicas: int = typer.Option(1, "--worker-replicas", help="Number of worker containers"),
    prefect_port: int = typer.Option(4200, "--prefect-port", help="Prefect UI port"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing .env file"),
):
    """Generate .env file for Docker Compose deployment.

    Creates a .env file with all necessary configuration for running
    w2t-bkin in Docker containers with Prefect orchestration.

    The generated file includes:
    - Prefect server configuration (UI port, logging)
    - PostgreSQL database settings
    - Worker configuration (replicas, resources)
    - Deployment defaults (config file, max workers)
    - Data paths (mounted volumes)

    Example:
        # Generate with defaults
        $ w2t-bkin data generate-env

        # Customize paths
        $ w2t-bkin data generate-env \\
            --data-root /mnt/data \\
            --models-root /mnt/models \\
            --max-workers 8

        # Generate to custom location
        $ w2t-bkin data generate-env --output docker/.env

        # Overwrite existing
        $ w2t-bkin data generate-env --force
    """
    # Check if file exists
    if output.exists() and not force:
        console.print(f"[yellow]Warning: {output} already exists[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    # Generate .env content
    env_content = f"""# Docker Compose Environment Variables
# Generated by w2t-bkin data generate-env command
# Edit as needed for your deployment

# =============================================================================
# Prefect Server Configuration
# =============================================================================
PREFECT_UI_PORT={prefect_port}
PREFECT_LOGGING_LEVEL=INFO

# =============================================================================
# Database Configuration
# =============================================================================
POSTGRES_USER=prefect
POSTGRES_PASSWORD=prefect
POSTGRES_DB=prefect

# =============================================================================
# Worker Configuration
# =============================================================================
WORK_POOL=docker-pool
WORKER_REPLICAS={worker_replicas}

# Worker resource limits (adjust based on your system)
WORKER_CPU_LIMIT=4
WORKER_MEMORY_LIMIT=8G
WORKER_CPU_RESERVATION=1
WORKER_MEMORY_RESERVATION=2G

# =============================================================================
# Deployment Defaults
# =============================================================================

# Default configuration file for deployments (must use absolute container paths)
DEFAULT_CONFIG_FILE=container.toml

# Default number of parallel sessions to process
DEFAULT_MAX_WORKERS={max_workers}

# Optional filters for batch processing
DEFAULT_SUBJECT_FILTER=
DEFAULT_SESSION_FILTER=

# =============================================================================
# Data Paths (adjust to your local directories)
# =============================================================================

# Root directory for raw data (READ-ONLY)
DATA_ROOT={data_root}

# Root directory for pose estimation models (READ-ONLY)
MODELS_ROOT={models_root}

# Root directory for configuration files (READ-ONLY)
CONFIG_ROOT={config_root}

# Intermediate processing outputs (READ-WRITE)
INTERIM_ROOT={data_root}/interim

# Final processed outputs (READ-WRITE)
OUTPUT_ROOT={data_root}/processed

# =============================================================================
# Notes
# =============================================================================
#
# Windows (WSL2):
#   Use WSL paths: /mnt/c/Users/YourName/data
#   Not Windows paths: C:\\Users\\YourName\\data
#
# macOS/Linux:
#   Use absolute paths: /Users/yourname/data or /home/yourname/data
#   Or relative paths: ./data (relative to docker-compose.yml location)
#
# Permissions:
#   Ensure your user has read/write access to mounted directories
#   Container runs as uid 1000 (user 'w2t')
#
# Resource Limits:
#   Adjust WORKER_CPU_LIMIT and WORKER_MEMORY_LIMIT based on available resources
#   Run 'docker stats' or 'podman stats' to monitor resource usage
#
# Deployment Flow Names (v0.0.10):
#   - process-session-flow/process-session (single session)
#   - batch-process-flow/batch-processing (parallel batch)
"""

    # Write file
    output.write_text(env_content)

    console.print(f"[green]✓ Generated {output}[/green]")
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Data root: [cyan]{data_root}[/cyan]")
    console.print(f"  Models root: [cyan]{models_root}[/cyan]")
    console.print(f"  Config root: [cyan]{config_root}[/cyan]")
    console.print(f"  Max workers: [yellow]{max_workers}[/yellow]")
    console.print(f"  Worker replicas: [yellow]{worker_replicas}[/yellow]")
    console.print(f"  Prefect UI: [cyan]http://localhost:{prefect_port}[/cyan]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Review and edit [cyan].env[/cyan] if needed")
    console.print("  2. Start services: [yellow]docker compose up -d[/yellow]")
    console.print(f"  3. Access Prefect UI: [cyan]http://localhost:{prefect_port}[/cyan]")


if __name__ == "__main__":
    app()
