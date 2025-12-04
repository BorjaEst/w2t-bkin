"""Batch processing orchestration for W2T Body Kinematics Pipeline.

This module implements parallel batch processing of multiple subjects/sessions.
It wraps the existing SessionPipeline without requiring any changes to the core
pipeline logic.

Two implementations are provided:
1. Simple multiprocessing-based batch processing (default, no dependencies)
2. Prefect-based orchestration (optional, requires Prefect server)

Architecture:
-------------
- process_single_session: Function that wraps SessionPipeline.run()
- batch_process_sessions: Orchestrates parallel session processing

Features:
---------
- Parallel execution via multiprocessing
- Automatic retries (2 attempts)
- Concurrency control via max_workers
- Graceful error handling (partial failures)
- Optional Prefect integration for observability
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
from pathlib import Path
import time
from typing import Optional

from ..core.pipeline import SessionPipeline
from ..utils import discover_sessions

logger = logging.getLogger(__name__)

# Try to import Prefect (optional dependency)
try:
    from prefect import flow, task
    from prefect.logging import get_run_logger

    PREFECT_AVAILABLE = True
except (ImportError, NameError, AttributeError) as e:
    PREFECT_AVAILABLE = False
    logger.debug(f"Prefect not available: {e}. Using multiprocessing fallback.")


def _process_with_retry(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
    max_retries: int = 2,
) -> dict:
    """Process a single session with retry logic.

    Returns dict with session result (only counts as 1 regardless of retries).

    Args:
        config_path: Path to configuration file
        subject_id: Subject identifier
        session_id: Session identifier
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with execution results and status
    """
    session_label = f"{subject_id}/{session_id}"
    logger.info(f"▶ Processing {session_label}")

    for attempt in range(max_retries + 1):
        try:
            pipeline = SessionPipeline(
                config_path=config_path,
                subject_id=subject_id,
                session_id=session_id,
            )

            result = pipeline.run()
            logger.info(f"✓ Completed {session_label} (attempt {attempt + 1}/{max_retries + 1})")

            return {
                "subject_id": subject_id,
                "session_id": session_id,
                "success": True,
                "nwb_path": str(result.nwb_path) if result.nwb_path else None,
                "error": None,
                "attempts": attempt + 1,  # Track how many attempts it took
            }

        except Exception as e:
            if attempt < max_retries:
                wait_time = 60 * (attempt + 1)
                logger.warning(f"⚠ Attempt {attempt + 1}/{max_retries + 1} failed for {session_label}: {e}. " f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"✗ Failed {session_label} after {max_retries + 1} attempts: {e}")
                return {
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "success": False,
                    "nwb_path": None,
                    "error": str(e),
                    "attempts": attempt + 1,
                }

    # Should never reach here
    return {
        "subject_id": subject_id,
        "session_id": session_id,
        "success": False,
        "nwb_path": None,
        "error": "Unknown error",
        "attempts": max_retries + 1,
    }


def batch_process_sessions(
    config_path: str | Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
    max_workers: int = 4,
) -> dict:
    """Orchestrate batch processing of multiple sessions using multiprocessing.

    This function discovers available sessions and processes them in parallel
    using Python's ProcessPoolExecutor. Provides automatic retries and
    graceful error handling.

    Args:
        config_path: Path to configuration file
        subject_filter: Optional subject ID filter
        session_filter: Optional session ID filter
        max_workers: Maximum concurrent sessions (controls parallelism)

    Returns:
        Summary dictionary with:
        - total: Total number of sessions discovered
        - successful: Number of successfully processed sessions
        - failed: Number of failed sessions
        - results: List of per-session results

    Example:
        >>> from w2t_bkin.orchestration import batch_process_sessions
        >>>
        >>> # Process all sessions
        >>> result = batch_process_sessions("config.toml", max_workers=4)
        >>> print(f"Processed {result['successful']}/{result['total']} sessions")
        >>>
        >>> # Filter by subject
        >>> result = batch_process_sessions(
        ...     "config.toml",
        ...     subject_filter="subject-001",
        ...     max_workers=2,
        ... )
        >>>
        >>> # Check for failures
        >>> if result['failed'] > 0:
        ...     for r in result['results']:
        ...         if not r['success']:
        ...             print(f"Failed: {r['subject_id']}/{r['session_id']}")
        ...             print(f"Error: {r['error']}")
    """
    # Discover sessions
    logger.info(f"Discovering sessions from {config_path}")
    sessions = discover_sessions(
        config_path=config_path,
        subject_filter=subject_filter,
        session_filter=session_filter,
    )

    total = len(sessions)
    logger.info(f"Found {total} session(s) to process")

    if total == 0:
        logger.warning("No sessions found!")
        return {"total": 0, "successful": 0, "failed": 0, "results": []}

    # Process sessions in parallel
    logger.info(f"🚀 Processing {total} sessions with max_workers={max_workers}")
    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all sessions
        future_to_session = {
            executor.submit(
                _process_with_retry,
                str(config_path),
                session_info["subject"],
                session_info["session"],
            ): session_info
            for session_info in sessions
        }

        # Collect results as they complete
        for future in as_completed(future_to_session):
            session_info = future_to_session[future]
            session_label = f"{session_info['subject']}/{session_info['session']}"

            try:
                result = future.result()
                results.append(result)
                completed += 1

                # Progress indicator
                status = "✓" if result["success"] else "✗"
                logger.info(f"{status} [{completed}/{total}] {session_label}")

            except Exception as e:
                logger.error(f"✗ [{completed + 1}/{total}] {session_label}: " f"Unexpected executor error: {e}")
                results.append(
                    {
                        "subject_id": session_info["subject"],
                        "session_id": session_info["session"],
                        "success": False,
                        "nwb_path": None,
                        "error": f"Executor error: {str(e)}",
                        "attempts": 1,
                    }
                )
                completed += 1

    # Calculate summary (each session counts once)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful

    # Calculate retry statistics
    retry_stats = {
        "sessions_with_retries": sum(1 for r in results if r.get("attempts", 1) > 1),
        "total_attempts": sum(r.get("attempts", 1) for r in results),
    }

    logger.info(f"📊 Batch complete: {successful}/{total} sessions successful, {failed} failed")
    if retry_stats["sessions_with_retries"] > 0:
        logger.info(f"   Retries: {retry_stats['sessions_with_retries']} session(s) needed retries " f"({retry_stats['total_attempts']} total attempts)")

    # Log failed sessions for easy debugging
    if failed > 0:
        logger.warning("❌ Failed sessions:")
        for r in results:
            if not r["success"]:
                logger.warning(f"  - {r['subject_id']}/{r['session_id']}: {r['error']}")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "results": results,
        "retry_stats": retry_stats,  # Add retry information
    }


# Prefect-based implementation (optional, requires working Prefect installation)
if PREFECT_AVAILABLE:

    @task(
        name="process-session",
        retries=2,
        retry_delay_seconds=60,
        log_prints=True,
        tags=["pipeline", "session"],
    )
    def process_single_session(
        config_path: str | Path,
        subject_id: str,
        session_id: str,
    ) -> dict:
        """Prefect task wrapper for processing a single session."""
        return _process_with_retry(config_path, subject_id, session_id)

    @flow(
        name="batch-process-sessions-prefect",
        log_prints=True,
        description="Process multiple subjects/sessions in parallel using Prefect",
    )
    def batch_process_sessions_prefect(
        config_path: str | Path,
        subject_filter: Optional[str] = None,
        session_filter: Optional[str] = None,
        max_workers: int = 4,
    ) -> dict:
        """Prefect flow for batch processing (requires Prefect server)."""
        flow_logger = get_run_logger()

        # Discover sessions
        flow_logger.info(f"Discovering sessions from {config_path}")
        sessions = discover_sessions(
            config_path=config_path,
            subject_filter=subject_filter,
            session_filter=session_filter,
        )

        total = len(sessions)
        flow_logger.info(f"Found {total} session(s) to process")

        if total == 0:
            flow_logger.warning("No sessions found!")
            return {"total": 0, "successful": 0, "failed": 0, "results": []}

        # Submit all sessions as parallel tasks
        flow_logger.info(f"Submitting {total} tasks with max_workers={max_workers}")

        futures = []
        for session_info in sessions:
            future = process_single_session.submit(
                config_path=str(config_path),
                subject_id=session_info["subject"],
                session_id=session_info["session"],
            )
            futures.append(future)

        # Wait for all tasks to complete
        flow_logger.info("Waiting for all tasks to complete...")
        results = [f.result() for f in futures]

        # Calculate summary
        successful = sum(1 for r in results if r["success"])
        failed = total - successful

        flow_logger.info(f"Batch processing complete: {successful}/{total} successful, {failed} failed")

        # Log failed sessions
        if failed > 0:
            flow_logger.warning("Failed sessions:")
            for r in results:
                if not r["success"]:
                    flow_logger.warning(f"  - {r['subject_id']}/{r['session_id']}: {r['error']}")

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "results": results,
        }

else:
    # Stub functions if Prefect is not available
    def process_single_session(*args, **kwargs):
        """Stub - Prefect not available."""
        raise ImportError("Prefect is not available. Use batch_process_sessions instead.")

    def batch_process_sessions_prefect(*args, **kwargs):
        """Stub - Prefect not available."""
        raise ImportError("Prefect is not available. Use batch_process_sessions instead.")


# Compatibility: Keep old function signature
process_single_session_compat = _process_with_retry
