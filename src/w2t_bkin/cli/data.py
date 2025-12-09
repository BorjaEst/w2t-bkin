"""Data management commands for experiment setup."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.prompt import Confirm, Prompt
import typer

from ..data_manager import ExperimentConfig, SessionConfig, SubjectConfig
from ..data_manager import add_session as dm_add_session
from ..data_manager import add_subject as dm_add_subject
from ..data_manager import import_raw_data as dm_import_raw_data
from ..data_manager import init_experiment as dm_init_experiment
from ..data_manager import validate_experiment_structure as dm_validate_structure
from .utils import console, copy_docker_compose_template, copy_dockerfile, create_startup_scripts, generate_docker_env

data_app = typer.Typer(name="data", help="Experiment data management")


@data_app.command(name="init")
def init(
    root_path: Path = typer.Argument(..., help="Path to experiment root directory"),
    lab: Optional[str] = typer.Option(None, "--lab", help="Lab name"),
    institution: Optional[str] = typer.Option(None, "--institution", help="Institution name"),
    experimenters: Optional[str] = typer.Option(None, "--experimenters", help="Comma-separated experimenter names"),
    protocol: Optional[str] = typer.Option(None, "--protocol", help="Protocol ID (e.g., IACUC number)"),
    description: Optional[str] = typer.Option(None, "--description", help="Experiment description"),
    skip_docker_env: bool = typer.Option(False, "--skip-docker-env", help="Skip Docker .env generation"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Initialize a new experiment folder structure.

    Creates:
    - {root}/data/raw/ (with metadata.toml)
    - {root}/data/interim/
    - {root}/data/processed/
    - {root}/data/external/
    - {root}/models/
    - {root}/configuration.toml

    Optionally generates Docker .env file for containerized deployment.

    Example:
        $ w2t-bkin data init /data/my-experiment --lab "Larkum Lab" --institution "HU Berlin" --experimenters "Alice,Bob"
        $ w2t-bkin data init /data/my-experiment --skip-docker-env -y
    """
    # Interactive prompts if values not provided
    if not yes:
        if not lab:
            lab = Prompt.ask("Lab name")
        if not institution:
            institution = Prompt.ask("Institution name")
        if not experimenters:
            experimenters = Prompt.ask("Experimenter names (comma-separated)")

    # Ensure required fields
    if not lab or not institution or not experimenters:
        console.print("[red]Error: lab, institution, and experimenters are required[/red]")
        raise typer.Exit(1)

    experimenter_list = [e.strip() for e in experimenters.split(",")]

    # Call pure function
    success = dm_init_experiment(
        root_path=root_path,
        lab=lab,
        institution=institution,
        experimenters=experimenter_list,
        protocol=protocol,
        experiment_description=description,
        interactive=not yes,
    )

    if not success:
        console.print("[red]✗ Failed to initialize experiment[/red]")
        raise typer.Exit(1)

    # Setup Docker environment (unless explicitly skipped)
    if not skip_docker_env:
        console.print("\n[cyan]🐳 Setting up Docker environment...[/cyan]")

        # Step 1: Copy docker-compose.yml
        compose_path = root_path / "docker-compose.yml"
        if copy_docker_compose_template(compose_path):
            console.print(f"[green]✓[/green] Created docker-compose.yml")
        else:
            console.print("[yellow]⚠ Could not create docker-compose.yml[/yellow]")
            console.print("[dim]  You can copy it manually from the repository[/dim]")

        # Step 1b: Copy Dockerfile (needed for local builds)
        dockerfile_path = root_path / "Dockerfile"
        if copy_dockerfile(dockerfile_path):
            console.print(f"[green]✓[/green] Copied Dockerfile")
        else:
            console.print("[yellow]⚠ Could not copy Dockerfile (using pip install? Set images in .env)[/yellow]")

        # Step 2: Generate .env file
        env_path = root_path / "docker" / ".env"
        try:
            generate_docker_env(root_path, env_path)
            console.print(f"[green]✓[/green] Generated docker/.env")
        except Exception as e:
            console.print(f"[yellow]⚠ Could not generate .env: {e}[/yellow]")

        # Step 3: Create startup scripts
        try:
            create_startup_scripts(root_path)
            console.print(f"[green]✓[/green] Created startup scripts")

            # Show usage instructions
            console.print("\n[bold green]✓ Experiment initialized successfully![/bold green]")
            console.print("\n[bold]To start the pipeline:[/bold]")

            import platform

            if platform.system() == "Windows":
                console.print(f"  1. Double-click: [cyan]{root_path / 'start-server.bat'}[/cyan]")
                console.print(f"  2. Open browser to: [cyan]http://localhost:4200[/cyan]")
            else:
                console.print(f"  1. Run: [cyan]cd {root_path} && ./start-server.sh[/cyan]")
                console.print(f"  2. Open browser to: [cyan]http://localhost:4200[/cyan]")

            console.print("\n[dim]Other useful scripts:[/dim]")
            console.print(f"  [dim]• stop-server: Stop all containers[/dim]")
            console.print(f"  [dim]• view-logs: View container logs[/dim]")
            console.print(f"  [dim]• open-ui: Open Prefect UI in browser[/dim]")

        except Exception as e:
            console.print(f"[yellow]⚠ Could not create startup scripts: {e}[/yellow]")


