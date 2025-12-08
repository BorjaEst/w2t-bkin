"""Prefect flows for W2T Body Kinematics Pipeline.

This module provides flow definitions for orchestrating pipeline execution
with Prefect. Two execution modes are available:

1. Monolithic Mode (fast, simple):
   - Entire session as one task
   - Current proven behavior
   - Best for production

2. Phase-Level Mode (observable, debuggable):
   - Each pipeline phase as separate task
   - Maximum observability in Prefect UI
   - Best for debugging and development

Flows:
------
- process_session_monolithic: Single session, monolithic task
- process_session_with_phases: Single session, phase-level tasks
- batch_process_sessions: Batch processing with mode selection

Examples:
---------
>>> from w2t_bkin.prefect import batch_process_sessions
>>>
>>> # Production mode (fast)
>>> batch_process_sessions(
...     config_path="config.toml",
...     subject_filter="SNA-*",
...     use_phases=False,
... )
>>>
>>> # Debug mode (observable)
>>> batch_process_sessions(
...     config_path="config.toml",
...     subject_filter="SNA-*",
...     use_phases=True,
... )
"""

import logging
from pathlib import Path
from typing import Optional

from prefect import flow
from prefect.logging import get_run_logger

from ..core.pipeline.models import PipelineContext, RunOptions
from ..utils import discover_sessions
from .tasks import assembly_task, discovery_task, finalization_task, ingestion_task, initialization_task, preprocessing_task, process_session_monolithic_task, synchronization_task

logger = logging.getLogger(__name__)


@flow(
    name="process-session-with-phases",
    log_prints=True,
    description="Process session with phase-level granularity for maximum observability",
)
def process_session_with_phases(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
    options: Optional[RunOptions] = None,
) -> dict:
    """Process a single session with each phase as a separate task.

    Advantages:
    - Phase-level retry logic
    - Detailed observability in Prefect UI
    - Can see which phase failed
    - Per-phase duration tracking

    Disadvantages:
    - Slightly slower (~5-10% overhead from task serialization)
    - More complex execution graph

    Args:
        config_path: Path to configuration TOML file
        subject_id: Subject identifier
        session_id: Session identifier
        options: Optional run options (defaults to RunOptions())

    Returns:
        Result dictionary with success status and metadata

    Examples:
        >>> from w2t_bkin.prefect import process_session_with_phases
        >>> result = process_session_with_phases(
        ...     config_path="config.toml",
        ...     subject_id="subject-001",
        ...     session_id="session_20251201",
        ... )
        >>> print(f"Success: {result['success']}, Phases: {result['phases_completed']}")
    """
    flow_logger = get_run_logger()

    if options is None:
        options = RunOptions()

    flow_logger.info(f"Starting phase-level processing: {subject_id}/{session_id}")

    try:
        # Initialize context
        context = PipelineContext(
            config_path=Path(config_path),
            subject_id=subject_id,
            session_id=session_id,
            options=options,
        )

        # Run phases sequentially (context passed through and updated by each phase)
        flow_logger.info("Phase 0: Initialization")
        context = initialization_task(context)

        flow_logger.info("Phase 1: Discovery")
        context = discovery_task(context)

        flow_logger.info("Phase 2: Preprocessing")
        context = preprocessing_task(context)

        flow_logger.info("Phase 3: Ingestion")
        context = ingestion_task(context)

        flow_logger.info("Phase 4: Synchronization")
        context = synchronization_task(context)

        flow_logger.info("Phase 5: Assembly")
        context = assembly_task(context)

        flow_logger.info("Phase 6: Finalization")
        context = finalization_task(context)

        flow_logger.info(f"✓ Completed all phases: {subject_id}/{session_id}")

        return {
            "success": True,
            "subject_id": subject_id,
            "session_id": session_id,
            "phases_completed": 7,
            "nwb_path": str(context.nwbfile_path) if hasattr(context, "nwbfile_path") else None,
            "error": None,
        }

    except Exception as e:
        flow_logger.error(f"✗ Phase-level processing failed: {subject_id}/{session_id}: {e}")
        return {
            "success": False,
            "subject_id": subject_id,
            "session_id": session_id,
            "phases_completed": None,
            "nwb_path": None,
            "error": str(e),
        }


