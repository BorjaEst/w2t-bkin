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

from . import behavior, bpod
from . import config as config_pkg
from . import session, sync, ttl, utils, validate
from .exceptions import IngestError, SyncError

# Setup rich console and logging
console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(console=console, rich_tracebacks=True)])
logger = logging.getLogger(__name__)


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


@dataclass
class PipelineContext:
    """Context holding the state of a pipeline execution.

    This object is passed between pipeline phases and accumulates state.
    It is designed to be serializable for distributed execution.
    """

    # Inputs
    config_path: Path
    subject_id: str
    session_id: str
    options: RunOptions

    # State variables (populated during phases)
    config: Optional[config_pkg.Config] = None
    metadata: Optional[Dict[str, Any]] = None
    nwbfile: Optional[NWBFile] = None
    session_dir: Optional[Path] = None

    # Intermediate results
    camera_files: Dict[str, List[Path]] = field(default_factory=dict)
    bpod_files: Dict[str, List[Path]] = field(default_factory=dict)
    ttl_files: Dict[str, List[Path]] = field(default_factory=dict)
    bpod_data: Optional[Dict[str, Any]] = None
    trial_offsets: Optional[Dict[int, float]] = None
    ttl_pulses: Dict[str, List[float]] = field(default_factory=dict)
    alignment_stats: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SessionPipeline Class
# =============================================================================


