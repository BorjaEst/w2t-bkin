"""Data management utilities for W2T-BKIN pipeline.

Provides functions for:
- Creating experiment structures
- Managing subjects and sessions
- Importing existing raw data safely (using symlinks)
- Validating folder structures and metadata

Safety features:
- Never moves or deletes original data
- Uses symlinks for imports (preserves originals)
- Dry-run mode for imports
- Validation before filesystem operations
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib.resources
import os
from pathlib import Path
import re
import shutil
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.tree import Tree
import tomli
import tomli_w

console = Console()


# =============================================================================
# File System Utilities
# =============================================================================


def ensure_parent_dir(path: Path | str) -> Path:
    """Ensure parent directory exists for the provided path and return Path.

    Args:
        path: File path whose parent directory should be created

    Returns:
        Path object (absolute) for the provided path

    Example:
        >>> p = ensure_parent_dir("data/raw/subject-001/session.toml")
        >>> # Creates data/raw/subject-001/ if it doesn't exist
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# =============================================================================
# TOML Utilities
# =============================================================================


def read_toml(path: Path | str) -> dict:
    """Read and parse a TOML file.

    Args:
        path: Path to TOML file

    Returns:
        Dictionary with parsed TOML content

    Raises:
        FileNotFoundError: If file doesn't exist
        tomli.TOMLDecodeError: If TOML is invalid
    """
    with open(path, "rb") as f:
        return tomli.load(f)


def write_toml(path: Path | str, data: dict, *, ensure_parents: bool = True) -> Path:
    """Write dictionary to TOML file.

    Args:
        path: Target file path
        data: Dictionary to serialize to TOML
        ensure_parents: If True, creates parent directories

    Returns:
        Absolute Path to written file

    Example:
        >>> data = {\"synchronization\": {\"strategy\": \"hardware_pulse\"}}
        >>> write_toml("config.toml", data)
    """
    p = Path(path)
    if ensure_parents:
        p = ensure_parent_dir(p)

    with open(p, "wb") as f:
        tomli_w.dump(data, f)

    return p.resolve()


def validate_toml_syntax(path: Path | str) -> tuple[bool, str | None]:
    """Validate TOML file syntax without loading into memory.

    Args:
        path: Path to TOML file

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_string) if invalid
    """
    try:
        read_toml(path)
        return True, None
    except FileNotFoundError:
        return False, f"File not found: {path}"
    except tomli.TOMLDecodeError as e:
        return False, f"Invalid TOML: {e}"
    except Exception as e:
        return False, f"Error reading TOML: {e}"


@dataclass
class ExperimentConfig:
    """Experiment-level configuration."""

    root_path: Path
    lab: str
    institution: str
    experimenters: List[str]
    protocol: Optional[str] = None
    experiment_description: Optional[str] = None


@dataclass
class SubjectConfig:
    """Subject-level configuration."""

    subject_id: str
    species: str = "Mus musculus"
    sex: str = "U"  # F | M | U (unknown) | O (other)
    age: Optional[str] = None  # ISO 8601 Duration (e.g., P84D)
    genotype: Optional[str] = None
    strain: Optional[str] = None
    date_of_birth: Optional[str] = None
    weight: Optional[str] = None
    description: Optional[str] = None


@dataclass
class SessionConfig:
    """Session-level configuration."""

    session_id: str
    session_date: str  # ISO 8601 date
    session_description: str
    experimenter: str
    session_start_time: Optional[str] = None  # ISO 8601 datetime


@dataclass
class FilePattern:
    """Detected file pattern for auto-import."""

    category: str  # 'video', 'ttl', 'bpod', 'other'
    files: List[Path]
    suggested_pattern: str
    suggested_camera_id: Optional[str] = None
    suggested_ttl_id: Optional[str] = None


# =============================================================================
# Experiment Initialization
# =============================================================================


