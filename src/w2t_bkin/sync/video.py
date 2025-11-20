"""Align video frames to reference timebase.

Example:
    >>> result = sync_video_frames_to_timebase(
    ...     frame_indices=list(range(100)),
    ...     frame_times=frame_times,
    ...     reference_times=reference,
    ...     timebase_config=config
    ... )
"""

from typing import Dict, List

from .mapping import align_samples
from .protocols import TimebaseConfigProtocol

__all__ = ["sync_video_frames_to_timebase"]


def sync_video_frames_to_timebase(
    frame_indices: List[int],
    frame_times: List[float],
    reference_times: List[float],
    timebase_config: TimebaseConfigProtocol,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align video frame timestamps to reference timebase.

    Args:
        frame_indices: Frame numbers
        frame_times: Frame timestamps
        reference_times: Reference timebase
        timebase_config: Timebase configuration
        enforce_budget: Enforce jitter budget

    Returns:
        Dict with indices, frame_times_aligned, jitter_stats, and mapping

    Raises:
        JitterExceedsBudgetError: Jitter exceeds budget
        SyncError: Alignment failed

    Example:
        >>> result = sync_video_frames_to_timebase(
        ...     frame_indices=list(range(100)),
        ...     frame_times=[i/30.0 for i in range(100)],
        ...     reference_times=reference,
        ...     timebase_config=config
        ... )
    """
    # Perform alignment using generic strategy
    result = align_samples(frame_times, reference_times, timebase_config, enforce_budget)

    indices = result["indices"]

    # Extract aligned timestamps from reference
    if timebase_config.mapping == "nearest":
        # Simple indexing for nearest neighbor
        frame_times_aligned = [reference_times[idx] for idx in indices]
    elif timebase_config.mapping == "linear":
        # Weighted average for linear interpolation
        frame_times_aligned = []
        weights = result.get("weights", [])
        for (idx0, idx1), (w0, w1) in zip(indices, weights):
            t_aligned = w0 * reference_times[idx0] + w1 * reference_times[idx1]
            frame_times_aligned.append(t_aligned)
    else:
        # Fallback: use nearest
        frame_times_aligned = [reference_times[indices[0]] for _ in frame_indices]

    return {
        "indices": indices,
        "frame_times_aligned": frame_times_aligned,
        "jitter_stats": result["jitter_stats"],
        "mapping": result["mapping"],
    }
