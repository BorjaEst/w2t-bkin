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

from ...figures.profiling import PhaseTimer, PipelineProfile, plot_pipeline_execution, plot_synchronization_stats
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
logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(console=console, rich_tracebacks=True)])
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
            with Progress(*columns, console=console) as progress:

                # Phase 0: Initialization
                with PhaseTimer(profile, phase_index=0, phase_name="Initialization"):
                    task = progress.add_task("[cyan]Phase 0: Initialization", total=1)
                    run_phase_0(self.context, progress, task)
                    progress.update(task, completed=1)

                # Phase 1: Discovery & Verification
                with PhaseTimer(profile, phase_index=1, phase_name="Discovery & Verification"):
                    task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=None)
                    run_phase_1(self.context, progress, task)

                # Phase 2: Preprocessing
                with PhaseTimer(profile, phase_index=2, phase_name="Preprocessing"):
                    task = progress.add_task("[cyan]Phase 2: Preprocessing", total=None)
                    run_phase_2(self.context, progress, task)

                # Phase 3: Ingestion
                with PhaseTimer(profile, phase_index=3, phase_name="Ingestion"):
                    task = progress.add_task("[cyan]Phase 3: Ingestion", total=None)
                    run_phase_3(self.context, progress, task)

                # Phase 4: Synchronization
                with PhaseTimer(profile, phase_index=4, phase_name="Synchronization"):
                    task = progress.add_task("[cyan]Phase 4: Synchronization", total=1)
                    run_phase_4(self.context, progress, task)
                    progress.update(task, completed=1)

                # Phase 5: Assembly
                with PhaseTimer(profile, phase_index=5, phase_name="Assembly"):
                    task = progress.add_task("[cyan]Phase 5: Assembly", total=None)
                    run_phase_5(self.context, progress, task)

                # Phase 6: Finalization
                with PhaseTimer(profile, phase_index=6, phase_name="Finalization & Validation"):
                    task = progress.add_task("[cyan]Phase 6: Finalization & Validation", total=None)
                    run_phase_6(self.context, progress, task)

            # Finalize profiling
            profile.finalize()

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
            console.print(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            profile.finalize()
            return RunResult(
                nwb_path=Path(""),
                profile=profile,
                success=False,
                error=str(e),
            )

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

            console.print(f"\n[green]✓ Diagnostic figures saved to: {figures_dir}[/green]")

        except ImportError:
            logger.warning("matplotlib not installed, skipping diagnostic figures")
        except Exception as e:
            logger.warning(f"Failed to generate diagnostic figures: {e}")