class SessionPipeline:
    """Session-level pipeline orchestrator.

    Encapsulates configuration, metadata, and NWBFile state for a single
    session processing run. Provides methods for each pipeline phase and
    orchestrates the complete workflow.

    Attributes:
        context: PipelineContext holding all session state
    """

    def __init__(self, config_path: str | Path, subject_id: str, session_id: str, options: Optional[RunOptions] = None):
        """Initialize pipeline for a session.

        Args:
            config_path: Path to config.toml
            subject_id: Subject identifier (e.g., "subject-001")
            session_id: Session identifier (e.g., "session-001")
            options: Pipeline execution options (optional)
        """
        self.context = PipelineContext(
            config_path=Path(config_path),
            subject_id=subject_id,
            session_id=session_id,
            options=options or RunOptions(),
        )

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
                f"Subject: [yellow]{self.context.subject_id}[/yellow]\n"
                f"Session: [yellow]{self.context.session_id}[/yellow]\n"
                f"Config: [dim]{self.context.config_path}[/dim]",
                border_style="cyan",
            )
        )

        try:
            columns = SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeRemainingColumn()
            with Progress(*columns, console=console) as progress:

                # Phase 0: Initialization
                task = progress.add_task("[cyan]Phase 0: Initialization", total=1)
                self._phase_0_initialization(self.context)
                progress.update(task, advance=1)

                # Phase 1: Discovery & Verification
                task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=1)
                self._phase_1_discovery(self.context)
                progress.update(task, advance=1)

                # Phase 2: Ingestion
                task = progress.add_task("[cyan]Phase 2: Ingestion", total=1)
                self._phase_2_ingestion(self.context)
                progress.update(task, advance=1)

                # Phase 3: Synchronization
                task = progress.add_task("[cyan]Phase 3: Synchronization", total=1)
                self._phase_3_synchronization(self.context)
                progress.update(task, advance=1)

                # Phase 4: Assembly
                task = progress.add_task("[cyan]Phase 4: Assembly", total=1)
                self._phase_4_assembly(self.context)
                progress.update(task, advance=1)

                # Phase 5: Finalization
                task = progress.add_task("[cyan]Phase 5: Finalization & Validation", total=1)
                nwb_path, validation_results = self._phase_5_finalization(self.context)
                progress.update(task, advance=1)

            console.print("\n[bold green]✓ Pipeline completed successfully[/bold green]")

            return RunResult(
                nwb_path=nwb_path,
                nwbfile=self.context.nwbfile,
                alignment_stats=self.context.alignment_stats,
                validation_results=validation_results,
                success=True,
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            console.print(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            return RunResult(nwb_path=Path(""), success=False, error=str(e))

    def _phase_0_initialization(self, context: PipelineContext) -> None:
        """Phase 0: Load configuration and create NWBFile."""
        logger.info("Loading configuration and creating NWBFile...")

        # Load configuration (paths now auto-resolved by Pydantic validators)
        context.config = config_pkg.load_config(context.config_path)
        logger.info(f"  Project: {context.config.project.name}")
        logger.info(f"  Raw root: {context.config.paths.raw_root}")
        logger.info(f"  Output root: {context.config.paths.output_root}")

        # Load metadata and create NWBFile
        context.metadata, context.nwbfile = utils.load_session_metadata_and_nwb(
            config=context.config,
            subject_id=context.subject_id,
            session_id=context.session_id,
        )
        context.session_dir = context.config.paths.raw_root / context.subject_id / context.session_id

        logger.info(f"  NWBFile: identifier='{context.nwbfile.identifier}'")
        if context.nwbfile.subject:
            logger.info(f"  Subject: {context.nwbfile.subject.subject_id}")

    def _phase_1_discovery(self, context: PipelineContext) -> None:
        """Phase 1: Discover and verify files."""
        logger.info("Discovering files and verifying synchronization...")

        # Discover cameras
        cameras = context.metadata.get("cameras", [])
        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]

            video_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if not video_paths:
                raise IngestError(
                    message=f"No video files found for camera '{camera_id}'",
                    context={"camera_id": camera_id, "pattern": pattern},
                    hint=f"Check that files exist matching pattern: {pattern}",
                )

            context.camera_files[camera_id] = video_paths
            frame_count = sum(utils.count_video_frames(p) for p in video_paths)

            logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s), {frame_count} frames")

            # Add video acquisition to NWBFile
            device = context.nwbfile.devices.get(camera_id)
            session.add_video_acquisition(
                context.nwbfile,
                camera_id=camera_id,
                video_files=[str(p) for p in video_paths],
                frame_rate=camera.get("fps", 30.0),
                device=device,
            )

        # Discover TTL files
        ttls = context.metadata.get("TTLs", [])
        for ttl in ttls:
            ttl_id = ttl["id"]
            pattern = ttl["paths"]

            ttl_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if ttl_paths:
                context.ttl_files[ttl_id] = ttl_paths
                pulse_count = sum(utils.count_ttl_pulses(p) for p in ttl_paths)
                logger.info(f"  TTL '{ttl_id}': {len(ttl_paths)} file(s), {pulse_count} pulses")
            else:
                logger.warning(f"  TTL '{ttl_id}': No files found (pattern: {pattern})")
                context.ttl_files[ttl_id] = []

        # Verification: Check frame/TTL synchronization
        if not context.options.skip_verification:
            for camera in cameras:
                camera_id = camera["id"]
                ttl_id = camera.get("ttl_id")

                if not ttl_id or ttl_id not in context.ttl_files:
                    continue

                frame_count = sum(utils.count_video_frames(p) for p in context.camera_files[camera_id])
                pulse_count = sum(utils.count_ttl_pulses(p) for p in context.ttl_files[ttl_id])

                validate.verify_synchronization(
                    camera_id=camera_id,
                    ttl_id=ttl_id,
                    frame_count=frame_count,
                    pulse_count=pulse_count,
                    tolerance=0,
                )

        # Discover Bpod files
        bpod_config = context.metadata.get("bpod")
        if bpod_config:
            pattern = bpod_config["path"]
            bpod_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if bpod_paths:
                context.bpod_files["bpod"] = bpod_paths
                logger.info(f"  Bpod: {len(bpod_paths)} file(s)")

    def _phase_2_ingestion(self, context: PipelineContext) -> None:
        """Phase 2: Ingest Bpod and TTL data."""
        logger.info("Processing Bpod and TTL data...")

        # Process Bpod
        if not context.options.skip_bpod and context.bpod_files:
            bpod_config = context.metadata.get("bpod", {})

            context.bpod_data = bpod.parse_bpod(
                session_dir=context.session_dir,
                pattern=bpod_config["path"],
                order=bpod_config.get("order", "time_asc"),
                continuous_time=bpod_config.get("continuous_time", True),
            )

            session_data = utils.convert_matlab_struct(context.bpod_data.get("SessionData", {}))
            raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
            trials = raw_events.get("Trial", [])
            n_trials = len(trials) if trials is not None else 0
            logger.info(f"  Bpod: {n_trials} trials")

        # Process TTL
        ttl_patterns = {ttl_id: context.metadata["TTLs"][i]["paths"] for i, ttl_id in enumerate(context.ttl_files.keys()) if i < len(context.metadata.get("TTLs", []))}

        context.ttl_pulses = ttl.get_ttl_pulses(context.session_dir, ttl_patterns)
        for ttl_id, timestamps in context.ttl_pulses.items():
            if timestamps:
                logger.info(f"  TTL '{ttl_id}': {len(timestamps)} pulses, " f"range=[{timestamps[0]:.3f}, {timestamps[-1]:.3f}] s")

        # Compute trial offsets
        if context.bpod_data and context.config.bpod.sync.trial_types:
            context.trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
                trial_type_configs=context.config.bpod.sync.trial_types,
                bpod_data=context.bpod_data,
                ttl_pulses=context.ttl_pulses,
            )
            logger.info(f"  Aligned {len(context.trial_offsets)} trials")
            if warnings:
                logger.warning(f"  {len(warnings)} alignment warnings")

    def _phase_3_synchronization(self, context: PipelineContext) -> None:
        """Phase 3: Synchronization and jitter checking."""
        logger.info("Computing alignment statistics...")

        context.alignment_stats = {
            "trial_offsets": context.trial_offsets if context.trial_offsets else {},
            "ttl_channels": {k: len(v) for k, v in context.ttl_pulses.items()},
        }

        if context.trial_offsets:
            offsets_array = np.array(list(context.trial_offsets.values()))
            stats = {
                "n_trials_aligned": len(context.trial_offsets),
                "mean_offset_s": float(np.mean(offsets_array)),
                "std_offset_s": float(np.std(offsets_array)),
                "min_offset_s": float(np.min(offsets_array)),
                "max_offset_s": float(np.max(offsets_array)),
            }
            context.alignment_stats["statistics"] = stats

            logger.info(f"  Trials: {stats['n_trials_aligned']}")
            logger.info(f"  Mean offset: {stats['mean_offset_s']:.4f} s")
            logger.info(f"  Std offset: {stats['std_offset_s']:.4f} s")

    def _phase_4_assembly(self, context: PipelineContext) -> None:
        """Phase 4: Assemble NWB objects."""
        logger.info("Building behavior tables...")

        if context.bpod_data and context.trial_offsets:
            # Extract type tables
            state_types = behavior.extract_state_types(context.bpod_data)
            event_types = behavior.extract_event_types(context.bpod_data)
            action_types = behavior.extract_action_types(context.bpod_data)

            # Extract data tables
            states, state_indices = behavior.extract_states(context.bpod_data, state_types, trial_offsets=context.trial_offsets)
            events, event_indices = behavior.extract_events(context.bpod_data, event_types, trial_offsets=context.trial_offsets)
            actions, action_indices = behavior.extract_actions(context.bpod_data, action_types, trial_offsets=context.trial_offsets)

            logger.info(f"  States: {len(states)}, Events: {len(events)}, Actions: {len(actions)}")

            # Build and add to NWBFile
            task_recording = behavior.build_task_recording(states, events, actions)
            trials_table = behavior.build_trials_table(
                context.bpod_data,
                task_recording,
                state_indices,
                event_indices,
                action_indices,
                trial_offsets=context.trial_offsets,
            )

            task_arguments = behavior.extract_task_arguments(context.bpod_data)
            task = behavior.build_task(state_types, event_types, action_types, task_arguments=task_arguments)

            context.nwbfile.add_trials_table(trials_table)
            context.nwbfile.add_lab_meta_data(task)

            logger.info(f"  Added TrialsTable ({len(trials_table)} trials) and Task to NWBFile")

    def _phase_5_finalization(self, context: PipelineContext) -> tuple[Path, Optional[List[Dict[str, Any]]]]:
        """Phase 5: Write NWB file, validate, and create sidecars.

        Returns:
            Tuple of (nwb_path, validation_results)
        """
        logger.info("Writing NWB file and creating sidecars...")

        # Prepare provenance
        provenance = {
            "pipeline": "w2t_bkin",
            "version": "v2",
            "config_hash": utils.compute_hash(context.config.model_dump(mode="json")),
            "alignment_stats": context.alignment_stats,
        }

        # Write NWB file
        output_dir = context.config.paths.output_root / context.subject_id / context.session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / f"{context.session_id}.nwb"

        session.write_nwb_file(context.nwbfile, nwb_path)
        nwb_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        logger.info(f"  NWB file: {nwb_path.name} ({nwb_size_mb:.1f} MB)")

        # Write sidecars
        if context.alignment_stats:
            stats_path = output_dir / "alignment_stats.json"
            utils.write_json(context.alignment_stats, stats_path)
            logger.info(f"  Alignment stats: {stats_path.name}")

        provenance_path = output_dir / "provenance.json"
        utils.write_json(provenance, provenance_path)
        logger.info(f"  Provenance: {provenance_path.name}")

        # Validate NWB file with nwbinspector
        validation_results = None
        if not context.options.skip_nwb_validation:
            logger.info("Validating NWB file with nwbinspector...")
            validation_results = validate.validate_nwb_file(nwb_path)

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
