"""Pipeline orchestration for W2T Body Kinematics.

This module implements the high-level pipeline orchestration following a
7-phase workflow with improvements:

- Class-based orchestrator (SessionPipeline) for state management
- Rich logging with progress bars and formatted output
- NWB validation with nwbinspector
- Centralized path logic in config validators
- Typer CLI for enhanced command-line interface
- Preprocessing phase for intermediate artifact generation

Phase 0: Initialization - Load config, create NWBFile
Phase 1: Discovery & Verification - Find files, verify consistency
Phase 2: Preprocessing - Generate intermediate artifacts (e.g., DLC pose)
Phase 3: Ingestion - Process Bpod, Pose, TTL data
Phase 4: Synchronization - Align data streams to reference timeline
Phase 5: Assembly - Add all objects to NWBFile
Phase 6: Finalization - Write NWB file, validate, and create sidecars

Architecture:
- SessionPipeline class encapsulates config, metadata, and nwbfile
- Rich console for beautiful progress tracking and logging
- Typer for CLI commands: run, validate, inspect
- In-memory NWB → Atomic write → Validation strategy
- Task-based preprocessing with dependency checking and caching

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
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from . import session, validate
from .. import config as config_pkg
from .. import sync, utils
from ..exceptions import IngestError, MismatchExceedsToleranceError, SyncError
from ..ingest import behavior, bpod, ttl

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
    verification_tolerance: Optional[int] = None
    warn_on_mismatch: Optional[bool] = None


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
    nwb_path: Optional[Path] = None
    validation_results: Optional[List[Dict[str, Any]]] = None


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
                self._phase_0_initialization(self.context, progress, task)
                progress.update(task, completed=1)

                # Phase 1: Discovery & Verification
                task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=None)
                self._phase_1_discovery(self.context, progress, task)

                # Phase 2: Preprocessing
                task = progress.add_task("[cyan]Phase 2: Preprocessing", total=None)
                self._phase_2_preprocessing(self.context, progress, task)

                # Phase 3: Ingestion
                task = progress.add_task("[cyan]Phase 3: Ingestion", total=None)
                self._phase_3_ingestion(self.context, progress, task)

                # Phase 4: Synchronization
                task = progress.add_task("[cyan]Phase 4: Synchronization", total=1)
                self._phase_4_synchronization(self.context, progress, task)
                progress.update(task, completed=1)

                # Phase 5: Assembly
                task = progress.add_task("[cyan]Phase 5: Assembly", total=None)
                self._phase_5_assembly(self.context, progress, task)

                # Phase 6: Finalization
                task = progress.add_task("[cyan]Phase 6: Finalization & Validation", total=None)
                self._phase_6_finalization(self.context, progress, task)

            console.print("\n[bold green]✓ Pipeline completed successfully[/bold green]")

            return RunResult(
                nwb_path=self.context.nwb_path or Path(""),
                nwbfile=self.context.nwbfile,
                alignment_stats=self.context.alignment_stats,
                validation_results=self.context.validation_results,
                success=True,
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            console.print(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            return RunResult(nwb_path=Path(""), success=False, error=str(e))

    def _phase_0_initialization(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 0: Load configuration and create NWBFile."""
        logger.info("Loading configuration and creating NWBFile...")
        logger.debug(f"Config path: {context.config_path}")

        # Load configuration (paths now auto-resolved by Pydantic validators)
        context.config = config_pkg.load_config(context.config_path)

        # Apply CLI overrides
        if context.options.verification_tolerance is not None:
            context.config.verification.mismatch_tolerance_frames = context.options.verification_tolerance
            logger.info(f"  Overriding verification tolerance: {context.options.verification_tolerance}")

        if context.options.warn_on_mismatch is not None:
            context.config.verification.warn_on_mismatch = context.options.warn_on_mismatch
            logger.info(f"  Overriding warn_on_mismatch: {context.options.warn_on_mismatch}")

        logger.info(f"  Project: {context.config.project.name}")
        logger.info(f"  Raw root: {context.config.paths.raw_root}")
        logger.info(f"  Output root: {context.config.paths.output_root}")
        logger.debug(f"  Full config: {context.config.model_dump_json(indent=2)}")

        # Load metadata and create NWBFile
        context.metadata, context.nwbfile = utils.load_session_metadata_and_nwb(
            config=context.config,
            subject_id=context.subject_id,
            session_id=context.session_id,
        )
        context.session_dir = context.config.paths.raw_root / context.subject_id / context.session_id
        logger.debug(f"  Session directory: {context.session_dir}")

        logger.info(f"  NWBFile: identifier='{context.nwbfile.identifier}'")
        if context.nwbfile.subject:
            logger.info(f"  Subject: {context.nwbfile.subject.subject_id}")
            logger.debug(f"  Subject metadata: {context.nwbfile.subject}")

    def _phase_1_discovery(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 1: Discover and verify files."""
        logger.info("Discovering files and verifying synchronization...")

        # Discover cameras
        cameras = context.metadata.get("cameras", [])
        ttls = context.metadata.get("TTLs", [])
        bpod_config = context.metadata.get("bpod")

        # Calculate total steps
        total_steps = len(cameras) + len(ttls)
        if not context.options.skip_verification:
            total_steps += 1
        if bpod_config:
            total_steps += 1

        if progress and task_id is not None:
            progress.update(task_id, total=total_steps)

        logger.debug(f"Searching for {len(cameras)} camera(s)")

        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]
            logger.debug(f"  Scanning camera '{camera_id}' with pattern: {pattern}")

            video_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if not video_paths:
                logger.error(f"No video files found for camera '{camera_id}'")
                raise IngestError(
                    message=f"No video files found for camera '{camera_id}'",
                    context={"camera_id": camera_id, "pattern": pattern},
                    hint=f"Check that files exist matching pattern: {pattern}",
                )

            context.camera_files[camera_id] = video_paths
            frame_count = sum(utils.count_video_frames(p) for p in video_paths)

            logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s), {frame_count} frames")
            logger.debug(f"    Files: {[p.name for p in video_paths]}")

            # Add video acquisition to NWBFile
            device = context.nwbfile.devices.get(camera_id)
            if device:
                logger.debug(f"    Linked to device: {device.name}")
            else:
                logger.warning(f"    Device '{camera_id}' not found in NWBFile devices")

            # Determine frame rate with warning if missing
            fps = camera.get("fps")
            if fps is None:
                logger.warning(f"    Camera '{camera_id}': 'fps' not configured in metadata, defaulting to 30.0 Hz")
                fps = 30.0
            else:
                logger.debug(f"    Camera '{camera_id}': configured fps={fps} Hz")

            session.add_video_acquisition(
                context.nwbfile,
                camera_id=camera_id,
                video_files=[str(p) for p in video_paths],
                frame_rate=fps,
                device=device,
            )

            if progress and task_id is not None:
                progress.advance(task_id)

        # Discover TTL files
        logger.debug(f"Searching for {len(ttls)} TTL source(s)")

        for ttl in ttls:
            ttl_id = ttl["id"]
            pattern = ttl["paths"]
            logger.debug(f"  Scanning TTL '{ttl_id}' with pattern: {pattern}")

            ttl_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if ttl_paths:
                context.ttl_files[ttl_id] = ttl_paths
                pulse_count = sum(utils.count_ttl_pulses(p) for p in ttl_paths)
                logger.info(f"  TTL '{ttl_id}': {len(ttl_paths)} file(s), {pulse_count} pulses")
                logger.debug(f"    Files: {[p.name for p in ttl_paths]}")
            else:
                logger.warning(f"  TTL '{ttl_id}': No files found (pattern: {pattern})")
                context.ttl_files[ttl_id] = []

            if progress and task_id is not None:
                progress.advance(task_id)

        # Verification: Check frame/TTL synchronization
        if not context.options.skip_verification:
            logger.debug("Verifying synchronization between cameras and TTLs...")
            for camera in cameras:
                camera_id = camera["id"]
                ttl_id = camera.get("ttl_id")

                if not ttl_id:
                    logger.debug(f"  Skipping verification for '{camera_id}' (no ttl_id configured)")
                    continue

                if ttl_id not in context.ttl_files:
                    logger.warning(f"  Skipping verification for '{camera_id}': TTL source '{ttl_id}' not found")
                    continue

                frame_count = sum(utils.count_video_frames(p) for p in context.camera_files[camera_id])
                pulse_count = sum(utils.count_ttl_pulses(p) for p in context.ttl_files[ttl_id])

                logger.debug(f"  Verifying '{camera_id}' ({frame_count} frames) vs '{ttl_id}' ({pulse_count} pulses)")

                try:
                    validate.verify_synchronization(
                        camera_id=camera_id,
                        ttl_id=ttl_id,
                        frame_count=frame_count,
                        pulse_count=pulse_count,
                        tolerance=context.config.verification.mismatch_tolerance_frames,
                    )
                except MismatchExceedsToleranceError as e:
                    if context.config.verification.warn_on_mismatch:
                        logger.warning(f"  Synchronization mismatch (warning only): {e}")
                    else:
                        raise

            if progress and task_id is not None:
                progress.advance(task_id)
        else:
            logger.info("Skipping synchronization verification (requested by options)")

        # Discover Bpod files
        if bpod_config:
            pattern = bpod_config["path"]
            logger.debug(f"Scanning Bpod with pattern: {pattern}")
            bpod_paths = utils.discover_files(context.session_dir, pattern, sort=True)
            if bpod_paths:
                context.bpod_files["bpod"] = bpod_paths
                logger.info(f"  Bpod: {len(bpod_paths)} file(s)")
                logger.debug(f"    Files: {[p.name for p in bpod_paths]}")
            else:
                logger.warning(f"  Bpod: No files found (pattern: {pattern})")

            if progress and task_id is not None:
                progress.advance(task_id)

    def _phase_2_preprocessing(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 2: Execute preprocessing tasks to generate intermediate artifacts."""
        logger.info("Running preprocessing tasks...")

        if progress and task_id is not None:
            progress.update(task_id, total=1)

        # Import task framework
        from ..tasks import DLCPoseTask, TaskConfig
        from ..tasks.base import TaskStatus

        # Create interim directory structure
        interim_dir = context.config.paths.intermediate_root / context.session_id
        interim_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Interim directory: {interim_dir}")

        # Build task configuration
        task_config = TaskConfig(
            enabled=context.config.preprocessing.dlc.enabled,
            force_rerun=context.config.preprocessing.force_rerun,
            session_dir=context.session_dir,
            interim_dir=interim_dir,
            metadata=context.metadata,
            config=context.config,
        )

        # Execute DLC preprocessing if enabled
        if context.config.preprocessing.dlc.enabled:
            logger.info("  DLC pose estimation enabled")
            dlc_task = DLCPoseTask(task_config)

            # Run task with full lifecycle (check deps, check output, execute if needed)
            status = dlc_task.run()

            if status == TaskStatus.COMPLETED:
                logger.info("  DLC: Completed successfully")
            elif status == TaskStatus.CACHED:
                logger.info("  DLC: Using cached results from interim folder")
            elif status == TaskStatus.SKIP:
                logger.info("  DLC: Skipped (dependencies not met or disabled)")
            elif status == TaskStatus.FAILED:
                logger.error("  DLC: Task failed")
                raise IngestError(
                    message="DLC preprocessing task failed",
                    context={"task": "DLCPoseTask", "status": status.name},
                    hint="Check DLC model configuration and video files",
                )
        else:
            logger.info("  DLC pose estimation disabled")

        if progress and task_id is not None:
            progress.advance(task_id)

    def _phase_3_ingestion(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 3: Ingest Bpod and TTL data."""
        logger.info("Processing Bpod and TTL data...")

        total_steps = 3
        if progress and task_id is not None:
            progress.update(task_id, total=total_steps)

        # Process Bpod
        if not context.options.skip_bpod and context.bpod_files:
            bpod_config = context.metadata.get("bpod", {})
            logger.debug(f"Parsing Bpod data (order={bpod_config.get('order')}, continuous={bpod_config.get('continuous_time')})")

            context.bpod_data = bpod.parse_bpod(
                session_dir=context.session_dir,
                pattern=bpod_config["path"],
                order=bpod_config.get("order", "time_asc"),
                continuous_time=bpod_config.get("continuous_time", False),
            )

            session_data = utils.convert_matlab_struct(context.bpod_data.get("SessionData", {}))
            raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
            trials = raw_events.get("Trial", [])
            n_trials = len(trials) if trials is not None else 0
            logger.info(f"  Bpod: {n_trials} trials")
            logger.debug(f"    SessionData keys: {list(session_data.keys())}")
        elif context.options.skip_bpod:
            logger.info("Skipping Bpod processing (requested by options)")

        if progress and task_id is not None:
            progress.advance(task_id)

        # Process TTL
        ttl_patterns = {ttl_id: context.metadata["TTLs"][i]["paths"] for i, ttl_id in enumerate(context.ttl_files.keys()) if i < len(context.metadata.get("TTLs", []))}

        context.ttl_pulses = ttl.get_ttl_pulses(context.session_dir, ttl_patterns)
        for ttl_id, timestamps in context.ttl_pulses.items():
            if timestamps:
                logger.info(f"  TTL '{ttl_id}': {len(timestamps)} pulses, " f"range=[{timestamps[0]:.3f}, {timestamps[-1]:.3f}] s")
                if len(timestamps) > 0:
                    logger.debug(f"    First 5 timestamps: {timestamps[:5]}")
            else:
                logger.warning(f"  TTL '{ttl_id}': No pulses extracted")

        if progress and task_id is not None:
            progress.advance(task_id)

        # Compute trial offsets
        if context.bpod_data and context.config.bpod.sync.trial_types:
            logger.debug("Aligning Bpod trials to TTL pulses...")
            context.trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
                trial_type_configs=context.config.bpod.sync.trial_types,
                bpod_data=context.bpod_data,
                ttl_pulses=context.ttl_pulses,
            )
            logger.info(f"  Aligned {len(context.trial_offsets)} trials")
            if warnings:
                logger.warning(f"  {len(warnings)} alignment warnings")
                for w in warnings[:5]:  # Show first 5 warnings
                    logger.debug(f"    Warning: {w}")
                if len(warnings) > 5:
                    logger.debug(f"    ... and {len(warnings) - 5} more")
        else:
            logger.debug("Skipping trial alignment (missing Bpod data or sync config)")

        if progress and task_id is not None:
            progress.advance(task_id)

    def _phase_4_synchronization(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 4: Synchronization and jitter checking."""
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
            logger.debug(f"  Offset range: [{stats['min_offset_s']:.4f}, {stats['max_offset_s']:.4f}] s")
        else:
            logger.warning("  No trial offsets computed - synchronization statistics are empty")

    def _phase_5_assembly(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 5: Assemble NWB objects."""
        logger.info("Building behavior tables...")

        total_steps = 3
        if progress and task_id is not None:
            progress.update(task_id, total=total_steps)

        if context.bpod_data and context.trial_offsets:
            # Extract type tables
            logger.debug("Extracting state, event, and action types...")
            state_types = behavior.extract_state_types(context.bpod_data)
            event_types = behavior.extract_event_types(context.bpod_data)
            action_types = behavior.extract_action_types(context.bpod_data)
            logger.debug(f"  Found {len(state_types)} state types, {len(event_types)} event types, {len(action_types)} action types")

            if progress and task_id is not None:
                progress.advance(task_id)

            # Extract data tables
            logger.debug("Extracting trial data...")
            states, state_indices = behavior.extract_states(context.bpod_data, state_types, trial_offsets=context.trial_offsets)
            events, event_indices = behavior.extract_events(context.bpod_data, event_types, trial_offsets=context.trial_offsets)
            actions, action_indices = behavior.extract_actions(context.bpod_data, action_types, trial_offsets=context.trial_offsets)

            logger.info(f"  States: {len(states)}, Events: {len(events)}, Actions: {len(actions)}")

            if progress and task_id is not None:
                progress.advance(task_id)

            # Build and add to NWBFile
            logger.debug("Building NWB tables...")
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

            context.nwbfile.trials = trials_table
            context.nwbfile.add_acquisition(task_recording)
            context.nwbfile.add_lab_meta_data(task)

            logger.info(f"  Added TrialsTable ({len(trials_table)} trials), TaskRecording, and Task to NWBFile")

            if progress and task_id is not None:
                progress.advance(task_id)
        else:
            logger.warning("Skipping behavior table assembly (missing Bpod data or trial offsets)")
            if progress and task_id is not None:
                progress.update(task_id, completed=total_steps)

    def _phase_6_finalization(self, context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
        """Phase 6: Write NWB, validate, and create sidecars."""
        logger.info("Writing NWB file and creating sidecars...")

        total_steps = 3
        if progress and task_id is not None:
            progress.update(task_id, total=total_steps)

        # Prepare provenance
        provenance = {
            "pipeline": "w2t_bkin",
            "version": "v2",
            "config_hash": utils.compute_hash(context.config.model_dump(mode="json")),
            "alignment_stats": context.alignment_stats,
        }
        logger.debug(f"Provenance data prepared: {list(provenance.keys())}")

        # Write NWB file
        output_dir = context.config.paths.output_root / context.subject_id / context.session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / f"{context.session_id}.nwb"

        logger.debug(f"Writing NWB file to: {nwb_path}")
        session.write_nwb_file(context.nwbfile, nwb_path)
        context.nwb_path = nwb_path
        nwb_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        logger.info(f"  NWB file: {nwb_path.name} ({nwb_size_mb:.1f} MB)")

        if progress and task_id is not None:
            progress.advance(task_id)

        # Write sidecars
        if context.alignment_stats:
            stats_path = output_dir / "alignment_stats.json"
            utils.write_json(context.alignment_stats, stats_path)
            logger.info(f"  Alignment stats: {stats_path.name}")
        else:
            logger.debug("Skipping alignment stats sidecar (empty stats)")

        provenance_path = output_dir / "provenance.json"
        utils.write_json(provenance, provenance_path)
        logger.info(f"  Provenance: {provenance_path.name}")

        if progress and task_id is not None:
            progress.advance(task_id)

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
                    for r in validation_results:
                        if r.get("severity") in ["CRITICAL", "ERROR"]:
                            logger.debug(f"    {r.get('severity')}: {r.get('message')}")
                else:
                    logger.info(f"  Validation passed ({warnings} warnings)")
                    if warnings > 0:
                        logger.debug(f"    {warnings} warnings found (check validation report)")
            else:
                logger.info("  Validation passed (no issues)")
        else:
            logger.info("Skipping NWB validation (requested by options)")

        context.validation_results = validation_results

        if progress and task_id is not None:
            progress.advance(task_id)
