"""NWB file validation and inspection commands."""

import json
from pathlib import Path
from typing import Optional

from pynwb import NWBHDF5IO
import typer

from w2t_bkin.cli.utils import console, display_nwb_structure, display_validation_results


def validate(
    nwb_path: Path = typer.Argument(..., help="Path to NWB file to validate"),
    show_warnings: bool = typer.Option(True, help="Show warnings in output"),
    output_json: Optional[Path] = typer.Option(None, "--output", help="Save results to JSON file"),
):
    """Validate an NWB file using nwbinspector.

    Runs comprehensive validation checks on an NWB file and reports
    any issues found (critical errors, errors, and warnings).

    Example:
        $ w2t-bkin validate data/processed/subject-001/session-001.nwb
        $ w2t-bkin validate file.nwb --output validation.json
        $ w2t-bkin validate file.nwb --no-show-warnings
    """
    if not nwb_path.exists():
        console.print(f"[red]Error: NWB file not found: {nwb_path}[/red]")
        raise typer.Exit(1)

    try:
        from nwbinspector import inspect_nwbfile

        console.print(f"Validating: [cyan]{nwb_path}[/cyan]")

        with console.status("[bold yellow]Running validation..."):
            results = list(inspect_nwbfile(nwbfile_path=str(nwb_path)))

        display_validation_results(results, show_warnings)

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
        critical = [r for r in results if r.severity.name == "CRITICAL"]
        errors = [r for r in results if r.severity.name == "ERROR"]

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
        $ w2t-bkin inspect data/processed/subject-001/session-001.nwb
        $ w2t-bkin inspect file.nwb --no-show-acquisition
        $ w2t-bkin inspect file.nwb --no-show-trials
    """
    if not nwb_path.exists():
        console.print(f"[red]Error: NWB file not found: {nwb_path}[/red]")
        raise typer.Exit(1)

    try:
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            display_nwb_structure(nwbfile, show_acquisition, show_trials, show_devices)

    except Exception as e:
        console.print(f"[red]Error reading NWB file: {e}[/red]")
        raise typer.Exit(1)
