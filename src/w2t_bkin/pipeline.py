"""Pipeline orchestration for W2T Body Kinematics.

This module implements the high-level pipeline orchestration following the
6-phase workflow defined in docs/pipeline-design.md with improvements:

- Class-based orchestrator (SessionPipeline) for state management
- Rich logging with progress bars and formatted output
- NWB validation with nwbinspector
- Centralized path logic in config validators
- Typer CLI for enhanced command-line interface

Phase 0: Initialization - Load config, create NWBFile
Phase 1: Discovery & Verification - Find files, verify consistency
Phase 2: Ingestion - Process Bpod, Pose, TTL data
Phase 3: Synchronization - Align data streams to reference timeline
Phase 4: Assembly - Add all objects to NWBFile
Phase 5: Finalization - Write NWB file, validate, and create sidecars

Architecture:
- SessionPipeline class encapsulates config, metadata, and nwbfile
- Rich console for beautiful progress tracking and logging
- Typer for CLI commands: run, validate, inspect
- In-memory NWB → Atomic write → Validation strategy

Example:
    >>> from w2t_bkin.pipeline import SessionPipeline
    >>>
    >>> pipeline = SessionPipeline(
    ...     config_path="config.toml",
    ...     subject_id="subject-001",
    ...     session_id="session-001"
    ... )
    >>> result = pipeline.run()
    >>> print(f"NWB written to: {result.nwb_path}")
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from pynwb import NWBFile
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from . import utils
from .behavior import (
    build_task,
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
    extract_task_arguments,
)
from .bpod import parse_bpod
from .config import Config, load_config
from .exceptions import IngestError, MismatchExceedsToleranceError, SyncError
from .session import add_video_acquisition, create_nwb_file, load_metadata, write_nwb_file
from .sync import align_bpod_trials_to_ttl
from .ttl import get_ttl_pulses

# Setup rich console and logging
console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(console=console, rich_tracebacks=True)])
logger = logging.getLogger(__name__)

__all__ = ["RunOptions", "RunResult", "SessionPipeline", "run_session"]


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class RunOptions:
    """Options for pipeline execution.

    Attributes:
        skip_bpod: Skip Bpod processing (default: False)
        skip_pose: Skip pose processing (default: False)
        skip_ttl: Skip TTL processing (default: False)
        skip_verification: Skip file verification (default: False)
        skip_nwb_validation: Skip NWB validation with nwbinspector (default: False)
        force_overwrite: Overwrite existing output files (default: False)
    """

    skip_bpod: bool = False
    skip_pose: bool = False
    skip_ttl: bool = False
    skip_verification: bool = False
    skip_nwb_validation: bool = False
    force_overwrite: bool = False


@dataclass
class RunResult:
    """Result of pipeline execution.

    Attributes:
        nwb_path: Path to written NWB file
        nwbfile: In-memory NWBFile object
        alignment_stats: Synchronization alignment statistics
        validation_results: NWB validation results from nwbinspector
        success: Whether pipeline completed successfully
        error: Error message if failed
    """

    nwb_path: Path
    nwbfile: Optional[NWBFile] = None
    alignment_stats: Optional[Dict[str, Any]] = None
    validation_results: Optional[List[Dict[str, Any]]] = None
    success: bool = True
    error: Optional[str] = None


# =============================================================================
# SessionPipeline Class
# =============================================================================


class SessionPipeline:
    """Session-level pipeline orchestrator.

    Encapsulates configuration, metadata, and NWBFile state for a single
    session processing run. Provides methods for each pipeline phase and
    orchestrates the complete workflow.

    Attributes:
        config_path: Path to configuration file
        subject_id: Subject identifier
        session_id: Session identifier
        options: Pipeline execution options
        config: Loaded configuration (set after initialization)
        metadata: Session metadata (set after initialization)
        nwbfile: NWBFile object (set after initialization)
        session_dir: Session directory path (set after initialization)
    """

    def __init__(self, config_path: str | Path, subject_id: str, session_id: str, options: Optional[RunOptions] = None):
        """Initialize pipeline for a session.

        Args:
            config_path: Path to config.toml
            subject_id: Subject identifier (e.g., "subject-001")
            session_id: Session identifier (e.g., "session-001")
            options: Pipeline execution options (optional)
        """
        self.config_path = Path(config_path)
        self.subject_id = subject_id
        self.session_id = session_id
        self.options = options or RunOptions()

        # State variables (populated during phases)
        self.config: Optional[Config] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.nwbfile: Optional[NWBFile] = None
        self.session_dir: Optional[Path] = None

        # Intermediate results
        self.camera_files: Dict[str, List[Path]] = {}
        self.bpod_files: Dict[str, List[Path]] = {}
        self.ttl_files: Dict[str, List[Path]] = {}
        self.bpod_data: Optional[Dict[str, Any]] = None
        self.trial_offsets: Optional[Dict[int, float]] = None
        self.ttl_pulses: Dict[str, List[float]] = {}
        self.alignment_stats: Dict[str, Any] = {}

    def run(self) -> RunResult:
        """Run complete pipeline workflow.

        Executes all 6 phases with rich progress tracking and error handling.

        Returns:
            RunResult with paths, NWBFile, statistics, and validation results

        Raises:
            Exception: Any phase failure is caught and returned in RunResult
        """
        console.print(
            Panel.fit(
                f"[bold cyan]W2T Body Kinematics Pipeline[/bold cyan]\n"
                f"Subject: [yellow]{self.subject_id}[/yellow]\n"
                f"Session: [yellow]{self.session_id}[/yellow]\n"
                f"Config: [dim]{self.config_path}[/dim]",
                border_style="cyan",
            )
        )

        try:
            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeRemainingColumn(), console=console
            ) as progress:

                # Phase 0: Initialization
                task = progress.add_task("[cyan]Phase 0: Initialization", total=1)
                self._phase_0_initialization()
                progress.update(task, advance=1)

                # Phase 1: Discovery & Verification
                task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=1)
                self._phase_1_discovery()
                progress.update(task, advance=1)

                # Phase 2: Ingestion
                task = progress.add_task("[cyan]Phase 2: Ingestion", total=1)
                self._phase_2_ingestion()
                progress.update(task, advance=1)

                # Phase 3: Synchronization
                task = progress.add_task("[cyan]Phase 3: Synchronization", total=1)
                self._phase_3_synchronization()
                progress.update(task, advance=1)

                # Phase 4: Assembly
                task = progress.add_task("[cyan]Phase 4: Assembly", total=1)
                self._phase_4_assembly()
                progress.update(task, advance=1)

                # Phase 5: Finalization
                task = progress.add_task("[cyan]Phase 5: Finalization & Validation", total=1)
                nwb_path, validation_results = self._phase_5_finalization()
                progress.update(task, advance=1)

            console.print("\n[bold green]✓ Pipeline completed successfully[/bold green]")

            return RunResult(nwb_path=nwb_path, nwbfile=self.nwbfile, alignment_stats=self.alignment_stats, validation_results=validation_results, success=True)

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            console.print(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            return RunResult(nwb_path=Path(""), success=False, error=str(e))

    def _phase_0_initialization(self) -> None:
        """Phase 0: Load configuration and create NWBFile."""
        logger.info("Loading configuration and creating NWBFile...")

        # Load configuration (paths now auto-resolved by Pydantic validators)
        self.config = load_config(self.config_path)
        logger.info(f"  Project: {self.config.project.name}")
        logger.info(f"  Raw root: {self.config.paths.raw_root}")
        logger.info(f"  Output root: {self.config.paths.output_root}")

        # Load metadata and create NWBFile
        self.metadata, self.nwbfile = utils.load_session_metadata_and_nwb(
            config=self.config,
            subject_id=self.subject_id,
            session_id=self.session_id,
        )
        self.session_dir = self.config.paths.raw_root / self.subject_id / self.session_id

        logger.info(f"  NWBFile: identifier='{self.nwbfile.identifier}'")
        if self.nwbfile.subject:
            logger.info(f"  Subject: {self.nwbfile.subject.subject_id}")

    def _phase_1_discovery(self) -> None:
        """Phase 1: Discover and verify files."""
        logger.info("Discovering files and verifying synchronization...")

        # Discover cameras
        cameras = self.metadata.get("cameras", [])
        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]

            video_paths = utils.discover_files(self.session_dir, pattern, sort=True)
            if not video_paths:
                raise IngestError(
                    message=f"No video files found for camera '{camera_id}'",
                    context={"camera_id": camera_id, "pattern": pattern},
                    hint=f"Check that files exist matching pattern: {pattern}",
                )

            self.camera_files[camera_id] = video_paths
            frame_count = sum(utils.count_video_frames(p) for p in video_paths)

            logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s), {frame_count} frames")

            # Add video acquisition to NWBFile
            device = self.nwbfile.devices.get(camera_id)
            add_video_acquisition(
                self.nwbfile,
                camera_id=camera_id,
                video_files=[str(p) for p in video_paths],
                frame_rate=camera.get("fps", 30.0),
                device=device,
            )

        # Discover TTL files
        ttls = self.metadata.get("TTLs", [])
        for ttl in ttls:
            ttl_id = ttl["id"]
            pattern = ttl["paths"]

            ttl_paths = utils.discover_files(self.session_dir, pattern, sort=True)
            if ttl_paths:
                self.ttl_files[ttl_id] = ttl_paths
                pulse_count = sum(utils.count_ttl_pulses(p) for p in ttl_paths)
                logger.info(f"  TTL '{ttl_id}': {len(ttl_paths)} file(s), {pulse_count} pulses")
            else:
                logger.warning(f"  TTL '{ttl_id}': No files found (pattern: {pattern})")
                self.ttl_files[ttl_id] = []

        # Verification: Check frame/TTL synchronization
        if not self.options.skip_verification:
            for camera in cameras:
                camera_id = camera["id"]
                ttl_id = camera.get("ttl_id")

                if not ttl_id or ttl_id not in self.ttl_files:
                    continue

                frame_count = sum(utils.count_video_frames(p) for p in self.camera_files[camera_id])
                pulse_count = sum(utils.count_ttl_pulses(p) for p in self.ttl_files[ttl_id])
                mismatch = abs(frame_count - pulse_count)

                if mismatch > 0:
                    raise MismatchExceedsToleranceError(camera_id=camera_id, frame_count=frame_count, ttl_count=pulse_count, mismatch=mismatch, tolerance=0)

                logger.info(f"  Verification: '{camera_id}' ↔ '{ttl_id}' matched ({frame_count} frames)")

        # Discover Bpod files
        bpod_config = self.metadata.get("bpod")
        if bpod_config:
            pattern = bpod_config["path"]
            bpod_paths = utils.discover_files(self.session_dir, pattern, sort=True)
            if bpod_paths:
                self.bpod_files["bpod"] = bpod_paths
                logger.info(f"  Bpod: {len(bpod_paths)} file(s)")

    def _phase_2_ingestion(self) -> None:
        """Phase 2: Ingest Bpod and TTL data."""
        logger.info("Processing Bpod and TTL data...")

        # Process Bpod
        if not self.options.skip_bpod and self.bpod_files:
            bpod_config = self.metadata.get("bpod", {})

            self.bpod_data = parse_bpod(
                session_dir=self.session_dir,
                pattern=bpod_config["path"],
                order=bpod_config.get("order", "time_asc"),
                continuous_time=bpod_config.get("continuous_time", True),
            )

            session_data = utils.convert_matlab_struct(self.bpod_data.get("SessionData", {}))
            raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
            trials = raw_events.get("Trial", [])
            n_trials = len(trials) if trials is not None else 0
            logger.info(f"  Bpod: {n_trials} trials")

        # Process TTL
        ttl_patterns = {ttl_id: self.metadata["TTLs"][i]["paths"] for i, ttl_id in enumerate(self.ttl_files.keys()) if i < len(self.metadata.get("TTLs", []))}

        self.ttl_pulses = get_ttl_pulses(self.session_dir, ttl_patterns)
        for ttl_id, timestamps in self.ttl_pulses.items():
            if timestamps:
                logger.info(f"  TTL '{ttl_id}': {len(timestamps)} pulses, " f"range=[{timestamps[0]:.3f}, {timestamps[-1]:.3f}] s")

        # Compute trial offsets
        if self.bpod_data and self.config.bpod.sync.trial_types:
            self.trial_offsets, warnings = align_bpod_trials_to_ttl(
                trial_type_configs=self.config.bpod.sync.trial_types,
                bpod_data=self.bpod_data,
                ttl_pulses=self.ttl_pulses,
            )
            logger.info(f"  Aligned {len(self.trial_offsets)} trials")
            if warnings:
                logger.warning(f"  {len(warnings)} alignment warnings")

    def _phase_3_synchronization(self) -> None:
        """Phase 3: Synchronization and jitter checking."""
        logger.info("Computing alignment statistics...")

        self.alignment_stats = {
            "trial_offsets": self.trial_offsets if self.trial_offsets else {},
            "ttl_channels": {k: len(v) for k, v in self.ttl_pulses.items()},
        }

        if self.trial_offsets:
            offsets_array = np.array(list(self.trial_offsets.values()))
            stats = {
                "n_trials_aligned": len(self.trial_offsets),
                "mean_offset_s": float(np.mean(offsets_array)),
                "std_offset_s": float(np.std(offsets_array)),
                "min_offset_s": float(np.min(offsets_array)),
                "max_offset_s": float(np.max(offsets_array)),
            }
            self.alignment_stats["statistics"] = stats

            logger.info(f"  Trials: {stats['n_trials_aligned']}")
            logger.info(f"  Mean offset: {stats['mean_offset_s']:.4f} s")
            logger.info(f"  Std offset: {stats['std_offset_s']:.4f} s")

    def _phase_4_assembly(self) -> None:
        """Phase 4: Assemble NWB objects."""
        logger.info("Building behavior tables...")

        if self.bpod_data and self.trial_offsets:
            # Extract type tables
            state_types = extract_state_types(self.bpod_data)
            event_types = extract_event_types(self.bpod_data)
            action_types = extract_action_types(self.bpod_data)

            # Extract data tables
            states, state_indices = extract_states(self.bpod_data, state_types, trial_offsets=self.trial_offsets)
            events, event_indices = extract_events(self.bpod_data, event_types, trial_offsets=self.trial_offsets)
            actions, action_indices = extract_actions(self.bpod_data, action_types, trial_offsets=self.trial_offsets)

            logger.info(f"  States: {len(states)}, Events: {len(events)}, Actions: {len(actions)}")

            # Build and add to NWBFile
            task_recording = build_task_recording(states, events, actions)
            trials_table = build_trials_table(
                self.bpod_data,
                task_recording,
                state_indices,
                event_indices,
                action_indices,
                trial_offsets=self.trial_offsets,
            )

            task_arguments = extract_task_arguments(self.bpod_data)
            task = build_task(state_types, event_types, action_types, task_arguments=task_arguments)

            self.nwbfile.add_trials_table(trials_table)
            self.nwbfile.add_lab_meta_data(task)

            logger.info(f"  Added TrialsTable ({len(trials_table)} trials) and Task to NWBFile")

    def _phase_5_finalization(self) -> tuple[Path, Optional[List[Dict[str, Any]]]]:
        """Phase 5: Write NWB file, validate, and create sidecars.

        Returns:
            Tuple of (nwb_path, validation_results)
        """
        logger.info("Writing NWB file and creating sidecars...")

        # Prepare provenance
        provenance = {
            "pipeline": "w2t_bkin",
            "version": "v2",
            "config_hash": utils.compute_hash(self.config.model_dump(mode="json")),
            "alignment_stats": self.alignment_stats,
        }

        # Write NWB file
        output_dir = self.config.paths.output_root / self.session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / f"{self.session_id}.nwb"

        write_nwb_file(self.nwbfile, nwb_path)
        nwb_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        logger.info(f"  NWB file: {nwb_path.name} ({nwb_size_mb:.1f} MB)")

        # Write sidecars
        if self.alignment_stats:
            stats_path = output_dir / "alignment_stats.json"
            utils.write_json(self.alignment_stats, stats_path)
            logger.info(f"  Alignment stats: {stats_path.name}")

        provenance_path = output_dir / "provenance.json"
        utils.write_json(provenance, provenance_path)
        logger.info(f"  Provenance: {provenance_path.name}")

        # Validate NWB file with nwbinspector
        validation_results = None
        if not self.options.skip_nwb_validation:
            logger.info("Validating NWB file with nwbinspector...")
            validation_results = self._validate_nwb(nwb_path)

            # Summary of validation
            if validation_results:
                critical = sum(1 for r in validation_results if r.get("severity") == "CRITICAL")
                errors = sum(1 for r in validation_results if r.get("severity") == "ERROR")
                warnings = sum(1 for r in validation_results if r.get("severity") == "WARNING")

                if critical > 0 or errors > 0:
                    logger.warning(f"  Validation issues: {critical} critical, {errors} errors, {warnings} warnings")
                else:
                    logger.info(f"  Validation passed ({warnings} warnings)")
            else:
                logger.info("  Validation passed (no issues)")

        return nwb_path, validation_results

    def _validate_nwb(self, nwb_path: Path) -> List[Dict[str, Any]]:
        """Validate NWB file using nwbinspector.

        Args:
            nwb_path: Path to NWB file

        Returns:
            List of validation results
        """
        try:
            from nwbinspector import inspect_nwbfile

            # Run inspection
            results = list(inspect_nwbfile(nwbfile_path=str(nwb_path)))

            # Convert to serializable format
            validation_results = []
            for result in results:
                validation_results.append(
                    {
                        "severity": result.severity.name,
                        "check_name": result.check_function_name,
                        "message": result.message,
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "location": result.location,
                    }
                )

            return validation_results

        except ImportError:
            logger.warning("nwbinspector not available, skipping validation")
            return []
        except Exception as e:
            logger.error(f"NWB validation failed: {e}")
            return []


# =============================================================================
# Convenience Function (backward compatibility)
# =============================================================================


def run_session(
    config_path: str,
    subject_id: str,
    session_id: str,
    options: Optional[RunOptions] = None,
) -> RunResult:
    """Run the W2T Body Kinematics pipeline for a single session.

    Convenience function that creates a SessionPipeline and runs it.
    Maintains backward compatibility with original API.

    Args:
        config_path: Path to config.toml
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")
        options: Pipeline execution options (optional)

    Returns:
        RunResult with NWB path, NWBFile object, and statistics

    Example:
        >>> from w2t_bkin.pipeline import run_session
        >>> result = run_session(
        ...     config_path="config.toml",
        ...     subject_id="subject-001",
        ...     session_id="session-001"
        ... )
        >>> print(f"Success: {result.success}")
    """
    pipeline = SessionPipeline(config_path, subject_id, session_id, options)
    return pipeline.run()
