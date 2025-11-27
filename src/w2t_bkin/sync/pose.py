"""Align pose estimation data to reference timebase.

Example:
    >>> result = sync_pose_to_timebase(
    ...     pose_times=pose_times,
    ...     reference_times=reference,
    ...     config=config
    ... )
"""

import logging
from typing import Dict, List

from ..exceptions import SyncError
from .mapping import align_samples
from .protocols import TimebaseConfigProtocol

logger = logging.getLogger(__name__)

__all__ = ["sync_pose_to_timebase", "align_pose_frames_to_reference"]


def sync_pose_to_timebase(
    pose_times: List[float],
    reference_times: List[float],
    config: TimebaseConfigProtocol,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align pose timestamps to reference timebase.

    Args:
        pose_times: Pose sample timestamps
        reference_times: Reference timebase
        config: Timebase configuration
        enforce_budget: Enforce jitter budget

    Returns:
        Dict with indices, pose_times_aligned, jitter_stats, and mapping

    Raises:
        JitterExceedsBudgetError: Jitter exceeds budget
        SyncError: Alignment failed

    Example:
        >>> result = sync_pose_to_timebase(
        ...     pose_times=[i/30.0 for i in range(100)],
        ...     reference_times=reference,
        ...     config=config
        ... )
    """
    # Perform alignment using generic strategy
    result = align_samples(pose_times, reference_times, config, enforce_budget)

    indices = result["indices"]

    # Extract aligned timestamps from reference
    if config.mapping == "nearest":
        # Simple indexing for nearest neighbor
        pose_times_aligned = [reference_times[idx] for idx in indices]
    elif config.mapping == "linear":
        # Weighted average for linear interpolation
        pose_times_aligned = []
        weights = result.get("weights", [])
        for (idx0, idx1), (w0, w1) in zip(indices, weights):
            t_aligned = w0 * reference_times[idx0] + w1 * reference_times[idx1]
            pose_times_aligned.append(t_aligned)
    else:
        # Fallback: use nearest
        pose_times_aligned = [reference_times[indices[0]] for _ in pose_times]

    return {
        "indices": indices,
        "pose_times_aligned": pose_times_aligned,
        "jitter_stats": result["jitter_stats"],
        "mapping": result["mapping"],
    }


def align_pose_frames_to_reference(
    pose_data: List[Dict],
    reference_times: List[float],
    mapping: str = "nearest",
) -> Dict[int, float]:
    """Align pose frame indices to reference timebase (returns offsets only).

    Follows the behavior module pattern: returns frame_index → timestamp mapping
    that can be used to add timestamps to pose data before building NWB objects.

    Algorithm:
    ----------
    1. For each pose frame, extract frame_index
    2. Map frame_index to reference timestamp using strategy (nearest/linear)
    3. Return dict of frame_index → absolute_timestamp

    Edge Cases:
    -----------
    - Frame index out of bounds: Use last timestamp (nearest) or extrapolate (linear)
    - Empty keypoints: Still return timestamp for frame

    Args:
        pose_data: Harmonized pose data (List of dicts with frame_index, keypoints)
        reference_times: Reference timestamps (sorted, typically from video TTL)
        mapping: Alignment strategy ("nearest" or "linear")

    Returns:
        Dict mapping frame_index → absolute timestamp

    Raises:
        SyncError: If mapping strategy invalid or data malformed

    Example:
        >>> harmonized = harmonize_to_canonical(raw_data, skeleton_map, source="dlc")
        >>> timestamps = align_pose_frames_to_reference(
        ...     pose_data=harmonized,
        ...     reference_times=video_ttl_times,
        ...     mapping="nearest"
        ... )
        >>> # Apply timestamps to data
        >>> for frame in harmonized:
        ...     frame["timestamp"] = timestamps[frame["frame_index"]]
        >>> # Now build PoseEstimation with timestamped data

    Note:
        This returns offsets only. Use pose.build_pose_estimation() to create
        the actual NWB PoseEstimation object after adding timestamps.
    """
    if not pose_data:
        return {}

    if not reference_times:
        raise SyncError("Reference timebase is empty")

    if mapping not in ["nearest", "linear"]:
        raise SyncError(f"Unknown mapping strategy: {mapping}")

    frame_timestamps = {}

    for frame_data in pose_data:
        frame_idx = frame_data["frame_index"]

        # Get timestamp based on mapping strategy
        if mapping == "nearest":
            if frame_idx < len(reference_times):
                timestamp = reference_times[frame_idx]
            else:
                # Out of bounds - use last timestamp
                logger.warning(f"Frame {frame_idx} out of bounds, using last timestamp")
                timestamp = reference_times[-1]

        elif mapping == "linear":
            if frame_idx < len(reference_times):
                timestamp = reference_times[frame_idx]
            else:
                # Linear extrapolation
                if len(reference_times) >= 2:
                    dt = reference_times[-1] - reference_times[-2]
                    timestamp = reference_times[-1] + dt * (frame_idx - len(reference_times) + 1)
                else:
                    timestamp = reference_times[-1]

        frame_timestamps[frame_idx] = timestamp

    logger.debug(f"Aligned {len(frame_timestamps)} pose frames to reference timebase")
    return frame_timestamps
