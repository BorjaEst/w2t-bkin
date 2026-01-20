"""Shared CLI utilities for formatting and display."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def setup_logging(level: str) -> None:
    """Configure logging for CLI.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def display_session_result(result) -> None:
    """Display session processing result.

    Args:
        result: SessionResult from process_session_flow
    """
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
    else:
        console.print(f"\n[red]✗ Failed: {result.error}[/red]")


def display_batch_result(result) -> None:
    """Display batch processing results.

    Args:
        result: BatchResult from batch_process_flow
    """
    table = Table(title="Batch Processing Results")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Total", str(result.total))
    table.add_row("Successful", str(result.successful), style="green")
    table.add_row("Failed", str(result.failed), style="red")
    table.add_row("Skipped", str(result.skipped), style="dim")

    console.print(table)

    if result.errors:
        console.print("\n[bold red]Failed Sessions:[/bold red]")
        for session_key, error in result.errors.items():
            console.print(f"  • {session_key}: {error}")


def format_discoveries(sessions: List[Dict[str, Any]], output_format: str) -> str:
    """Format session discoveries as JSON/TSV/plain.

    Args:
        sessions: List of session dictionaries
        output_format: Output format (json, tsv, plain)

    Returns:
        Formatted string
    """
    if output_format == "json":
        return json.dumps(sessions, indent=2)
    elif output_format == "tsv":
        return "\n".join(f"{s['subject']}\t{s['session']}" for s in sessions)
    else:  # plain
        table = Table(title=f"Found {len(sessions)} session(s)")
        table.add_column("Subject", style="cyan")
        table.add_column("Session", style="yellow")
        table.add_column("Metadata", style="dim")

        for session in sessions:
            table.add_row(
                session["subject"],
                session["session"],
                session["metadata_file"],
            )

        # Render to string
        from io import StringIO

        string_io = StringIO()
        temp_console = Console(file=string_io, force_terminal=True)
        temp_console.print(table)
        return string_io.getvalue()


def display_validation_results(results: list, show_warnings: bool) -> None:
    """Display NWB validation results.

    Args:
        results: List of validation results from nwbinspector
        show_warnings: Whether to show warnings
    """
    if not results:
        console.print("[green]✓ No issues found - file is valid![/green]")
        return

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


def display_nwb_structure(nwbfile, show_acquisition: bool, show_trials: bool, show_devices: bool) -> None:
    """Display NWB file structure.

    Args:
        nwbfile: Opened NWBFile object
        show_acquisition: Whether to show acquisition data
        show_trials: Whether to show trials table
        show_devices: Whether to show devices
    """
    # File info
    console.print(
        Panel.fit(
            f"[bold cyan]NWB File Inspection[/bold cyan]\n" f"Identifier: [yellow]{nwbfile.identifier}[/yellow]\n" f"Session: [dim]{nwbfile.session_description}[/dim]",
            border_style="cyan",
        )
    )

    # Session metadata
    meta_table = Table(title="Session Metadata", show_header=False)
    meta_table.add_column("Field", style="bold")
    meta_table.add_column("Value")

    meta_table.add_row("Start Time", str(nwbfile.session_start_time))
    if nwbfile.timestamps_reference_time:
        meta_table.add_row("Reference Time", str(nwbfile.timestamps_reference_time))
    if nwbfile.experimenter:
        meta_table.add_row("Experimenter", ", ".join(nwbfile.experimenter))
    if nwbfile.lab:
        meta_table.add_row("Lab", nwbfile.lab)
    if nwbfile.institution:
        meta_table.add_row("Institution", nwbfile.institution)

    console.print(meta_table)

    # Subject
    if nwbfile.subject:
        subject_table = Table(title="Subject", show_header=False)
        subject_table.add_column("Field", style="bold")
        subject_table.add_column("Value")

        subject_table.add_row("ID", nwbfile.subject.subject_id)
        if nwbfile.subject.species:
            subject_table.add_row("Species", nwbfile.subject.species)
        if nwbfile.subject.sex:
            subject_table.add_row("Sex", nwbfile.subject.sex)
        if nwbfile.subject.age:
            subject_table.add_row("Age", nwbfile.subject.age)

        console.print(subject_table)

    # Devices
    if show_devices and nwbfile.devices:
        devices_table = Table(title="Devices")
        devices_table.add_column("Name", style="cyan")
        devices_table.add_column("Description")

        for name, device in nwbfile.devices.items():
            devices_table.add_row(name, device.description or "")

        console.print(devices_table)

    # Acquisition
    if show_acquisition and nwbfile.acquisition:
        acq_table = Table(title="Acquisition Data")
        acq_table.add_column("Name", style="yellow")
        acq_table.add_column("Type", style="dim")

        for name, obj in nwbfile.acquisition.items():
            acq_table.add_row(name, type(obj).__name__)

        console.print(acq_table)

    # Processing modules
    if nwbfile.processing:
        proc_table = Table(title="Processing Modules")
        proc_table.add_column("Module", style="green")
        proc_table.add_column("Containers", style="dim")

        for name, module in nwbfile.processing.items():
            containers = ", ".join(module.data_interfaces.keys())
            proc_table.add_row(name, containers)

        console.print(proc_table)

    # Trials
    if show_trials and nwbfile.trials is not None:
        console.print(f"\n[bold]Trials:[/bold] {len(nwbfile.trials)} trials")
        console.print(f"Columns: {', '.join(nwbfile.trials.colnames)}")


def _load_template(template_name: str) -> str:
    """Load template file from package templates directory.

    All templates are stored in src/w2t_bkin/templates/ as the single source of truth.
    Script templates are in scripts/ subdirectory.

    Args:
        template_name: Name of template file (e.g., ".env.template" or "scripts/start-server.sh.template")

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template not found
    """
    import w2t_bkin

    template_dir = Path(w2t_bkin.__file__).parent / "templates"
    template_path = template_dir / template_name

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name} " f"(expected at {template_path})")

    return template_path.read_text()


def generate_env_dev_content(project_root: Path) -> str:
    """Generate .env.dev content with absolute paths for development mode.

    This file is auto-managed and should never be manually edited.
    It will be regenerated on every 'server start --dev' or 'worker start --type process'.

    Args:
        project_root: Absolute path to experiment/project root

    Returns:
        Content for .workers/.env.dev file
    """
    project_root = project_root.resolve()  # Ensure absolute

    content = [
        "# =============================================================================",
        "# W2T-BKIN Development Environment (AUTO-GENERATED)",
        "# =============================================================================",
        "# THIS FILE IS AUTO-MANAGED - DO NOT EDIT",
        "#",
        "# This file is automatically regenerated on every:",
        "#   - w2t-bkin server start --dev",
        "#   - w2t-bkin worker start --type process",
        "#",
        "# Any manual edits will be overwritten to ensure correct absolute paths.",
        "# For production Docker settings, edit .workers/.env instead.",
        "# =============================================================================",
        "",
        "# Development mode paths (host absolute)",
        f"W2T_RAW_ROOT={project_root / 'data' / 'raw'}",
        f"W2T_INTERMEDIATE_ROOT={project_root / 'data' / 'interim'}",
        f"W2T_OUTPUT_ROOT={project_root / 'data' / 'processed'}",
        f"W2T_MODELS_ROOT={project_root / 'models'}",
        "",
        "# Optional: Root metadata path",
        f"# W2T_ROOT_METADATA={project_root / 'data' / 'raw' / 'metadata.toml'}",
        "",
    ]

    return "\n".join(content)
