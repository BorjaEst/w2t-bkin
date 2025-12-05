"""Pipeline orchestration for W2T Body Kinematics.

This module implements the high-level pipeline orchestration following a
7-phase workflow with improvements:

- Class-based orchestrator (SessionPipeline) for state management
- Rich logging with progress bars and formatted output
- NWB validation with nwbinspector
- Centralized path logic in config validators
- Typer CLI for enhanced command-line interface
- Preprocessing phase for intermediate artifact generation
- Built-in profiling and diagnostic figure generation

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
- Automatic profiling with timing and diagnostic figures

Example:
    >>> from w2t_bkin.core.pipeline import SessionPipeline
    >>>
    >>> pipeline = SessionPipeline(
    ...     config_path="config.toml",
    ...     subject_id="subject-001",
    ...     session_id="session-001"
    ... )
    >>> result = pipeline.run()
    >>> print(f"NWB written to: {result.nwb_path}")
"""

import json
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

from ...figures.profiling import (
    PhaseTimer,
    PipelineProfile,
    plot_pipeline_execution,
    plot_sync_quality_and_completeness,
    plot_synchronization_stats,
    plot_ttl_inter_pulse_intervals,
)
from .models import PipelineContext, RunOptions, RunResult
from .phases.assembly import run_phase_5
from .phases.discovery import run_phase_1
from .phases.finalization import run_phase_6
from .phases.ingestion import run_phase_3
from .phases.initialization import run_phase_0
from .phases.preprocessing import run_phase_2
from .phases.synchronization import run_phase_4

# Setup rich console and logging
console = Console()

# Configure console handler for high-level output only (WARNING+)
console_handler = RichHandler(console=console, rich_tracebacks=True, show_path=False)
console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in terminal

# Configure root logger (DEBUG level for file handlers)
logging.basicConfig(level=logging.DEBUG, format="%(message)s", datefmt="[%X]", handlers=[console_handler])  # Capture all levels for file handlers

