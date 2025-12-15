"""Prefect tasks for pre-processing verification."""

import logging
from typing import Any, Dict

from prefect import task

from w2t_bkin.models import DiscoveryResult, SessionConfig
from w2t_bkin.operations import verify_session_inputs

logger = logging.getLogger(__name__)


@task(
    name="Verify Session Inputs",
    description="Verify session inputs before processing (fail-fast)",
    tags=["verification", "pre-processing", "fail-fast"],
    retries=0,  # No retries - verification failures should fail immediately
    timeout_seconds=600,  # 10 minute timeout for large sessions
)
def verify_session_inputs_task(
    discovery: DiscoveryResult,
    session_config: SessionConfig,
    skip_camera_sync: bool = False,
) -> Dict[str, Any]:
    """Verify session inputs before processing (fail-fast).

    Prefect task wrapper for verify_session_inputs operation.
    Performs early verification checks to detect problems before expensive
    processing begins.

    Args:
        discovery: File discovery results
        session_config: Session configuration
        skip_camera_sync: Skip camera-TTL frame counting (runtime override)

    Returns:
        Dictionary containing verification results:
        - skipped: True if verification disabled
        - frame_counts: Dict[camera_id, frame_count] (if enabled)
        - ttl_counts: Dict[ttl_id, pulse_count] (if enabled)
        - verified_cameras: List of camera IDs that passed verification

    Raises:
        VerificationError: If verification checks fail
        CameraUnverifiableError: If camera references unknown TTL
        MismatchExceedsToleranceError: If frame/TTL mismatch exceeds tolerance
    """
    logger.info("Verifying session inputs (fail-fast)")

    return verify_session_inputs(
        discovery=discovery,
        session_config=session_config,
        skip_camera_sync=skip_camera_sync,
    )