def init_experiment(
    root_path: Path,
    lab: str,
    institution: str,
    experimenters: List[str],
    protocol: Optional[str] = None,
    experiment_description: Optional[str] = None,
    interactive: bool = True,
) -> bool:
    """Initialize a new experiment folder structure.

    Creates:
    - {root}/data/raw/
    - {root}/data/interim/
    - {root}/data/processed/
    - {root}/data/external/
    - {root}/models/
    - {root}/data/raw/metadata.toml (root metadata)
    - {root}/configuration.toml (pipeline configuration)

    Args:
        root_path: Path to experiment root
        lab: Lab name
        institution: Institution name
        experimenters: List of experimenter names
        protocol: Optional protocol ID (e.g., IACUC number)
        experiment_description: Optional experiment description
        interactive: If True, prompts for confirmation

    Returns:
        True if successful, False otherwise
    """
    root_path = Path(root_path).resolve()

    # Check if already exists
    if root_path.exists() and any(root_path.iterdir()):
        console.print(f"[yellow]⚠ Directory already exists and is not empty: {root_path}[/yellow]")
        if interactive and not Confirm.ask("Continue anyway?", default=False):
            return False

    # Create directory structure with data/ subdirectory
    data_root = root_path / "data"
    folders = {
        "data/raw": data_root / "raw",
        "data/interim": data_root / "interim",
        "data/processed": data_root / "processed",
        "data/external": data_root / "external",
        "models": root_path / "models",
    }

    console.print("\n[cyan]Creating experiment structure...[/cyan]")
    tree = Tree(f"📁 {root_path.name}")

    # Add configuration.toml to tree
    tree.add("📄 configuration.toml")

    # Add data folder with subfolders
    data_branch = tree.add("📁 data/")
    data_branch.add("📁 external/")
    data_branch.add("📁 interim/")
    data_branch.add("📁 processed/")
    raw_branch = data_branch.add("📁 raw/")
    raw_branch.add("📄 metadata.toml")

    # Add models folder
    tree.add("📁 models/")

    for name, path in folders.items():
        path.mkdir(parents=True, exist_ok=True)

    console.print(tree)

    # Generate root metadata.toml
    metadata = {
        "experiment_description": experiment_description or "Multi-subject behavioral experiment",
        "experimenter": experimenters,
        "lab": lab,
        "institution": institution,
        "protocol": protocol or "",
        "keywords": ["behavior", "pose tracking", "synchronization"],
        "devices": [
            {
                "name": "bpod",
                "description": "Bpod State Machine for behavioral control",
                "manufacturer": "Sanworks",
            }
        ],
        "processing_modules": [
            {"name": "behavior", "description": "Processed behavioral data"},
            {"name": "sync", "description": "Synchronization data"},
        ],
    }

    metadata_path = write_toml(folders["data/raw"] / "metadata.toml", metadata)

    console.print(f"\n[green]✓[/green] Created metadata: {metadata_path.relative_to(root_path)}")

    # Copy configuration template (no substitutions needed - template is now parameter-only)
    # Read template from package
    template_ref = importlib.resources.files("w2t_bkin.templates").joinpath("configuration.toml.template")
    config_content = template_ref.read_text()

    config_path = root_path / "configuration.toml"
    with open(config_path, "w") as f:
        f.write(config_content)

    console.print(f"[green]✓[/green] Created config: {config_path.relative_to(root_path)}")

    return True


# =============================================================================
# Subject Management
# =============================================================================


