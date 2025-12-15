"""Batch processing flow orchestration for w2t-bkin pipeline.

This module defines Prefect flows for parallel batch processing of multiple
sessions. It handles session discovery, filtering, parallel execution, and
aggregated result reporting.

Architecture:
    Session discovery → Parallel session flows → Aggregate results

Features:
    - Automatic session discovery from raw data directory
    - Subject/session filtering
    - Parallel execution with configurable concurrency
    - Graceful error handling (partial failures)
    - Aggregated statistics and reporting

Example:
    >>> from w2t_bkin.flows import batch_process_flow
    >>> result = batch_process_flow(
    ...     config_path="config.toml",
    ...     subject_filter="subject-*",
    ...     max_parallel=4
    ... )
    >>> print(f"Completed {result['successful']}/{result['total']} sessions")
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional

from prefect import flow, get_run_logger, task

from w2t_bkin.api import BatchFlowConfig, SessionFlowConfig
from w2t_bkin.flows.session import process_session_flow
from w2t_bkin.models import SessionResult
from w2t_bkin.utils import discover_sessions

logger = logging.getLogger(__name__)


@task(
    name="process-single-session-task",
    description="Process a single session (used in batch processing)",
    retries=2,
    retry_delay_seconds=60,
    tags=["session-processing"],
)
def process_single_session_task(session_config: SessionFlowConfig) -> SessionResult:
    """Process a single session as a Prefect task.

    This wrapper allows parallel execution of multiple sessions in batch processing.

    Args:
        session_config: Session configuration

    Returns:
        SessionResult with processing outcome
    """
    try:
        return process_session_flow(session_config)
    except Exception as e:
        # Return failed result instead of raising
        return SessionResult(
            success=False,
            subject_id=session_config.subject_id,
            session_id=session_config.session_id,
            error=str(e),
        )


@dataclass
class BatchResult:
    """Result of batch session processing.

    Attributes:
        total: Total number of sessions attempted
        successful: Number of successfully processed sessions
        failed: Number of failed sessions
        skipped: Number of skipped sessions
        session_results: Individual session results
        errors: Error messages per session
        duration_seconds: Total batch processing time
    """

    total: int
    successful: int
    failed: int
    skipped: int
    session_results: List[SessionResult]
    errors: Dict[str, str]
    duration_seconds: float


import os


@flow(
    name="batch-process-sessions",
    description="Process multiple sessions in parallel",
    log_prints=True,
    persist_result=True,
    task_runner=None,  # Use default ConcurrentTaskRunner for parallel execution
)
def batch_process_flow(config: BatchFlowConfig) -> BatchResult:
    """Process multiple sessions in parallel using Prefect.

    This flow discovers sessions from the raw data directory, filters them
    according to the provided patterns, and processes them in parallel using
    the process_session_flow. Failed sessions do not stop the batch - all
    sessions are attempted and results are aggregated.

    Parallelism: Sessions are submitted as concurrent Prefect tasks. The actual
    degree of parallelism depends on available workers. Use max_parallel to
    limit concurrency (requires configuring a work pool concurrency limit in
    Prefect server settings).

    Args:
        config: Validated configuration model with all batch parameters.
                Auto-generates UI forms in Prefect with validation and docs.

    Returns:
        BatchResult with aggregated statistics and individual results

    Example:
        >>> from w2t_bkin.flows.config_models import BatchFlowConfig
        >>> config = BatchFlowConfig(
        ...     subject_filter="subject-001",
        ...     max_parallel=2
        ... )
        >>> result = batch_process_flow(config)
        >>>
        >>> # Process specific session pattern across subjects
        >>> config = BatchFlowConfig(
        ...     session_filter="session-001",
        ...     max_parallel=4
        ... )
        >>> result = batch_process_flow(config)
    """
    run_logger = get_run_logger()
    start_time = datetime.now()

    # Extract values from Pydantic model
    subject_filter = config.subject_filter
    session_filter = config.session_filter
    max_parallel = config.max_parallel
    skip_bpod = config.skip_bpod
    skip_pose = config.skip_pose
    skip_ecephys = config.skip_ecephys
    skip_camera_sync = config.skip_camera_sync
    skip_nwb_validation = config.skip_nwb_validation

    try:
        # =====================================================================
        # Phase 1: Discover Sessions
        # =====================================================================
        run_logger.info("Discovering sessions from raw data directory")

        # Load configuration from environment variable (baked at deployment time)
        import json

        from w2t_bkin.config import load_config_from_dict

        config_json = os.getenv("W2T_RUNTIME_CONFIG_JSON")
        if not config_json:
            raise ValueError("W2T_RUNTIME_CONFIG_JSON environment variable not set. Deployment configuration missing.")

        config_dict = json.loads(config_json)
        temp_config = load_config_from_dict(config_dict)

        # Discover sessions from raw_root
        from w2t_bkin.utils import discover_sessions as discover_sessions_util

        sessions = []
        for subject_dir in sorted(temp_config.paths.raw_root.iterdir()):
            if not subject_dir.is_dir() or subject_dir.name.startswith("."):
                continue

            subject_id = subject_dir.name
            if subject_filter and subject_id != subject_filter:
                continue

            for session_dir in sorted(subject_dir.iterdir()):
                if not session_dir.is_dir() or session_dir.name.startswith("."):
                    continue

                session_id = session_dir.name
                if session_filter and session_id != session_filter:
                    continue

                sessions.append({"subject": subject_id, "session": session_id})

        if not sessions:
            run_logger.warning(f"No sessions found matching filters " f"(subject: {subject_filter}, session: {session_filter})")
            return BatchResult(
                total=0,
                successful=0,
                failed=0,
                skipped=0,
                session_results=[],
                errors={},
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

        run_logger.info(f"Found {len(sessions)} sessions " f"(subject_filter: {subject_filter}, session_filter: {session_filter})")

        # =====================================================================
        # Phase 2: Process Sessions in Parallel
        # =====================================================================
        # Submit all sessions as tasks for parallel execution
        # Prefect will respect max_parallel limit via task concurrency
        run_logger.info(f"Processing {len(sessions)} sessions with max_parallel={max_parallel}")

        # Create session configs and submit as tasks
        futures = []
        for session_info in sessions:
            subject_id = session_info["subject"]
            session_id = session_info["session"]

            session_config = SessionFlowConfig(
                subject_id=subject_id,
                session_id=session_id,
                skip_bpod=skip_bpod,
                skip_pose=skip_pose,
                skip_dlc=False,  # Only skip_pose controls DLC in batch
                skip_sleap=False,  # Only skip_pose controls SLEAP in batch
                skip_ecephys=skip_ecephys,
                skip_camera_sync=skip_camera_sync,
                skip_nwb_validation=skip_nwb_validation,
            )

            # Submit task for concurrent execution
            future = process_single_session_task.submit(session_config)
            futures.append((subject_id, session_id, future))

        # Wait for all tasks to complete and collect results
        session_results = []
        errors = {}
        successful = 0
        failed = 0

        for subject_id, session_id, future in futures:
            try:
                result = future.result()
                session_results.append(result)

                if result.success:
                    successful += 1
                    run_logger.info(f"✓ {subject_id}/{session_id} completed successfully " f"({result.duration_seconds:.1f}s)")
                else:
                    failed += 1
                    session_key = f"{subject_id}/{session_id}"
                    errors[session_key] = result.error or "Unknown error"
                    run_logger.error(f"✗ {subject_id}/{session_id} failed: {result.error}")

            except Exception as e:
                failed += 1
                session_key = f"{subject_id}/{session_id}"
                errors[session_key] = str(e)
                run_logger.error(
                    f"✗ {subject_id}/{session_id} failed with exception: {e}",
                    exc_info=True,
                )

                # Create failure result
                session_results.append(
                    SessionResult(
                        success=False,
                        subject_id=subject_id,
                        session_id=session_id,
                        error=str(e),
                    )
                )

        # =====================================================================
        # Phase 4: Aggregate and Report
        # =====================================================================
        duration = (datetime.now() - start_time).total_seconds()

        batch_result = BatchResult(
            total=len(sessions),
            successful=successful,
            failed=failed,
            skipped=0,
            session_results=session_results,
            errors=errors,
            duration_seconds=duration,
        )

        # Log summary
        run_logger.info(
            f"\n"
            f"Batch processing complete:\n"
            f"  Total sessions: {batch_result.total}\n"
            f"  Successful: {batch_result.successful}\n"
            f"  Failed: {batch_result.failed}\n"
            f"  Duration: {duration:.1f}s\n"
            f"  Avg per session: {duration / len(sessions):.1f}s"
        )

        if errors:
            run_logger.warning(f"Errors occurred in {len(errors)} sessions:")
            for session_key, error in errors.items():
                run_logger.warning(f"  {session_key}: {error}")

        return batch_result

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        run_logger.error(f"Batch processing failed: {e}", exc_info=True)

        return BatchResult(
            total=0,
            successful=0,
            failed=0,
            skipped=0,
            session_results=[],
            errors={"batch": str(e)},
            duration_seconds=duration,
        )