@data_app.command(name="add-subject")
def add_subject(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject_id: str = typer.Argument(..., help="Subject identifier (letters, numbers, hyphens, underscores)"),
    species: str = typer.Option("Mus musculus", "--species", help="Species name"),
    sex: str = typer.Option("U", "--sex", help="Sex (F|M|U|O)"),
    age: Optional[str] = typer.Option(None, "--age", help="Age in ISO 8601 duration (e.g., P84D for 84 days)"),
    genotype: Optional[str] = typer.Option(None, "--genotype", help="Genotype"),
    strain: Optional[str] = typer.Option(None, "--strain", help="Strain"),
    date_of_birth: Optional[str] = typer.Option(None, "--date-of-birth", help="Date of birth (ISO 8601)"),
    weight: Optional[str] = typer.Option(None, "--weight", help="Weight"),
    description: Optional[str] = typer.Option(None, "--description", help="Subject description"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Add a new subject to the experiment.

    Creates:
    - {raw_root}/{subject_id}/
    - {raw_root}/{subject_id}/subject.toml

    Example:
        $ w2t-bkin data add-subject /data/my-experiment mouse-001
        $ w2t-bkin data add-subject /data/my-experiment mouse-001 --species "Mus musculus" --sex F --age P84D -y
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

    success = dm_add_subject(
        experiment_root=experiment_root,
        subject_config=subject_config,
        interactive=not yes,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="add-session")
def add_session(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject_id: str = typer.Argument(..., help="Subject identifier"),
    session_id: str = typer.Argument(..., help="Session identifier (letters, numbers, hyphens, underscores)"),
    date: Optional[str] = typer.Option(None, "--date", help="Session date (ISO 8601, e.g., 2024-01-15)"),
    description: Optional[str] = typer.Option(None, "--description", help="Session description"),
    experimenter: Optional[str] = typer.Option(None, "--experimenter", help="Experimenter name"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Session start time (ISO 8601)"),
    no_subdirs: bool = typer.Option(False, "--no-subdirs", help="Don't create Video/TTLs/Bpod folders"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """Add a new session for a subject.

    Creates:
    - {raw_root}/{subject_id}/{session_id}/
    - {raw_root}/{subject_id}/{session_id}/session.toml
    - {raw_root}/{subject_id}/{session_id}/Video/ (optional)
    - {raw_root}/{subject_id}/{session_id}/TTLs/ (optional)
    - {raw_root}/{subject_id}/{session_id}/Bpod/ (optional)

    Example:
        $ w2t-bkin data add-session /data/my-experiment mouse-001 session-001
        $ w2t-bkin data add-session /data/my-experiment mouse-001 session-001 --date 2024-01-15 --experimenter Alice -y
        $ w2t-bkin data add-session /data/my-experiment mouse-001 session-002 --no-subdirs -y
    """
    # Interactive prompts if not provided
    if not yes:
        if not description:
            description = Prompt.ask("Session description", default="Behavioral session")
        if not experimenter:
            experimenter = Prompt.ask("Experimenter name")

    if not description or not experimenter:
        console.print("[red]Error: description and experimenter are required[/red]")
        raise typer.Exit(1)

    # Use current date if not provided
    session_date = date or datetime.now().strftime("%Y-%m-%d")

    session_config = SessionConfig(
        session_id=session_id,
        session_date=session_date,
        session_description=description,
        experimenter=experimenter,
        session_start_time=start_time,
    )

    success = dm_add_session(
        experiment_root=experiment_root,
        subject_id=subject_id,
        session_config=session_config,
        create_subdirs=not no_subdirs,
        interactive=not yes,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="import-raw")
def import_raw(
    source: Path = typer.Argument(..., help="Source directory containing raw data"),
    experiment: Path = typer.Option(..., "--experiment", "-e", help="Experiment root directory"),
    subject: str = typer.Option(..., "--subject", "-s", help="Target subject ID"),
    session: str = typer.Option(..., "--session", help="Target session ID"),
    no_detect: bool = typer.Option(False, "--no-detect", help="Skip automatic file pattern detection"),
    confirm: bool = typer.Option(False, "--confirm", help="Execute import (required for actual operation)"),
):
    """Import existing raw data using symbolic links (SAFE - preserves originals).

    This command creates symbolic links from source files to the session directory,
    preserving the original data. It auto-detects cameras, TTLs, and Bpod files
    and updates session.toml with detected configuration.

    Safety Features:
    - Symbolic links only (never moves/copies/deletes)
    - Originals preserved in source directory
    - Dry-run by default (requires --confirm to execute)
    - Auto-updates metadata (session.toml with detected cameras/TTLs)

    Example:
        # Step 1: Preview (dry-run, no changes)
        $ w2t-bkin data import-raw /raw-storage/2024-01-15 -e /data/my-experiment -s mouse-001 --session session-001

        # Step 2: Execute (creates symbolic links)
        $ w2t-bkin data import-raw /raw-storage/2024-01-15 -e /data/my-experiment -s mouse-001 --session session-001 --confirm
    """
    success = dm_import_raw_data(
        source_dir=source,
        experiment_root=experiment,
        subject_id=subject,
        session_id=session,
        auto_detect=not no_detect,
        dry_run=not confirm,
    )

    if not success:
        raise typer.Exit(1)


@data_app.command(name="validate")
def validate(
    experiment_root: Path = typer.Argument(..., help="Path to experiment root directory"),
    subject: Optional[str] = typer.Option(None, "--subject", help="Filter by specific subject ID"),
    session: Optional[str] = typer.Option(None, "--session", help="Filter by specific session ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed validation info"),
):
    """Validate experiment folder structure and metadata.

    Checks:
    - Required folders exist (raw/, interim/, processed/)
    - Root metadata.toml exists and is valid
    - Subject folders have subject.toml
    - Session folders have session.toml
    - Referenced files in metadata exist
    - Camera/TTL configurations are complete

    Example:
        $ w2t-bkin data validate /data/my-experiment
        $ w2t-bkin data validate /data/my-experiment --subject mouse-001
        $ w2t-bkin data validate /data/my-experiment --subject mouse-001 --session session-001 --verbose
    """
    result = dm_validate_structure(
        experiment_root=experiment_root,
        subject_filter=subject,
        session_filter=session,
        verbose=verbose,
    )

    # Display errors
    if result.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in result.errors:
            console.print(f"  [red]✗[/red] {error}")

    # Display warnings
    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    # Display info if verbose
    if verbose and result.info:
        console.print("\n[bold]Info:[/bold]")
        for info in result.info:
            console.print(f"  [dim]{info}[/dim]")

    # Summary
    if result.valid:
        console.print("\n[bold green]✓ Validation passed[/bold green]")
        if result.warnings:
            console.print(f"  ({len(result.warnings)} warnings)")
        raise typer.Exit(0)
    else:
        console.print(f"\n[bold red]✗ Validation failed[/bold red]")
        console.print(f"  {len(result.errors)} error(s), {len(result.warnings)} warning(s)")
        raise typer.Exit(1)
