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
from typing import Dict, List

from prefect import flow, get_run_logger, task

from w2t_bkin.config import BatchFlowConfig, SessionConfig
from w2t_bkin.flows.session import process_session_flow
from w2t_bkin.models import SessionResult
from w2t_bkin.utils import discover_sessions_in_raw_root

logger = logging.getLogger(__name__)


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


@flow(
    name="batch-process-sessions",
    description="Process multiple sessions in parallel",
    log_prints=True,
    persist_result=True,
    task_runner=None,  # Use default ConcurrentTaskRunner for parallel execution
)
def batch_process_flow(config: BatchFlowConfig) -> BatchResult:
    """Process multiple sessions in parallel using Prefect.

    Args:
        config: Batch configuration with session config and filters

    Returns:
        BatchResult with aggregated statistics
    """
    run_logger = get_run_logger()
    start_time = datetime.now()

    try:
        # =====================================================================
        # Phase 1: Discover Sessions
        # =====================================================================
        run_logger.info("Discovering sessions from raw data directory")

        # Get raw_root from environment
        import os

        raw_root_str = os.getenv("W2T_RAW_ROOT")
        if not raw_root_str:
            raise EnvironmentError("W2T_RAW_ROOT environment variable not set. " "Set it to your raw data directory (e.g., export W2T_RAW_ROOT=/data/raw)")

        raw_root = Path(raw_root_str).resolve()

        # Discover sessions using glob pattern matching
        sessions = discover_sessions_in_raw_root(
            raw_root=raw_root,
            subject_filter=config.subject_filter,
            session_filter=config.session_filter,
        )

        run_logger.info(f"Found {len(sessions)} sessions " f"(subject_filter: {config.subject_filter}, session_filter: {config.session_filter})")

        # =====================================================================
        # Phase 2: Process Sessions in Parallel
        # =====================================================================
        run_logger.info(f"Processing {len(sessions)} sessions with max_parallel={config.max_parallel}")

        # Submit all sessions as tasks for parallel execution
        futures = []
        for session_info in sessions:
            subject_id = session_info["subject"]
            session_id = session_info["session"]

            # Submit task for concurrent execution
            future = process_single_session_task.submit(
                subject_id=subject_id,
                session_id=session_id,
                config=config.configuration,
            )
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


@task(
    name="process-single-session",
    description="Process a single session (task wrapper for parallel execution)",
    retries=2,
    retry_delay_seconds=60,
    tags=["session-processing"],
)
def process_single_session_task(
    subject_id: str,
    session_id: str,
    config: SessionConfig,
) -> SessionResult:
    """Task wrapper for process_session_flow to enable parallel execution.

    Args:
        subject_id: Subject identifier
        session_id: Session identifier
        config: Session configuration

    Returns:
        SessionResult with processing outcome
    """
    try:
        return process_session_flow(
            subject_id=subject_id,
            session_id=session_id,
            config=config,
        )
    except Exception as e:
        # Return failed result instead of raising
        return SessionResult(
            success=False,
            subject_id=subject_id,
            session_id=session_id,
            error=str(e),
        )