def add_subject(
    experiment_root: Path,
    subject_config: SubjectConfig,
    interactive: bool = True,
) -> bool:
    """Add a new subject to the experiment.

    Creates:
    - {raw_root}/{subject_id}/
    - {raw_root}/{subject_id}/subject.toml

    Args:
        experiment_root: Path to experiment root
        subject_config: Subject configuration
        interactive: If True, prompts for confirmation

    Returns:
        True if successful, False otherwise
    """
    experiment_root = Path(experiment_root).resolve()
    raw_root = experiment_root / "data" / "raw"

    if not raw_root.exists():
        console.print(f"[red]✗ Experiment not initialized: {experiment_root}[/red]")
        console.print(f"  Run: [cyan]python -m w2t_bkin.cli data init {experiment_root}[/cyan]")
        return False

    # Validate subject_id format
    if not re.match(r"^[a-zA-Z0-9_-]+$", subject_config.subject_id):
        console.print(f"[red]✗ Invalid subject ID: {subject_config.subject_id}[/red]")
        console.print(f"  Use only letters, numbers, hyphens, and underscores")
        return False

    subject_dir = raw_root / subject_config.subject_id

    if subject_dir.exists():
        console.print(f"[yellow]⚠ Subject already exists: {subject_config.subject_id}[/yellow]")
        if interactive and not Confirm.ask("Overwrite subject.toml?", default=False):
            return False

    # Create subject directory
    subject_dir.mkdir(parents=True, exist_ok=True)

    # Generate subject.toml
    subject_data = {
        "subject": {
            "subject_id": subject_config.subject_id,
            "species": subject_config.species,
            "sex": subject_config.sex,
        }
    }

    # Add optional fields
    if subject_config.age:
        subject_data["subject"]["age"] = subject_config.age
    if subject_config.genotype:
        subject_data["subject"]["genotype"] = subject_config.genotype
    if subject_config.strain:
        subject_data["subject"]["strain"] = subject_config.strain
    if subject_config.date_of_birth:
        subject_data["subject"]["date_of_birth"] = subject_config.date_of_birth
    if subject_config.weight:
        subject_data["subject"]["weight"] = subject_config.weight
    if subject_config.description:
        subject_data["subject"]["description"] = subject_config.description

    subject_toml_path = write_toml(subject_dir / "subject.toml", subject_data)

    console.print(f"\n[green]✓ Subject added: {subject_config.subject_id}[/green]")
    console.print(f"  Location: {subject_dir.relative_to(experiment_root)}")
    console.print(f"  Metadata: {subject_toml_path.relative_to(experiment_root)}")

    console.print(f"\nNext step:")
    console.print(f"  Add session: [cyan]python -m w2t_bkin.cli data add-session {experiment_root} " f"{subject_config.subject_id} <session-id>[/cyan]")

    return True


# =============================================================================
# Session Management
# =============================================================================


def add_session(
    experiment_root: Path,
    subject_id: str,
    session_config: SessionConfig,
    create_subdirs: bool = True,
    interactive: bool = True,
) -> bool:
    """Add a new session for a subject.

    Creates:
    - {raw_root}/{subject_id}/{session_id}/
    - {raw_root}/{subject_id}/{session_id}/session.toml
    - {raw_root}/{subject_id}/{session_id}/Video/ (if create_subdirs)
    - {raw_root}/{subject_id}/{session_id}/TTLs/ (if create_subdirs)
    - {raw_root}/{subject_id}/{session_id}/Bpod/ (if create_subdirs)

    Args:
        experiment_root: Path to experiment root
        subject_id: Subject identifier
        session_config: Session configuration
        create_subdirs: If True, creates Video/TTLs/Bpod subdirectories
        interactive: If True, prompts for confirmation

    Returns:
        True if successful, False otherwise
    """
    experiment_root = Path(experiment_root).resolve()
    raw_root = experiment_root / "data" / "raw"
    subject_dir = raw_root / subject_id

    if not subject_dir.exists():
        console.print(f"[red]✗ Subject not found: {subject_id}[/red]")
        console.print(f"  Run: [cyan]python -m w2t_bkin.cli data add-subject {experiment_root} {subject_id}[/cyan]")
        return False

    # Validate session_id format
    if not re.match(r"^[a-zA-Z0-9_-]+$", session_config.session_id):
        console.print(f"[red]✗ Invalid session ID: {session_config.session_id}[/red]")
        console.print(f"  Use only letters, numbers, hyphens, and underscores")
        return False

    session_dir = subject_dir / session_config.session_id

    if session_dir.exists():
        console.print(f"[yellow]⚠ Session already exists: {subject_id}/{session_config.session_id}[/yellow]")
        if interactive and not Confirm.ask("Overwrite session.toml?", default=False):
            return False

    # Create session directory
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create standard subdirectories
    if create_subdirs:
        (session_dir / "Video").mkdir(exist_ok=True)
        (session_dir / "TTLs").mkdir(exist_ok=True)
        (session_dir / "Bpod").mkdir(exist_ok=True)

    # Generate session.toml
    session_start_time = session_config.session_start_time or f"{session_config.session_date}T00:00:00Z"
    identifier = f"{subject_id}-{session_config.session_id}"

    session_data = {
        "session_description": session_config.session_description,
        "identifier": identifier,
        "session_start_time": session_start_time,
        "session_id": session_config.session_id,
        "experimenter": [session_config.experimenter],
    }

    session_toml_path = write_toml(session_dir / "session.toml", session_data)

    console.print(f"\n[green]✓ Session added: {subject_id}/{session_config.session_id}[/green]")
    console.print(f"  Location: {session_dir.relative_to(experiment_root)}")
    console.print(f"  Metadata: {session_toml_path.relative_to(experiment_root)}")

    if create_subdirs:
        console.print(f"\n  Standard folders created:")
        console.print(f"    • Video/")
        console.print(f"    • TTLs/")
        console.print(f"    • Bpod/")

    console.print(f"\nNext steps:")
    console.print(f"  1. Add raw data to session folder")
    console.print(f"  2. Edit session metadata: [dim]{session_toml_path}[/dim]")
    console.print(
        f"  3. Or import existing data: [cyan]python -m w2t_bkin.cli data import-raw --source <path> "
        f"--experiment {experiment_root} --subject {subject_id} --session {session_config.session_id}[/cyan]"
    )

    return True


