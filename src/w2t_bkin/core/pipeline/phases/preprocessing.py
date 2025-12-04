"""Phase 2: Preprocessing."""

import logging
from typing import Optional

from rich.progress import Progress, TaskID

from ....exceptions import IngestError
from ....tasks import DLCPoseTask, SLEAPPoseTask, TaskConfig
from ....tasks.base import TaskStatus
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_2(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Execute preprocessing tasks to generate intermediate artifacts."""
    logger.info("Running preprocessing tasks...")

    if progress and task_id is not None:
        progress.update(task_id, total=1)

    # Create interim directory structure
    interim_dir = context.config.paths.intermediate_root / context.subject_id / context.session_id
    interim_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Interim directory: {interim_dir}")

    # Build task configuration
    task_config = TaskConfig(
        enabled=context.config.preprocessing.dlc.enabled,  # Base enabled flag (will be overridden per task if needed)
        force_rerun=context.config.preprocessing.force_rerun,
        session_dir=context.session_dir,
        interim_dir=interim_dir,
        metadata=context.metadata,
        config=context.config,
    )

    _run_dlc_preprocessing(context, task_config)
    _run_sleap_preprocessing(context, task_config)

    if progress and task_id is not None:
        progress.advance(task_id)


def _run_dlc_preprocessing(context: PipelineContext, task_config: TaskConfig) -> None:
    if context.config.preprocessing.dlc.enabled:
        logger.info("  DLC pose estimation enabled")
        dlc_task = DLCPoseTask()

        # Update enabled flag for DLC specifically
        task_config.enabled = True

        # Run task with full lifecycle (check deps, check output, execute if needed)
        status, _ = dlc_task.run(task_config)

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


def _run_sleap_preprocessing(context: PipelineContext, task_config: TaskConfig) -> None:
    if context.config.preprocessing.sleap.enabled:
        logger.info("  SLEAP pose estimation enabled")
        sleap_task = SLEAPPoseTask()

        # Update enabled flag for SLEAP specifically
        task_config.enabled = True

        # Run task with full lifecycle
        status, _ = sleap_task.run(task_config)

        if status == TaskStatus.COMPLETED:
            logger.info("  SLEAP: Completed successfully")
        elif status == TaskStatus.CACHED:
            logger.info("  SLEAP: Using cached results from interim folder")
        elif status == TaskStatus.SKIP:
            logger.info("  SLEAP: Skipped (dependencies not met or disabled)")
        elif status == TaskStatus.FAILED:
            logger.error("  SLEAP: Task failed")
            raise IngestError(
                message="SLEAP preprocessing task failed",
                context={"task": "SLEAPPoseTask", "status": status.name},
                hint="Check SLEAP model configuration and video files",
            )
    else:
        logger.info("  SLEAP pose estimation disabled")
