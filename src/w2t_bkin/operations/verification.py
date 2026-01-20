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
from w2t_bkin.models import DiscoveryResult, SessionInfo

logger = logging.getLogger(__name__)


def count_all_camera_frames(
    camera_files: Dict[str, List[Path]],
    session_info: SessionInfo,
) -> Dict[str, int]:
    """Count total frames for all cameras.

    Args:
        camera_files: Dictionary mapping camera_id to list of video paths
        session_info: Session configuration

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
    session_info: SessionInfo,
) -> Dict[str, int]:
    """Count total pulses for all TTL channels.

    Args:
        ttl_files: Dictionary mapping ttl_id to list of TTL file paths
        session_info: Session configuration

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
    session_info: SessionInfo,
    tolerance: int = 0,
) -> None:
    """Verify frame/TTL synchronization for all cameras.

    Args:
        frame_counts: Dictionary mapping camera_id to frame count
        ttl_counts: Dictionary mapping ttl_id to pulse count
        session_info: Session configuration
        tolerance: Allowed mismatch in frames

    Raises:
        CameraUnverifiableError: If camera references unknown TTL channel
        MismatchExceedsToleranceError: If mismatch exceeds tolerance
    """
    logger.info("Verifying camera-TTL synchronization")

    cameras = session_info.metadata.cameras

    for camera in cameras:
        camera_id = camera.id
        ttl_id = camera.ttl_id

        # Skip cameras without TTL sync
        if not ttl_id:
            logger.debug(f"  {camera_id}: No TTL sync configured (skipping)")
            continue

        # Check if camera is optional and missing/empty
        is_optional = camera.optional
        camera_frame_count = frame_counts.get(camera_id, 0)

        # Skip optional cameras with no discovered videos (frame_count=0 or missing)
        if is_optional and camera_frame_count == 0:
            logger.warning(f"  {camera_id}: Optional camera has no videos (skipping verification)")
            continue

        # Check if we have frame count for this camera (non-optional or optional with videos)
        if camera_id not in frame_counts:
            raise VerificationError(
                f"No frame count available for camera '{camera_id}'",
                context={"camera_id": camera_id},
                hint="Ensure video files were discovered and counted",
            )

        # Check if TTL channel exists
        if ttl_id not in ttl_counts:
            # Check if camera is optional
            if is_optional:
                logger.warning(f"  {camera_id}: TTL channel '{ttl_id}' not found (camera is optional, skipping)")
                continue
            else:
                raise CameraUnverifiableError(camera_id, ttl_id)

        # Verify synchronization using primitive
        verify_sync_counts(
            camera_id=camera_id,
            ttl_id=ttl_id,
            frame_count=camera_frame_count,
            pulse_count=ttl_counts[ttl_id],
            tolerance=tolerance,
        )
