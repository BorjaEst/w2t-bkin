"""FaceMap output synchronization utilities.

Provides high-level API for aligning FaceMap-derived behavioral traces
(motion energy, pupil diameter, etc.) to a reference timebase.

FaceMap outputs are typically frame-aligned with video, but this module
supports both video-derived and independent FaceMap timestamps.

Example:
    >>> from w2t_bkin.sync import sync_facemap_to_timebase
    >>>
    >>> # FaceMap outputs at video frame rate
    >>> facemap_times = video_frame_times  # Same as video
    >>> result = sync_facemap_to_timebase(
    ...     facemap_times=facemap_times,
    ...     reference_times=reference_timebase,
    ...     config=timebase_config
    ... )
    >>>
    >>> # Use aligned times for NWB FaceMap behavioral data
    >>> nwb_facemap_timestamps = result["facemap_times_aligned"]
"""

from typing import Dict, List

from ..domain import TimebaseConfig
from .mapping import align_samples

__all__ = ["sync_facemap_to_timebase"]


def sync_facemap_to_timebase(
    facemap_times: List[float],
    reference_times: List[float],
    config: TimebaseConfig,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align FaceMap-derived behavioral traces to reference timebase.

    FaceMap outputs (motion energy, pupil metrics, etc.) are synchronized
    to a reference timebase for integration with other modalities in NWB.

    If FaceMap outputs are strictly video-frame-aligned, consider using the
    video frame alignment directly to avoid redundant computation.

    Args:
        facemap_times: FaceMap sample timestamps (typically per video frame)
        reference_times: Reference timebase (from TimebaseProvider)
        config: Timebase configuration with mapping strategy and jitter budget
        enforce_budget: Whether to enforce jitter budget (raises on exceed)

    Returns:
        Dictionary with:
        - indices: List[int] - alignment indices into reference_times
        - facemap_times_aligned: List[float] - aligned FaceMap timestamps
        - jitter_stats: Dict - max_jitter_s and p95_jitter_s
        - mapping: str - strategy used ("nearest" or "linear")

    Raises:
        JitterBudgetExceeded: If enforce_budget=True and jitter exceeds budget
        SyncError: If alignment fails

    Example:
        >>> # FaceMap processing output
        >>> facemap_motion = load_facemap_motion("facemap_proc.npy")
        >>> facemap_times = [i / 30.0 for i in range(len(facemap_motion))]
        >>>
        >>> # Sync to reference timebase
        >>> result = sync_facemap_to_timebase(
        ...     facemap_times=facemap_times,
        ...     reference_times=ttl_reference,
        ...     config=timebase_config
        ... )
        >>>
        >>> # Store in NWB
        >>> nwb_behavior_module.add_timeseries(
        ...     name="facemap_motion",
        ...     data=facemap_motion,
        ...     timestamps=result["facemap_times_aligned"]
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