logger = logging.getLogger(__name__)


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
        self._session_log_handlers = []  # Track session-specific log handlers for cleanup

    def run(self) -> RunResult:
        """Run complete pipeline workflow.

        Executes all 7 phases with rich progress tracking, error handling,
        and automatic profiling. Generates diagnostic figures in the output
        directory showing phase timing and pipeline statistics.

        Returns:
            RunResult with paths, NWBFile, statistics, validation results,
            and profiling data

        Raises:
            Exception: Any phase failure is caught and returned in RunResult
        """
        if not self.context.options.quiet_mode:
            console.print(
                Panel.fit(
                    f"[bold cyan]W2T Body Kinematics Pipeline[/bold cyan]\n"
                    f"Subject: [yellow]{self.context.subject_id}[/yellow]\n"
                    f"Session: [yellow]{self.context.session_id}[/yellow]\n"
                    f"Config: [dim]{self.context.config_path}[/dim]",
                    border_style="cyan",
                )
            )

        # Initialize profiler
        profile = PipelineProfile(
            subject_id=self.context.subject_id,
            session_id=self.context.session_id,
            config_path=str(self.context.config_path),
        )

        try:
            columns = SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeRemainingColumn()
            with Progress(*columns, console=console, disable=self.context.options.quiet_mode) as progress:

                # Phase 0: Initialization
                with PhaseTimer(profile, phase_index=0, phase_name="Initialization"):
                    task = progress.add_task("[cyan]Phase 0: Initialization", total=1)
                    run_phase_0(self.context, progress, task)
                    progress.update(task, completed=1)

                # Setup session-specific log files AFTER config is loaded
                self._setup_session_logging()
                if not self.context.options.quiet_mode:
                    console.print("[green]✓[/green] Configuration loaded")

                # Phase 1: Discovery & Verification
                with PhaseTimer(profile, phase_index=1, phase_name="Discovery & Verification"):
                    task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=None)
                    run_phase_1(self.context, progress, task)

                # Summary after Phase 1
                camera_count = len([c for c in self.context.camera_files.values() if c])
                ttl_count = len([t for t in self.context.ttl_files.values() if t])
                if not self.context.options.quiet_mode:
                    console.print(f"[green]✓[/green] Discovered {camera_count} camera(s), {ttl_count} TTL channel(s)")

                # Phase 2: Preprocessing
                with PhaseTimer(profile, phase_index=2, phase_name="Preprocessing"):
                    task = progress.add_task("[cyan]Phase 2: Preprocessing", total=None)
                    run_phase_2(self.context, progress, task)
                if not self.context.options.quiet_mode:
                    console.print("[green]✓[/green] Preprocessing complete")

                # Phase 3: Ingestion
                with PhaseTimer(profile, phase_index=3, phase_name="Ingestion"):
                    task = progress.add_task("[cyan]Phase 3: Ingestion", total=None)
                    run_phase_3(self.context, progress, task)

                # Summary after Phase 3
                pose_count = len(self.context.pose_data)
                bpod_trials = len(self.context.bpod_data.get("trials", [])) if self.context.bpod_data else 0
                if not self.context.options.quiet_mode:
                    console.print(f"[green]✓[/green] Ingested pose data for {pose_count} camera(s), {bpod_trials} Bpod trial(s)")

                # Phase 4: Synchronization
                with PhaseTimer(profile, phase_index=4, phase_name="Synchronization"):
                    task = progress.add_task("[cyan]Phase 4: Synchronization", total=1)
                    run_phase_4(self.context, progress, task)
                    progress.update(task, completed=1)
                if not self.context.options.quiet_mode:
                    console.print("[green]✓[/green] Synchronization complete")

                # Phase 5: Assembly
                with PhaseTimer(profile, phase_index=5, phase_name="Assembly"):
                    task = progress.add_task("[cyan]Phase 5: Assembly", total=None)
                    run_phase_5(self.context, progress, task)
                if not self.context.options.quiet_mode:
                    console.print("[green]✓[/green] NWB assembly complete")

                # Phase 6: Finalization
                with PhaseTimer(profile, phase_index=6, phase_name="Finalization & Validation"):
                    task = progress.add_task("[cyan]Phase 6: Finalization & Validation", total=None)
                    run_phase_6(self.context, progress, task)
                if not self.context.options.quiet_mode:
                    console.print("[green]✓[/green] NWB file written and validated")

            # Finalize profiling
            profile.finalize()

            if not self.context.options.quiet_mode:
                console.print("\n[bold green]✓ Pipeline completed successfully[/bold green]")
                console.print(f"[dim]Total execution time: {profile.total_duration:.2f}s[/dim]")

            # Generate diagnostic figures and save profiling data
            self._save_profiling_artifacts(profile)

            return RunResult(
                nwb_path=self.context.nwb_path or Path(""),
                nwbfile=self.context.nwbfile,
                alignment_stats=self.context.alignment_stats,
                validation_results=self.context.validation_results,
                profile=profile,
                success=True,
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            if not self.context.options.quiet_mode:
                console.print(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            profile.finalize()
            return RunResult(
                nwb_path=Path(""),
                profile=profile,
                success=False,
                error=str(e),
            )
        finally:
            # Remove session log handlers
            self._cleanup_session_logging()

    def _setup_session_logging(self) -> None:
        """Setup session-specific log files for warnings and errors.

        Creates pipeline.log files in both output and intermediate directories
        to capture all WARNING and ERROR messages specific to this session.
        Also creates a detailed debug log with all DEBUG+ messages.
        """
        # Directories to write logs to
        output_dir = self.context.config.paths.output_root / self.context.subject_id / self.context.session_id
        interim_dir = self.context.config.paths.intermediate_root / self.context.subject_id / self.context.session_id

        # Create directories if they don't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        interim_dir.mkdir(parents=True, exist_ok=True)

        # Create log file handlers
        log_format = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

        # Add handler for output directory (WARNING+)
        output_log_path = output_dir / "pipeline.log"
        output_handler = logging.FileHandler(output_log_path, mode="w", encoding="utf-8")
        output_handler.setLevel(logging.WARNING)  # Only WARNING and ERROR
        output_handler.setFormatter(log_format)

        # Add handler for intermediate directory (WARNING+)
        interim_log_path = interim_dir / "pipeline.log"
        interim_handler = logging.FileHandler(interim_log_path, mode="w", encoding="utf-8")
        interim_handler.setLevel(logging.WARNING)  # Only WARNING and ERROR
        interim_handler.setFormatter(log_format)

        # Add detailed debug log handler (DEBUG+)
        debug_log_path = output_dir / "pipeline-debug.log"
        debug_handler = logging.FileHandler(debug_log_path, mode="w", encoding="utf-8")
        debug_handler.setLevel(logging.DEBUG)  # All messages
        debug_handler.setFormatter(log_format)

        # Add handlers to root logger (affects all w2t_bkin loggers)
        root_logger = logging.getLogger("w2t_bkin")
        root_logger.addHandler(output_handler)
        root_logger.addHandler(interim_handler)
        root_logger.addHandler(debug_handler)

        # Track handlers for cleanup
        self._session_log_handlers = [output_handler, interim_handler, debug_handler]

        logger.debug(f"Session logging enabled: {output_log_path}, {interim_log_path}, {debug_log_path}")

    def _cleanup_session_logging(self) -> None:
        """Remove session-specific log handlers."""
        root_logger = logging.getLogger("w2t_bkin")
        for handler in self._session_log_handlers:
            handler.close()
            root_logger.removeHandler(handler)
        self._session_log_handlers = []

    def _save_profiling_artifacts(self, profile: PipelineProfile) -> None:
        """Save profiling data and diagnostic figures to output directory.

        Args:
            profile: Pipeline profiling data with phase timings
        """
        if self.context.nwb_path is None:
            logger.warning("NWB path not set, skipping profiling artifacts")
            return

        # Determine output directory (same as NWB file)
        output_dir = self.context.nwb_path.parent
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        # Save profiling JSON data
        profile_path = output_dir / "pipeline_profile.json"
        try:
            with open(profile_path, "w") as f:
                json.dump(profile.to_dict(), f, indent=2)
            logger.info(f"Profiling data saved to: {profile_path}")
        except Exception as e:
            logger.warning(f"Failed to save profiling data: {e}")

        # Generate diagnostic figures (if enabled)
        if not self.context.options.generate_figures:
            logger.info("Figure generation disabled, skipping diagnostic plots")
            return

        try:
            # Pipeline execution (merged timing + timeline)
            execution_fig_path = figures_dir / "pipeline_execution.png"
            plot_pipeline_execution(profile, save_path=execution_fig_path)
            logger.info(f"Pipeline execution figure saved to: {execution_fig_path}")

            # Synchronization statistics (if available)
            if self.context.alignment_stats:
                sync_fig_path = figures_dir / "synchronization_stats.png"
                plot_synchronization_stats(self.context.alignment_stats, save_path=sync_fig_path)
                logger.info(f"Synchronization statistics figure saved to: {sync_fig_path}")

            # TTL inter-pulse interval analysis (if TTL data available)
            if self.context.ttl_pulses:
                ipi_fig_path = figures_dir / "ttl_inter_pulse_intervals.png"

                # Extract expected FPS from camera metadata
                expected_fps = {}
                for camera in self.context.metadata.get("cameras", []):
                    ttl_id = camera.get("ttl_id")
                    fps = camera.get("fps")
                    if ttl_id and fps:
                        expected_fps[ttl_id] = fps

                result = plot_ttl_inter_pulse_intervals(
                    self.context.ttl_pulses,
                    expected_fps if expected_fps else None,
                    save_path=ipi_fig_path,
                )
                if result:
                    logger.info(f"TTL inter-pulse interval figure saved to: {ipi_fig_path}")

            # Combined sync quality + completeness (if trial offsets available)
            if self.context.trial_offsets and len(self.context.trial_offsets) >= 3:
                combined_fig_path = figures_dir / "sync_quality_and_completeness.png"

                # Build data streams availability (if available)
                data_streams = None
                if self.context.bpod_data:
                    # Get ALL trial numbers from Bpod (not just successfully aligned ones)
                    # Extract trial count from Bpod structure
                    from w2t_bkin import utils

                    session_data = utils.convert_matlab_struct(self.context.bpod_data.get("SessionData", {}))
                    raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
                    trials = raw_events.get("Trial", [])
                    n_trials = len(trials) if trials is not None else 0

                    if n_trials == 0:
                        logger.warning("No trials found in Bpod data, skipping completeness data streams")
                        data_streams = None
                    else:
                        all_trial_numbers = list(range(1, n_trials + 1))

                        # Check which trials were successfully aligned
                        aligned_trials_set = set(self.context.trial_offsets.keys())

                        data_streams = {}

                        # Bpod availability: TRUE only for successfully aligned trials
                        data_streams["Bpod"] = [trial_num in aligned_trials_set for trial_num in all_trial_numbers]

                        # TTL channel availability: same as Bpod (if trial aligned, TTL was present)
                        if self.context.ttl_pulses:
                            for ttl_id in self.context.ttl_pulses.keys():
                                data_streams[f"TTL_{ttl_id}"] = [trial_num in aligned_trials_set for trial_num in all_trial_numbers]

                        # Camera/Pose availability: available for aligned trials (simplified)
                        if self.context.pose_data:
                            for camera_id, pose_list in self.context.pose_data.items():
                                has_pose = len(pose_list) > 0
                                data_streams[f"Pose_{camera_id}"] = [has_pose and (trial_num in aligned_trials_set) for trial_num in all_trial_numbers]

                        # Only include data_streams if we have multiple streams
                        if len(data_streams) <= 1:
                            data_streams = None

                result = plot_sync_quality_and_completeness(
                    self.context.trial_offsets,
                    data_streams=data_streams,
                    save_path=combined_fig_path,
                    csv_output_dir=output_dir,
                )
                if result:
                    logger.info(f"Sync quality and completeness figure saved to: {combined_fig_path}")
                    csv_path = output_dir / f"{combined_fig_path.stem}_validation.csv"
                    if csv_path.exists():
                        logger.info(f"Sync validation CSV saved to: {csv_path}")

            console.print(f"\n[green]✓ Diagnostic figures saved to: {figures_dir}[/green]")

        except ImportError:
            logger.warning("matplotlib not installed, skipping diagnostic figures")
        except Exception as e:
            logger.warning(f"Failed to generate diagnostic figures: {e}")
