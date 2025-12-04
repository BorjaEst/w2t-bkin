"""Command-line interface for W2T Body Kinematics Pipeline.

This module provides a Typer-based CLI with commands for running the pipeline,
validating NWB files, and inspecting session outputs.

Commands:
    run: Execute pipeline for a session
    validate: Validate an existing NWB file
    inspect: Display NWB file contents and metadata

Example:
    $ python -m w2t_bkin.cli run config.toml subject-001 session-001
    $ python -m w2t_bkin.cli validate output/session-001/session-001.nwb
    $ python -m w2t_bkin.cli inspect output/session-001/session-001.nwb
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
from .core.pipeline import RunOptions, SessionPipeline

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
    skip_verification: bool = typer.Option(False, "--skip-verification", help="Skip frame/TTL verification"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip NWB validation"),
    tolerance: Optional[int] = typer.Option(None, "--tolerance", help="Override verification tolerance (frames)"),
    warn_on_mismatch: Optional[bool] = typer.Option(None, "--warn-on-mismatch", help="Warn instead of fail on mismatch"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing outputs"),
    no_figures: bool = typer.Option(False, "--no-figures", help="Skip generating diagnostic figures"),
    video_frame_timeout: Optional[int] = typer.Option(None, "--video-timeout", help="Video frame counting timeout in seconds (overrides config)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
):
    """Run the pipeline for a single session.

    This command executes all 7 phases of the pipeline:
    0. Initialization - Load config and create NWBFile
    1. Discovery - Find and verify files
    2. Preprocessing - Generate intermediate artifacts
    3. Ingestion - Process Bpod, Pose, and TTL data
    4. Synchronization - Compute alignment statistics
    5. Assembly - Build NWB behavior tables
    6. Finalization - Write, validate, and create sidecars

    By default, diagnostic figures are generated showing pipeline execution
    timing and synchronization quality metrics. Use --no-figures to skip.

    Example:
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001 --skip-validation
        $ python -m w2t_bkin.cli run config.toml subject-001 session-001 --no-figures
    """
    # Set logging level
    logging.getLogger().setLevel(log_level.upper())

    if not config_path.exists():
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        raise typer.Exit(1)

    # Load config to get default timeout value
    config = load_config(config_path)

    # Use CLI timeout if provided, otherwise use config value
    timeout = video_frame_timeout if video_frame_timeout is not None else config.video.analysis.frame_count_timeout

    options = RunOptions(
        skip_bpod=skip_bpod,
        skip_pose=skip_pose,
        skip_ttl=skip_ttl,
        skip_verification=skip_verification,
        skip_nwb_validation=skip_validation,
        force_overwrite=force,
        generate_figures=not no_figures,
        verification_tolerance=tolerance,
        warn_on_mismatch=warn_on_mismatch,
        video_frame_timeout=timeout,
    )

    pipeline = SessionPipeline(config_path, subject_id, session_id, options)
    result = pipeline.run()

    if result.success:
        console.print(f"\n[green]✓ Success![/green] NWB file: {result.nwb_path}")

        if result.validation_results:
            critical = sum(1 for r in result.validation_results if r.get("severity") == "CRITICAL")
            errors = sum(1 for r in result.validation_results if r.get("severity") == "ERROR")
            warnings = sum(1 for r in result.validation_results if r.get("severity") == "WARNING")

            if critical > 0 or errors > 0:
                console.print(f"[yellow]⚠ Validation issues: {critical} critical, {errors} errors, {warnings} warnings[/yellow]")
            else:
                console.print(f"[green]✓ Validation passed ({warnings} warnings)[/green]")

        raise typer.Exit(0)
    else:
        console.print(f"\n[red]✗ Failed: {result.error}[/red]")
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


if __name__ == "__main__":
    app()