# =============================================================================
# Data Import (Safe - Uses Symlinks)
# =============================================================================


def detect_file_patterns(source_dir: Path) -> Dict[str, FilePattern]:
    """Detect file patterns in source directory.

    Categorizes files into:
    - video: *.avi, *.mp4, *.mkv
    - ttl: *ttl*.txt, *pulse*.txt, *.txt (in TTL-related folders)
    - bpod: *.mat
    - other: everything else

    Args:
        source_dir: Source directory to scan

    Returns:
        Dictionary mapping pattern names to FilePattern objects
    """
    patterns: Dict[str, FilePattern] = {}

    video_extensions = {".avi", ".mp4", ".mkv", ".mov"}
    ttl_patterns = ["ttl", "pulse", "sync", "trigger"]

    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        name_lower = file_path.name.lower()
        parent_lower = file_path.parent.name.lower()

        # Video files
        if ext in video_extensions:
            # Try to detect camera ID from filename or path
            camera_match = re.search(r"cam(era)?[_-]?(\d+|[a-z]+)", name_lower)
            camera_id = f"camera_{camera_match.group(2)}" if camera_match else "camera_0"

            if camera_id not in patterns:
                patterns[camera_id] = FilePattern(
                    category="video",
                    files=[],
                    suggested_pattern=f"Video/{camera_id}/*{ext}",
                    suggested_camera_id=camera_id,
                )
            patterns[camera_id].files.append(file_path)

        # TTL files
        elif ext == ".txt" and any(p in name_lower or p in parent_lower for p in ttl_patterns):
            # Try to detect TTL ID
            ttl_match = re.search(r"ttl[_-]?([a-z]+)", name_lower)
            ttl_id = f"ttl_{ttl_match.group(1)}" if ttl_match else "ttl_sync"

            if ttl_id not in patterns:
                patterns[ttl_id] = FilePattern(
                    category="ttl",
                    files=[],
                    suggested_pattern=f"TTLs/{ttl_id}_*.txt",
                    suggested_ttl_id=ttl_id,
                )
            patterns[ttl_id].files.append(file_path)

        # Bpod MATLAB files
        elif ext == ".mat":
            if "bpod" not in patterns:
                patterns["bpod"] = FilePattern(
                    category="bpod",
                    files=[],
                    suggested_pattern="Bpod/*.mat",
                )
            patterns["bpod"].files.append(file_path)

        # Other files
        else:
            if "other" not in patterns:
                patterns["other"] = FilePattern(
                    category="other",
                    files=[],
                    suggested_pattern="Other/*",
                )
            patterns["other"].files.append(file_path)

    return patterns


