"""Pure functions for pre-processing verification (fail-fast checks).

This module implements verification checks that run early in the pipeline
to detect problems before expensive processing begins.

Verification vs Validation:
- Verification: Pre-processing checks on inputs (this module)
- Validation: Post-processing checks on outputs (finalization module)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from w2t_bkin import utils
from w2t_bkin.core.validate import verify_sync_counts
from w2t_bkin.exceptions import CameraUnverifiableError, VerificationError
from w2t_bkin.models import DiscoveryResult, SessionConfig

logger = logging.getLogger(__name__)


def count_all_camera_frames(
    camera_files: Dict[str, List[Path]],
    session_config: SessionConfig,
) -> Dict[str, int]:
    """Count total frames for all cameras.

    Args:
        camera_files: Dictionary mapping camera_id to list of video paths
        session_config: Session configuration

    Returns:
        Dictionary mapping camera_id to total frame count

    Raises:
        RuntimeError: If frame counting fails for any video
    """
    logger.info("Counting frames for all cameras")

    frame_counts = {}

    for camera_id, video_paths in camera_files.items():
        total_frames = 0

        for video_path in video_paths:
            try:
                frame_count = utils.count_video_frames(video_path)
                total_frames += frame_count
                logger.debug(f"  {camera_id}/{video_path.name}: {frame_count} frames")
            except Exception as e:
                raise RuntimeError(f"Failed to count frames for {camera_id}/{video_path.name}: {e}")

        frame_counts[camera_id] = total_frames
        logger.info(f"  {camera_id}: {total_frames} total frames")

    return frame_counts


def count_all_ttl_pulses(
    ttl_files: Dict[str, List[Path]],
    session_config: SessionConfig,
) -> Dict[str, int]:
    """Count total pulses for all TTL channels.

    Args:
        ttl_files: Dictionary mapping ttl_id to list of TTL file paths
        session_config: Session configuration

    Returns:
        Dictionary mapping ttl_id to total pulse count
    """
    logger.info("Counting TTL pulses for all channels")

    pulse_counts = {}

    for ttl_id, ttl_paths in ttl_files.items():
        total_pulses = 0

        for ttl_path in ttl_paths:
            pulse_count = utils.count_ttl_pulses(ttl_path)
            total_pulses += pulse_count
            logger.debug(f"  {ttl_id}/{ttl_path.name}: {pulse_count} pulses")

        pulse_counts[ttl_id] = total_pulses
        logger.info(f"  {ttl_id}: {total_pulses} total pulses")

    return pulse_counts


def verify_camera_ttl_sync(
    frame_counts: Dict[str, int],
    ttl_counts: Dict[str, int],
    session_config: SessionConfig,
    tolerance: int = 0,
) -> None:
    """Verify frame/TTL synchronization for all cameras.

    Args:
        frame_counts: Dictionary mapping camera_id to frame count
        ttl_counts: Dictionary mapping ttl_id to pulse count
        session_config: Session configuration
        tolerance: Allowed mismatch in frames

    Raises:
        CameraUnverifiableError: If camera references unknown TTL channel
        MismatchExceedsToleranceError: If mismatch exceeds tolerance
    """
    logger.info("Verifying camera-TTL synchronization")

    cameras = session_config.metadata.get("cameras", [])

    for camera in cameras:
        camera_id = camera["id"]
        ttl_id = camera.get("ttl_id")

        # Skip cameras without TTL sync
        if not ttl_id:
            logger.debug(f"  {camera_id}: No TTL sync configured (skipping)")
            continue

        # Check if we have frame count for this camera
        if camera_id not in frame_counts:
            raise VerificationError(
                f"No frame count available for camera '{camera_id}'",
                context={"camera_id": camera_id},
                hint="Ensure video files were discovered and counted",
            )

        # Check if TTL channel exists
        if ttl_id not in ttl_counts:
            # Check if camera is optional
            if camera.get("optional", False):
                logger.warning(f"  {camera_id}: TTL channel '{ttl_id}' not found (camera is optional, skipping)")
                continue
            else:
                raise CameraUnverifiableError(camera_id, ttl_id)

        # Verify synchronization using primitive
        verify_sync_counts(
            camera_id=camera_id,
            ttl_id=ttl_id,
            frame_count=frame_counts[camera_id],
            pulse_count=ttl_counts[ttl_id],
            tolerance=tolerance,
        )


def verify_session_inputs(
    discovery: DiscoveryResult,
    session_config: SessionConfig,
    skip_camera_sync: bool = False,
) -> Dict[str, Any]:
    """Verify session inputs before processing (fail-fast).

    Performs early verification checks to detect problems before expensive
    processing begins (e.g., DLC inference). This implements the "fail fast"
    principle.

    Checks performed (controlled by verification config):
    - Frame counts for all cameras (if check_frame_counts=True and not skip_camera_sync)
    - TTL pulse counts (if check_sync_mismatch=True and not skip_camera_sync)
    - Frame/TTL synchronization (if check_sync_mismatch=True and not skip_camera_sync)

    Args:
        discovery: File discovery results
        session_config: Session configuration
        skip_camera_sync: Skip camera-TTL frame counting verification (runtime override)

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
    verification_config = session_config.config.verification

    # Check if verification is disabled
    if not verification_config.enabled:
        logger.info("Verification disabled (verification.enabled=false)")
        return {"skipped": True}

    logger.info("Starting session input verification")

    results = {}

    # Count frames for all cameras
    if verification_config.check_frame_counts and not skip_camera_sync:
        results["frame_counts"] = count_all_camera_frames(
            camera_files=discovery.camera_files,
            session_config=session_config,
        )
    else:
        if skip_camera_sync:
            logger.info("Frame counting skipped (skip_camera_sync=True)")
        else:
            logger.info("Frame counting disabled (verification.check_frame_counts=false)")
        results["frame_counts"] = {}

    # Count TTL pulses and verify synchronization
    if verification_config.check_sync_mismatch and not skip_camera_sync:
        # Count pulses
        results["ttl_counts"] = count_all_ttl_pulses(
            ttl_files=discovery.ttl_files,
            session_config=session_config,
        )

        # Verify synchronization
        if results["frame_counts"] and results["ttl_counts"]:
            verify_camera_ttl_sync(
                frame_counts=results["frame_counts"],
                ttl_counts=results["ttl_counts"],
                session_config=session_config,
                tolerance=verification_config.mismatch_tolerance_frames,
            )

            # Track which cameras were verified
            cameras_with_ttl = [cam["id"] for cam in session_config.metadata.get("cameras", []) if cam.get("ttl_id")]
            results["verified_cameras"] = cameras_with_ttl
        else:
            logger.warning("Cannot verify synchronization: missing frame or TTL counts")
            results["verified_cameras"] = []
    else:
        if skip_camera_sync:
            logger.info("Sync verification skipped (skip_camera_sync=True)")
        else:
            logger.info("Sync verification disabled (verification.check_sync_mismatch=false)")
        results["ttl_counts"] = {}
        results["verified_cameras"] = []

    logger.info(f"Verification complete: {len(results.get('verified_cameras', []))} cameras verified")

    return results
