"""Align pose estimation data to reference timebase.

Example:
    >>> result = sync_pose_to_timebase(
    ...     pose_times=pose_times,
    ...     reference_times=reference,
    ...     config=config
    ... )
"""

from typing import Dict, List

from .mapping import align_samples
from .protocols import TimebaseConfigProtocol

__all__ = ["sync_pose_to_timebase"]


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
