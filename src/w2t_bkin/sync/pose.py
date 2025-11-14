"""Pose estimation synchronization utilities.

Provides high-level API for aligning pose estimation outputs (DeepLabCut,
SLEAP, etc.) to a reference timebase. Handles both video-frame-aligned
and independent pose timestamps.

Example:
    >>> from w2t_bkin.sync import sync_pose_to_timebase
    >>>
    >>> # DeepLabCut outputs at video frame rate
    >>> pose_times = video_frame_times  # Typically same as video
    >>> result = sync_pose_to_timebase(
    ...     pose_times=pose_times,
    ...     reference_times=reference_timebase,
    ...     config=timebase_config
    ... )
    >>>
    >>> # Use aligned times for NWB pose data
    >>> nwb_pose_timestamps = result["pose_times_aligned"]
"""

from typing import Dict, List

from ..domain import TimebaseConfig
from .mapping import align_samples

__all__ = ["sync_pose_to_timebase"]


def sync_pose_to_timebase(
    pose_times: List[float],
    reference_times: List[float],
    config: TimebaseConfig,
    enforce_budget: bool = False,
) -> Dict[str, any]:
    """Align pose keypoint timestamps to reference timebase.

    Synchronizes pose estimation outputs (e.g., from DeepLabCut, SLEAP) to
    a reference timebase for integration with other modalities in NWB.

    Pose data is typically video-frame-aligned (one pose per frame), but
    this function supports any timestamp source including sparse detections.

    Args:
        pose_times: Pose sample timestamps (typically per video frame or detection)
        reference_times: Reference timebase (from TimebaseProvider)
        config: Timebase configuration with mapping strategy and jitter budget
        enforce_budget: Whether to enforce jitter budget (raises on exceed)

    Returns:
        Dictionary with:
        - indices: List[int] - alignment indices into reference_times
        - pose_times_aligned: List[float] - aligned pose timestamps
        - jitter_stats: Dict - max_jitter_s and p95_jitter_s
        - mapping: str - strategy used ("nearest" or "linear")

    Raises:
        JitterBudgetExceeded: If enforce_budget=True and jitter exceeds budget
        SyncError: If alignment fails

    Example:
        >>> # DeepLabCut pose output
        >>> dlc_df = pd.read_hdf("pose_dlc.h5")
        >>> n_frames = len(dlc_df)
        >>> pose_times = [i / 30.0 for i in range(n_frames)]
        >>>
        >>> # Sync to reference timebase
        >>> result = sync_pose_to_timebase(
        ...     pose_times=pose_times,
        ...     reference_times=ttl_reference,
        ...     config=timebase_config
        ... )
        >>>
        >>> # Extract keypoints and timestamps for NWB
        >>> nose_x = dlc_df["nose"]["x"].values
        >>> nose_y = dlc_df["nose"]["y"].values
        >>> timestamps = result["pose_times_aligned"]
        >>>
        >>> # Store in NWB PoseEstimation module
        >>> nwb_pose.add_spatial_series(
        ...     name="nose_position",
        ...     data=np.column_stack([nose_x, nose_y]),
        ...     timestamps=timestamps
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
