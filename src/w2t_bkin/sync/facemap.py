"""Align FaceMap outputs to reference timebase.

Example:
    >>> result = sync_facemap_to_timebase(
    ...     facemap_times=facemap_times,
    ...     reference_times=reference,
    ...     config=config
    ... )
"""

from typing import Dict, List

from .mapping import align_samples
from .protocols import TimebaseConfigProtocol

__all__ = ["sync_facemap_to_timebase"]


def sync_facemap_to_timebase(
    facemap_times: List[float],
    reference_times: List[float],
    config: TimebaseConfigProtocol,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align FaceMap timestamps to reference timebase.

    Args:
        facemap_times: FaceMap sample timestamps
        reference_times: Reference timebase
        config: Timebase configuration
        enforce_budget: Enforce jitter budget

    Returns:
        Dict with indices, facemap_times_aligned, jitter_stats, and mapping

    Raises:
        JitterExceedsBudgetError: Jitter exceeds budget
        SyncError: Alignment failed

    Example:
        >>> result = sync_facemap_to_timebase(
        ...     facemap_times=[i/30.0 for i in range(100)],
        ...     reference_times=reference,
        ...     config=config
        ... )
    """
    # Perform alignment using generic strategy
    result = align_samples(facemap_times, reference_times, config, enforce_budget)

    indices = result["indices"]

    # Extract aligned timestamps from reference
    if config.mapping == "nearest":
        # Simple indexing for nearest neighbor
        facemap_times_aligned = [reference_times[idx] for idx in indices]
    elif config.mapping == "linear":
        # Weighted average for linear interpolation
        facemap_times_aligned = []
        weights = result.get("weights", [])
        for (idx0, idx1), (w0, w1) in zip(indices, weights):
            t_aligned = w0 * reference_times[idx0] + w1 * reference_times[idx1]
            facemap_times_aligned.append(t_aligned)
    else:
        # Fallback: use nearest
        facemap_times_aligned = [reference_times[indices[0]] for _ in facemap_times]

    return {
        "indices": indices,
        "facemap_times_aligned": facemap_times_aligned,
        "jitter_stats": result["jitter_stats"],
        "mapping": result["mapping"],
    }