def import_raw_data(
    source_dir: Path,
    experiment_root: Path,
    subject_id: str,
    session_id: str,
    auto_detect: bool = True,
    dry_run: bool = True,
    file_patterns: Optional[Dict[str, FilePattern]] = None,
) -> bool:
    """Import existing raw data using symlinks (SAFE - preserves originals).

    Args:
        source_dir: Source directory containing raw data
        experiment_root: Experiment root path
        subject_id: Subject identifier
        session_id: Session identifier
        auto_detect: If True, automatically detects file patterns
        dry_run: If True, shows preview without creating links
        file_patterns: Optional pre-detected file patterns

    Returns:
        True if successful, False otherwise
    """
    source_dir = Path(source_dir).resolve()
    experiment_root = Path(experiment_root).resolve()

    if not source_dir.exists():
        console.print(f"[red]✗ Source directory not found: {source_dir}[/red]")
        return False

    session_dir = experiment_root / "data" / "raw" / subject_id / session_id

    if not session_dir.exists():
        console.print(f"[red]✗ Session not found: {subject_id}/{session_id}[/red]")
        console.print(f"  Create it first: [cyan]python -m w2t_bkin.cli data add-session " f"{experiment_root} {subject_id} {session_id}[/cyan]")
        return False

    # Detect patterns if not provided
    if file_patterns is None and auto_detect:
        console.print(f"\n[cyan]Scanning source directory...[/cyan]")
        file_patterns = detect_file_patterns(source_dir)

    if not file_patterns:
        console.print(f"[yellow]⚠ No recognizable files found in {source_dir}[/yellow]")
        return False

    # Display preview
    console.print(f"\n[bold]Import Preview:[/bold]")
    console.print(f"  Source: [cyan]{source_dir}[/cyan]")
    console.print(f"  Target: [cyan]{session_dir.relative_to(experiment_root)}[/cyan]")
    console.print()

    table = Table(title="Detected Files")
    table.add_column("Category", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Target Pattern", style="dim")

    total_files = 0
    for pattern_name, pattern in file_patterns.items():
        table.add_row(
            pattern.category.upper(),
            str(len(pattern.files)),
            pattern.suggested_pattern,
        )
        total_files += len(pattern.files)

    console.print(table)
    console.print(f"\n  Total files: [bold]{total_files}[/bold]")

    if dry_run:
        console.print(f"\n[yellow]DRY RUN - No files will be modified[/yellow]")
        console.print(f"  Add [green]--confirm[/green] to execute the import")
        return True

    # Confirm before proceeding
    console.print(f"\n[bold yellow]⚠ This will create symbolic links (originals preserved)[/bold yellow]")
    if not Confirm.ask("Proceed with import?", default=False):
        console.print("[yellow]Import cancelled[/yellow]")
        return False

    # Create symlinks
    console.print(f"\n[cyan]Creating symbolic links...[/cyan]")
    created_count = 0
    cameras_config = []
    ttls_config = []

    for pattern_name, pattern in file_patterns.items():
        if pattern.category == "video":
            target_dir = session_dir / "Video" / pattern.suggested_camera_id
        elif pattern.category == "ttl":
            target_dir = session_dir / "TTLs"
        elif pattern.category == "bpod":
            target_dir = session_dir / "Bpod"
        else:
            target_dir = session_dir / "Other"

        target_dir.mkdir(parents=True, exist_ok=True)

        for source_file in pattern.files:
            target_file = target_dir / source_file.name

            try:
                # Create relative symlink
                os.symlink(source_file, target_file)
                created_count += 1

            except FileExistsError:
                console.print(f"  [dim]Skip (exists): {target_file.name}[/dim]")
            except Exception as e:
                console.print(f"  [red]✗ Failed: {target_file.name} - {e}[/red]")

        # Track for metadata generation
        if pattern.category == "video" and pattern.suggested_camera_id:
            cameras_config.append(
                {
                    "id": pattern.suggested_camera_id,
                    "paths": f"Video/{pattern.suggested_camera_id}/*{pattern.files[0].suffix}",
                    "order": "name_asc",
                    "fps": 30.0,  # Default, user should update
                    "ttl_id": "ttl_camera",
                    "optional": False,
                }
            )
        elif pattern.category == "ttl" and pattern.suggested_ttl_id:
            ttls_config.append(
                {
                    "id": pattern.suggested_ttl_id,
                    "paths": pattern.suggested_pattern,
                    "description": f"{pattern.suggested_ttl_id} synchronization",
                }
            )

    console.print(f"\n[green]✓ Created {created_count} symbolic links[/green]")

    # Update session.toml with detected cameras/TTLs
    session_toml_path = session_dir / "session.toml"
    if cameras_config or ttls_config:
        console.print(f"\n[cyan]Updating session metadata...[/cyan]")

        # Read existing session.toml
        session_data = read_toml(session_toml_path)

        # Add cameras and TTLs
        if cameras_config:
            session_data["cameras"] = cameras_config
        if ttls_config:
            session_data["TTLs"] = ttls_config

        # Write updated session.toml
        write_toml(session_toml_path, session_data)

        console.print(f"[green]✓ Updated: {session_toml_path.relative_to(experiment_root)}[/green]")
        console.print(f"\n[yellow]⚠ Please review and update:[/yellow]")
        console.print(f"  • Camera FPS values")
        console.print(f"  • TTL channel descriptions")
        console.print(f"  • Camera-TTL mappings")

    console.print(f"\n[bold green]✓ Import completed successfully![/bold green]")
    return True


# =============================================================================
# Structure Validation
# =============================================================================


@dataclass
class ValidationResult:
    """Validation result."""

    valid: bool
    errors: List[str]
    warnings: List[str]
    info: List[str]


def validate_experiment_structure(
    experiment_root: Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
    verbose: bool = False,
) -> ValidationResult:
    """Validate experiment folder structure and metadata.

    Checks:
    - Required folders exist (raw/, interim/, processed/)
    - Root metadata.toml exists and is valid
    - Subject folders have subject.toml
    - Session folders have session.toml
    - Referenced files in metadata exist
    - Camera/TTL configurations are complete

    Args:
        experiment_root: Experiment root path
        subject_filter: Optional subject ID filter
        session_filter: Optional session ID filter
        verbose: If True, shows detailed validation info

    Returns:
        ValidationResult with errors, warnings, and info
    """
    experiment_root = Path(experiment_root).resolve()
    result = ValidationResult(valid=True, errors=[], warnings=[], info=[])

    # Check root structure (data subdirectory)
    data_root = experiment_root / "data"
    required_folders = ["data/raw", "data/interim", "data/processed"]
    for folder in required_folders:
        folder_path = experiment_root / folder
        if not folder_path.exists():
            result.errors.append(f"Missing required folder: {folder}/")
            result.valid = False
        else:
            result.info.append(f"✓ Found: {folder}/")

    # Check root metadata
    root_metadata = data_root / "raw" / "metadata.toml"
    if not root_metadata.exists():
        result.warnings.append(f"Missing root metadata: data/raw/metadata.toml")
    else:
        result.info.append(f"✓ Found root metadata")
        # Validate TOML syntax
        is_valid, error = validate_toml_syntax(root_metadata)
        if not is_valid:
            result.errors.append(f"Invalid TOML in metadata.toml: {error}")
            result.valid = False

    # Check configuration.toml
    config_path = experiment_root / "configuration.toml"
    if not config_path.exists():
        result.warnings.append(f"Missing configuration.toml")
    else:
        result.info.append(f"✓ Found configuration.toml")

    # Validate subjects and sessions
    raw_root = data_root / "raw"
    if raw_root.exists():
        subjects = [d for d in raw_root.iterdir() if d.is_dir() and d.name != "metadata.toml"]

        # Apply subject filter
        if subject_filter:
            subjects = [s for s in subjects if s.name == subject_filter]

        result.info.append(f"Found {len(subjects)} subject(s)")

        for subject_dir in subjects:
            subject_id = subject_dir.name

            # Check subject.toml
            subject_toml = subject_dir / "subject.toml"
            if not subject_toml.exists():
                result.warnings.append(f"Missing {subject_id}/subject.toml")
            else:
                is_valid, error = validate_toml_syntax(subject_toml)
                if not is_valid:
                    result.errors.append(f"Invalid TOML in {subject_id}/subject.toml: {error}")
                    result.valid = False

            # Check sessions
            sessions = [d for d in subject_dir.iterdir() if d.is_dir()]

            # Apply session filter
            if session_filter:
                sessions = [s for s in sessions if s.name == session_filter]

            for session_dir in sessions:
                session_id = session_dir.name
                session_path = f"{subject_id}/{session_id}"

                # Check session.toml
                session_toml = session_dir / "session.toml"
                if not session_toml.exists():
                    result.errors.append(f"Missing {session_path}/session.toml")
                    result.valid = False
                else:
                    try:
                        session_data = read_toml(session_toml)

                        # Validate required fields
                        required_fields = ["session_description", "identifier", "session_start_time"]
                        for field in required_fields:
                            if field not in session_data:
                                result.errors.append(f"{session_path}: Missing required field '{field}'")
                                result.valid = False

                        # Check camera files exist
                        if "cameras" in session_data:
                            for camera in session_data["cameras"]:
                                camera_id = camera.get("id")
                                pattern = camera.get("paths")
                                if camera_id and pattern:
                                    # Check if any files match pattern
                                    import glob

                                    matches = list(session_dir.glob(pattern))
                                    if not matches and not camera.get("optional", False):
                                        result.warnings.append(f"{session_path}: No files found for camera '{camera_id}' (pattern: {pattern})")

                        # Check TTL files exist
                        if "TTLs" in session_data:
                            for ttl in session_data["TTLs"]:
                                ttl_id = ttl.get("id")
                                pattern = ttl.get("paths")
                                if ttl_id and pattern:
                                    import glob

                                    matches = list(session_dir.glob(pattern))
                                    if not matches:
                                        result.warnings.append(f"{session_path}: No files found for TTL '{ttl_id}' (pattern: {pattern})")

                    except Exception as e:
                        result.errors.append(f"Invalid TOML in {session_path}/session.toml: {e}")
                        result.valid = False

    return result


def validate_symlinks(root_path: Path, console: Optional[Console] = None) -> Tuple[bool, List[str]]:
    """Validate symlinks in experiment structure.

    Checks all symlinks in the data/raw directory to ensure they point to
    existing targets. Broken symlinks are reported as issues.

    Args:
        root_path: Experiment root path
        console: Rich console for output (optional, creates new if None)

    Returns:
        Tuple of (is_valid, list_of_issues)

    Example:
        >>> valid, issues = validate_symlinks(Path("/data/experiment"))
        >>> if not valid:
        ...     print(f"Found {len(issues)} broken symlinks")
    """
    if console is None:
        console = Console()

    issues = []
    raw_root = root_path / "data" / "raw"

    if not raw_root.exists():
        console.print("[yellow]⚠[/yellow] No raw data directory found - skipping symlink validation")
        return True, []

    console.print("[cyan]🔍 Checking symlinks...[/cyan]")

    # Find all symlinks recursively
    symlinks = [p for p in raw_root.rglob("*") if p.is_symlink()]

    if not symlinks:
        console.print("[green]✓[/green] No symlinks found")
        return True, []

    console.print(f"Found {len(symlinks)} symlink(s)")

    for link in symlinks:
        rel_path = link.relative_to(raw_root)

        try:
            target = link.resolve(strict=True)
            console.print(f"[green]✓[/green] {rel_path} → {target}")
        except (FileNotFoundError, RuntimeError) as e:
            # Symlink is broken (target doesn't exist)
            try:
                # Get the target path even if it doesn't exist
                target = link.readlink() if hasattr(link, "readlink") else link.resolve(strict=False)
            except Exception:
                target = "unknown"

            issue = f"Broken symlink: {rel_path} → {target} (target does not exist)"
            console.print(f"[red]✗[/red] {issue}")
            issues.append(issue)

    if issues:
        console.print(f"\n[red]Found {len(issues)} broken symlink(s)[/red]")
        return False, issues
    else:
        console.print(f"\n[green]All {len(symlinks)} symlink(s) valid[/green]")
        return True, []
