"""Video frame synchronization utilities.

Provides high-level API for aligning video frame timestamps to a reference
timebase. Built on top of generic mapping strategies but with video-specific
semantics and return formats.

Example:
    >>> from w2t_bkin.sync import sync_video_frames_to_timebase, create_timebase_provider
    >>> from w2t_bkin.config import load_config
    >>>
    >>> # Create reference timebase
    >>> config = load_config("config.toml")
    >>> provider = create_timebase_provider(config, manifest=None)
    >>> reference_times = provider.get_timestamps(n_samples=10000)
    >>>
    >>> # Align video frames
    >>> result = sync_video_frames_to_timebase(
    ...     frame_indices=list(range(1000)),
    ...     frame_times=camera_timestamps,
    ...     reference_times=reference_times,
    ...     timebase_config=config.timebase,
    ...     enforce_budget=True
    ... )
    >>>
    >>> print(f"Aligned {len(result['frame_times_aligned'])} frames")
    >>> print(f"Max jitter: {result['jitter_stats']['max_jitter_s']:.4f}s")
"""

from typing import Dict, List

from ..domain import TimebaseConfig
from .mapping import align_samples

__all__ = ["sync_video_frames_to_timebase"]


def sync_video_frames_to_timebase(
    frame_indices: List[int],
    frame_times: List[float],
    reference_times: List[float],
    timebase_config: TimebaseConfig,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align video frames to reference timebase.

    High-level function for video frame synchronization. Takes camera frame
    timestamps and aligns them to a reference timebase, returning both the
    alignment indices and the aligned timestamps suitable for NWB assembly.

    Args:
        frame_indices: Frame numbers (typically 0, 1, 2, ..., n_frames-1)
        frame_times: Frame timestamps from camera (e.g., from video metadata)
        reference_times: Reference timebase (from TimebaseProvider)
        timebase_config: Timebase configuration with mapping strategy and jitter budget
        enforce_budget: Whether to enforce jitter budget (raises on exceed)

    Returns:
        Dictionary with:
        - indices: List[int] - alignment indices into reference_times
        - frame_times_aligned: List[float] - aligned frame timestamps
        - jitter_stats: Dict - max_jitter_s and p95_jitter_s
        - mapping: str - strategy used ("nearest" or "linear")

    Raises:
        JitterBudgetExceeded: If enforce_budget=True and jitter exceeds budget
        SyncError: If alignment fails

    Example:
        >>> # Video with 30 fps nominal rate
        >>> frame_times = [i / 30.0 for i in range(1000)]
        >>> frame_indices = list(range(1000))
        >>>
        >>> # Align to TTL-based reference
        >>> result = sync_video_frames_to_timebase(
        ...     frame_indices=frame_indices,
        ...     frame_times=frame_times,
        ...     reference_times=ttl_timestamps,
        ...     timebase_config=timebase_config,
        ...     enforce_budget=True
        ... )
        >>>
        >>> # Use aligned times for NWB
        >>> nwb_video_timestamps = result["frame_times_aligned"]
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
