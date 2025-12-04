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

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

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
                run_phase_0(self.context, progress, task)
                progress.update(task, completed=1)

                # Phase 1: Discovery & Verification
                task = progress.add_task("[cyan]Phase 1: Discovery & Verification", total=None)
                run_phase_1(self.context, progress, task)

                # Phase 2: Preprocessing
                task = progress.add_task("[cyan]Phase 2: Preprocessing", total=None)
                run_phase_2(self.context, progress, task)

                # Phase 3: Ingestion
                task = progress.add_task("[cyan]Phase 3: Ingestion", total=None)
                run_phase_3(self.context, progress, task)

                # Phase 4: Synchronization
                task = progress.add_task("[cyan]Phase 4: Synchronization", total=1)
                run_phase_4(self.context, progress, task)
                progress.update(task, completed=1)

                # Phase 5: Assembly
                task = progress.add_task("[cyan]Phase 5: Assembly", total=None)
                run_phase_5(self.context, progress, task)

                # Phase 6: Finalization
                task = progress.add_task("[cyan]Phase 6: Finalization & Validation", total=None)
                run_phase_6(self.context, progress, task)

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
