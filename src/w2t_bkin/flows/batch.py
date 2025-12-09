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

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional

from prefect import flow, get_run_logger

from ..models import SessionResult
from ..utils import discover_sessions
from .session import process_session_flow

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
)
def batch_process_flow(
    config_path: str | Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
    max_parallel: int = 4,
    skip_bpod: bool = False,
    skip_pose: bool = False,
    skip_nwb_validation: bool = False,
) -> BatchResult:
    """Process multiple sessions in parallel using Prefect.

    This flow discovers sessions from the raw data directory, filters them
    according to the provided patterns, and processes them in parallel using
    the process_session_flow. Failed sessions do not stop the batch - all
    sessions are attempted and results are aggregated.

    Args:
        config_path: Path to configuration TOML file
        subject_filter: Subject ID filter pattern (e.g., "subject-*", "SNA-*")
        session_filter: Session ID filter pattern (e.g., "session-001")
        max_parallel: Maximum number of sessions to process in parallel
        skip_bpod: Skip Bpod behavioral data processing
        skip_pose: Skip all pose estimation processing
        skip_nwb_validation: Skip NWB file validation

    Returns:
        BatchResult with aggregated statistics and individual results

    Example:
        >>> # Process all sessions for a subject
        >>> result = batch_process_flow(
        ...     config_path="configs/standard.toml",
        ...     subject_filter="subject-001",
        ...     max_parallel=2
        ... )
        >>>
        >>> # Process specific session pattern across subjects
        >>> result = batch_process_flow(
        ...     config_path="configs/standard.toml",
        ...     session_filter="session-001",
        ...     max_parallel=4
        ... )
    """
    run_logger = get_run_logger()
    from datetime import datetime

    start_time = datetime.now()

    try:
        # =====================================================================
        # Phase 1: Discover Sessions
        # =====================================================================
        run_logger.info("Discovering sessions from raw data directory")

        # Discover all sessions using config path
        sessions = discover_sessions(
            config_path=config_path,
            subject_filter=subject_filter,
            session_filter=session_filter,
        )

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
        run_logger.info(f"Processing sessions (max_parallel: {max_parallel})")

        # Process sessions using ThreadPoolExecutor for parallelism
        session_results = []
        errors = {}
        successful = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # Submit all session processing tasks
            future_to_session = {}
            for session_info in sessions:
                subject_id = session_info["subject"]
                session_id = session_info["session"]
                future = executor.submit(
                    process_session_flow,
                    config_path=config_path,
                    subject_id=subject_id,
                    session_id=session_id,
                    skip_bpod=skip_bpod,
                    skip_pose=skip_pose,
                    skip_nwb_validation=skip_nwb_validation,
                )
                future_to_session[future] = (subject_id, session_id)

            # =====================================================================
            # Phase 3: Collect Results
            # =====================================================================
            run_logger.info("Collecting results from session flows")

            for future in as_completed(future_to_session):
                subject_id, session_id = future_to_session[future]
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