@flow(
    name="process-session-monolithic",
    log_prints=True,
    description="Process session as single task (faster, less observable)",
)
def process_session_monolithic(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
) -> dict:
    """Process entire session as one monolithic task.

    Advantages:
    - Faster (no task overhead)
    - Simpler execution graph
    - Current proven behavior

    Disadvantages:
    - Limited observability
    - Can't see which phase failed
    - Less granular retry logic

    Args:
        config_path: Path to configuration TOML file
        subject_id: Subject identifier
        session_id: Session identifier

    Returns:
        Result dictionary with success status

    Examples:
        >>> from w2t_bkin.prefect import process_session_monolithic
        >>> result = process_session_monolithic(
        ...     config_path="config.toml",
        ...     subject_id="subject-001",
        ...     session_id="session_20251201",
        ... )
    """
    flow_logger = get_run_logger()
    flow_logger.info(f"Starting monolithic processing: {subject_id}/{session_id}")

    result = process_session_monolithic_task(
        str(config_path),
        subject_id,
        session_id,
    )

    if result["success"]:
        flow_logger.info(f"✓ Completed: {subject_id}/{session_id}")
    else:
        flow_logger.error(f"✗ Failed: {subject_id}/{session_id}: {result['error']}")

    return result


@flow(
    name="batch-process-sessions",
    log_prints=True,
    description="Batch process multiple sessions in parallel",
)
def batch_process_sessions(
    config_path: str | Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
    max_workers: int = 4,
    use_phases: bool = False,
) -> dict:
    """Batch process multiple subjects/sessions.

    Args:
        config_path: Path to configuration file
        subject_filter: Optional subject ID filter (glob pattern)
        session_filter: Optional session ID filter (glob pattern)
        max_workers: Concurrency hint (not enforced by Prefect, for logging only)
        use_phases: Use phase-level tasks (slower, more observable) vs monolithic (faster)

    Returns:
        Summary dict with total, successful, failed counts and results

    Examples:
        >>> from w2t_bkin.prefect import batch_process_sessions
        >>>
        >>> # Fast production mode
        >>> result = batch_process_sessions(
        ...     config_path="config.toml",
        ...     subject_filter="SNA-*",
        ...     use_phases=False,
        ... )
        >>>
        >>> # Observable debug mode
        >>> result = batch_process_sessions(
        ...     config_path="config.toml",
        ...     subject_filter="SNA-*",
        ...     use_phases=True,
        ... )
    """
    flow_logger = get_run_logger()

    # Discover sessions
    flow_logger.info(f"Discovering sessions from {config_path}")
    flow_logger.info(f"  Subject filter: {subject_filter or 'all'}")
    flow_logger.info(f"  Session filter: {session_filter or 'all'}")

    sessions = discover_sessions(
        config_path=config_path,
        subject_filter=subject_filter,
        session_filter=session_filter,
    )

    total = len(sessions)
    mode = "phase-level" if use_phases else "monolithic"
    flow_logger.info(f"Found {total} session(s) to process in {mode} mode")

    if total == 0:
        flow_logger.warning("No sessions found!")
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
            "mode": mode,
        }

    # Choose flow based on granularity preference
    flow_fn = process_session_with_phases if use_phases else process_session_monolithic
    flow_logger.info(f"Using {'phase-level' if use_phases else 'monolithic'} execution mode")
    flow_logger.info(f"Submitting {total} sub-flows (max_workers hint: {max_workers})")

    # Submit all sessions as parallel sub-flow runs
    futures = []
    for session in sessions:
        future = flow_fn.submit(
            config_path=str(config_path),
            subject_id=session["subject"],
            session_id=session["session"],
        )
        futures.append(future)

    # Wait for all to complete and collect results
    flow_logger.info("Waiting for all sub-flows to complete...")
    results = []

    for i, future in enumerate(futures, 1):
        try:
            result = future.result()
            results.append(result)

            # Progress logging
            status = "✓" if result.get("success", False) else "✗"
            session_label = f"{result['subject_id']}/{result['session_id']}"
            flow_logger.info(f"{status} [{i}/{total}] {session_label}")

        except Exception as e:
            # Unexpected error (shouldn't happen if tasks handle exceptions)
            flow_logger.error(f"✗ [{i}/{total}] Unexpected error: {e}")
            results.append(
                {
                    "success": False,
                    "subject_id": "unknown",
                    "session_id": "unknown",
                    "error": f"Future error: {str(e)}",
                }
            )

    # Calculate summary
    successful = sum(1 for r in results if r.get("success", False))
    failed = total - successful

    flow_logger.info(f"📊 Batch complete: {successful}/{total} successful, {failed} failed")

    # Log failed sessions for debugging
    if failed > 0:
        flow_logger.warning("❌ Failed sessions:")
        for r in results:
            if not r.get("success", False):
                session_label = f"{r.get('subject_id', 'unknown')}/{r.get('session_id', 'unknown')}"
                flow_logger.warning(f"  - {session_label}: {r.get('error', 'Unknown error')}")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "results": results,
        "mode": mode,
    }


# Backward compatibility alias
batch_process_sessions_prefect = batch_process_sessions


__all__ = [
    # New preferred names
    "process_session_with_phases",
    "process_session_monolithic",
    "batch_process_sessions",
    # Backward compatibility
    "batch_process_sessions_prefect",
]
