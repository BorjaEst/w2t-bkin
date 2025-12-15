"""Core synchronization logic and algorithms.

This module consolidates the core synchronization functionality, including:
1. Low-level alignment algorithms (nearest neighbor, linear interpolation)
2. Jitter computation and budget enforcement
3. High-level stream synchronization utilities
4. Protocol definitions for configuration

Key Concepts:
-------------
- **Sample Times**: The original timestamps recorded by your data stream's internal
  clock (e.g., video camera's timer, pose estimation software's clock). These may
  have clock drift or offset relative to other devices.

- **Reference Times**: The ground-truth timestamps from hardware synchronization
  signals (e.g., TTL pulses from a master clock). These define the canonical
  timebase that all data streams should align to.

- **Synchronized Times**: Sample times that have been **mapped** to the reference
  timebase. These are NOT the raw reference times—they are your original sample
  times adjusted to account for clock drift and offset between your device and
  the reference clock.

- **Alignment**: The process of finding the mapping between sample_times and
  reference_times, then computing synchronized times that place your samples on
  the reference timebase.

Clock Drift Example:
--------------------
    Device Clock (sample_times):  [0.0, 1.0, 2.0, 3.0, 4.0]  # 1 Hz
    Reference Clock:               [0.0, 1.01, 2.02, 3.03, 4.04]  # 1% drift

    Synchronized times:            [0.0, 1.01, 2.02, 3.03, 4.04]
    # ^ Sample times mapped to reference clock to correct for drift

Typical Workflow:
-----------------
1. Acquire TTL pulses from hardware (e.g., camera trigger signals)
2. Use TTL timestamps as reference_times
3. Align each data stream (video, pose, facemap) to reference_times
4. Use synchronized times (NOT raw sample times) when building NWB objects
"""

import logging
from typing import Any, Dict, List, Literal, Protocol, Tuple
import warnings

import numpy as np
from scipy import stats

from w2t_bkin.exceptions import JitterExceedsBudgetError, SyncError

logger = logging.getLogger(__name__)


# =============================================================================
# Protocols
# =============================================================================


class TimebaseConfigProtocol(Protocol):
    """Protocol for timebase configuration access.

    Defines minimal interface needed by sync modules without importing
    from domain.config.TimebaseConfig.

    Attributes:
        method: Alignment strategy ("nearest" or "linear")
        tolerance_s: Maximum acceptable jitter in seconds
    """

    method: Literal["nearest", "linear"]
    tolerance_s: float


# =============================================================================
# Mapping Strategies (Primitives)
# =============================================================================


def map_nearest(sample_times: List[float], reference_times: List[float]) -> List[int]:
    """Map samples to nearest reference timestamps.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase (sorted)

    Returns:
        List of indices into reference_times

    Raises:
        SyncError: Empty or non-monotonic reference

    Example:
        >>> indices = map_nearest([0.3, 1.7], [0.0, 1.0, 2.0])
    """
    if not reference_times:
        raise SyncError("Cannot map to empty reference timebase")

    # Check monotonicity
    if reference_times != sorted(reference_times):
        raise SyncError("Reference timestamps must be monotonic")

    if not sample_times:
        return []

    # Check for large gaps and warn
    ref_array = np.array(reference_times)
    indices = []

    for sample_time in sample_times:
        # Find nearest index
        idx = np.argmin(np.abs(ref_array - sample_time))
        indices.append(int(idx))

        # Check for large gaps
        gap = abs(ref_array[idx] - sample_time)
        if gap > 1.0:  # > 1 second gap
            warnings.warn(f"Sample time {sample_time} has large gap ({gap:.3f}s) from nearest reference", UserWarning)

    return indices


def map_linear(sample_times: List[float], reference_times: List[float]) -> Tuple[List[Tuple[int, int]], List[Tuple[float, float]]]:
    """Map samples using linear interpolation.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase (sorted)

    Returns:
        (indices, weights) where indices are (idx0, idx1) pairs and
        weights are (w0, w1) for interpolation

    Raises:
        SyncError: Empty or non-monotonic reference

    Example:
        >>> indices, weights = map_linear([0.5], [0.0, 1.0])
    """
    if not reference_times:
        raise SyncError("Cannot map to empty reference timebase")

    if reference_times != sorted(reference_times):
        raise SyncError("Reference timestamps must be monotonic")

    if not sample_times:
        return [], []

    ref_array = np.array(reference_times)
    indices = []
    weights = []

    for sample_time in sample_times:
        # Find bracketing indices
        idx_after = np.searchsorted(ref_array, sample_time)

        if idx_after == 0:
            # Before first reference point - clamp to first
            indices.append((0, 0))
            weights.append((1.0, 0.0))
        elif idx_after >= len(ref_array):
            # After last reference point - clamp to last
            idx = len(ref_array) - 1
            indices.append((idx, idx))
            weights.append((1.0, 0.0))
        else:
            # Interpolate between idx_after-1 and idx_after
            idx0 = idx_after - 1
            idx1 = idx_after

            t0 = ref_array[idx0]
            t1 = ref_array[idx1]

            # Linear interpolation weight
            if t1 - t0 > 0:
                w1 = (sample_time - t0) / (t1 - t0)
                w0 = 1.0 - w1
            else:
                # Zero interval - equal weights
                w0, w1 = 0.5, 0.5

            indices.append((idx0, idx1))
            weights.append((w0, w1))

    return indices, weights


# =============================================================================
# Jitter Computation
# =============================================================================


def compute_jitter_stats(sample_times: List[float], reference_times: List[float], indices: List[int]) -> Dict[str, float]:
    """Compute jitter statistics.

    Args:
        sample_times: Original sample times
        reference_times: Reference timebase
        indices: Mapping indices

    Returns:
        Dict with max_jitter_s and p95_jitter_s

    Example:
        >>> stats = compute_jitter_stats(samples, reference, indices)
    """
    if not sample_times or not indices:
        return {"max_jitter_s": 0.0, "p95_jitter_s": 0.0}

    ref_array = np.array(reference_times)
    sample_array = np.array(sample_times)

    # Compute jitter for each sample
    jitters = []
    for i, idx in enumerate(indices):
        jitter = abs(sample_array[i] - ref_array[idx])
        jitters.append(jitter)

    jitter_array = np.array(jitters)

    return {"max_jitter_s": float(np.max(jitter_array)), "p95_jitter_s": float(np.percentile(jitter_array, 95))}


# =============================================================================
# Jitter Budget Enforcement
# =============================================================================


def enforce_jitter_budget(max_jitter: float, p95_jitter: float, budget: float) -> None:
    """Enforce jitter budget before NWB assembly.

    Validates that observed jitter is within acceptable limits. This is
    typically called before writing final NWB files to ensure data quality.

    Args:
        max_jitter: Maximum jitter observed (seconds)
        p95_jitter: 95th percentile jitter (seconds)
        budget: Configured jitter budget threshold (seconds)

    Raises:
        JitterExceedsBudgetError: If max or p95 jitter exceeds budget

    Example:
        >>> enforce_jitter_budget(
        ...     max_jitter=0.005,
        ...     p95_jitter=0.003,
        ...     budget=0.010
        ... )  # Passes
    """
    if max_jitter > budget:
        raise JitterExceedsBudgetError(max_jitter, p95_jitter, budget)
    if p95_jitter > budget:
        raise JitterExceedsBudgetError(max_jitter, p95_jitter, budget)


# =============================================================================
# High-Level Alignment (Primitives)
# =============================================================================


def align_samples(
    sample_times: List[float],
    reference_times: List[float],
    config: TimebaseConfigProtocol,
    enforce_budget: bool = False,
) -> Dict[str, Any]:
    """Align samples to reference timebase using configured strategy.

    Orchestrates mapping, jitter computation, and budget enforcement.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        config: Timebase configuration
        enforce_budget: Enforce jitter budget

    Returns:
        Dict with indices, jitter_stats, and mapping

    Raises:
        JitterExceedsBudgetError: Jitter exceeds budget
        SyncError: Alignment failed
    """
    if config.method == "nearest":
        indices = map_nearest(sample_times, reference_times)
        jitter_stats = compute_jitter_stats(sample_times, reference_times, indices)
        result = {"indices": indices, "jitter_stats": jitter_stats, "mapping": "nearest"}

    elif config.method == "linear":
        indices, weights = map_linear(sample_times, reference_times)
        # Jitter stats for linear interpolation are complex, using nearest for budget check
        # This is a simplification - ideally we'd compute residual from interpolation
        nearest_indices = map_nearest(sample_times, reference_times)
        jitter_stats = compute_jitter_stats(sample_times, reference_times, nearest_indices)
        result = {"indices": indices, "weights": weights, "jitter_stats": jitter_stats, "mapping": "linear"}

    else:
        raise SyncError(f"Unknown mapping strategy: {config.method}")

    if enforce_budget:
        enforce_jitter_budget(
            max_jitter=jitter_stats["max_jitter_s"],
            p95_jitter=jitter_stats["p95_jitter_s"],
            budget=config.tolerance_s,
        )

    return result


# =============================================================================
# Stream Synchronization
# =============================================================================


def sync_stream_to_timebase(
    sample_times: List[float],
    reference_times: List[float],
    config: TimebaseConfigProtocol,
    enforce_budget: bool = False,
) -> Dict[str, Any]:
    """Align data stream timestamps to a reference timebase, correcting for clock drift.

    This function performs temporal alignment between two clocks:
    1. Your device's clock (sample_times) - may have drift/offset
    2. A reference clock (reference_times) - the ground truth timebase

    It returns timestamps on the reference timebase that correspond to your samples,
    effectively "translating" from your device's clock to the reference clock.

    **Important: The returned "aligned_times" are NOT simply reference_times!**
    They are your sample_times mapped/interpolated onto the reference timebase to
    correct for clock drift and offset.

    **What this function does:**
    - Finds correspondence between sample_times and reference_times
    - Computes timestamps on the reference clock for each of your samples
    - Accounts for clock drift, offset, and timing jitter
    - Returns quality metrics to validate synchronization accuracy

    **When to use:**
    - Synchronizing video frames to camera TTL pulses (video clock → TTL clock)
    - Aligning pose estimation to video timestamps (pose clock → video clock)
    - Synchronizing facemap outputs to behavioral recordings
    - Any case where two clocks need temporal alignment

    Algorithm:
    ----------
    For "nearest" mapping:
        1. For each sample_time, find nearest reference_time
        2. Return that reference_time as the aligned timestamp
        3. Effectively snaps each sample to closest reference point

    For "linear" mapping:
        1. For each sample_time, find bracketing reference_times
        2. Interpolate between them based on sample_time position
        3. Returns interpolated timestamps (smoother alignment)

    Args:
        sample_times: Original timestamps from your data stream's internal clock.
            Examples:
            - Video frame timestamps from camera's timer
            - Pose estimation frame times from DLC/SLEAP processing clock
            - Facemap processing timestamps
            These may have clock drift relative to reference_times.

        reference_times: Ground-truth timestamps from a master clock.
            Typically from hardware TTL pulses (e.g., camera trigger signals).
            These define the canonical timebase all data should align to.

        config: Configuration object specifying:
            - mapping: "nearest" (snap to closest) or "linear" (interpolate)
            - jitter_budget: Maximum acceptable alignment error (seconds)
            - Other alignment parameters

        enforce_budget: If True, raise error when jitter exceeds configured budget.
            Use this when synchronization quality is critical.

    Returns:
        Dictionary containing:
            - indices: Reference indices used for each sample (int for nearest,
                      tuple for linear interpolation)
            - aligned_times: Timestamps on reference timebase corresponding to your
                           samples. Use these instead of raw sample_times in NWB.
            - jitter_stats: Quality metrics (mean, std, max jitter in seconds)
            - mapping: Strategy used ("nearest" or "linear")

    Raises:
        JitterExceedsBudgetError: If enforce_budget=True and alignment quality poor
        SyncError: If alignment fails due to incompatible data

    Example - Video to Hardware TTL:
        >>> from w2t_bkin import ttl, sync
        >>>
        >>> # Step 1: Get hardware clock (ground truth)
        >>> ttl_pulses = ttl.get_ttl_pulses(rawdata_dir, {"ttl_camera": "TTLs/*.xa_7_0*.txt"})
        >>> reference_times = ttl_pulses["ttl_camera"]  # [0.0, 0.0334, 0.0667, ...]
        >>>
        >>> # Step 2: Get video's internal clock (may have drift)
        >>> video_metadata = load_video_metadata("video.mp4")
        >>> sample_times = video_metadata["frame_timestamps"]  # [0.0, 0.033, 0.066, ...]
        >>>
        >>> # Step 3: Align video clock → hardware clock
        >>> config = sync.TimebaseConfig(mapping="nearest", jitter_budget=0.001)
        >>> result = sync.sync_stream_to_timebase(
        ...     sample_times=sample_times,      # Video's clock (may drift)
        ...     reference_times=reference_times, # Hardware clock (ground truth)
        ...     config=config,
        ...     enforce_budget=True
        ... )
        >>>
        >>> # Step 4: Use synchronized times (on reference clock, NOT raw sample times)
        >>> aligned_timestamps = result["aligned_times"]
        >>> # aligned_timestamps are now on TTL clock: [0.0, 0.0334, 0.0667, ...]
        >>> # They correct for any drift between video and hardware clocks
        >>>
        >>> print(f"Mean jitter: {result['jitter_stats']['mean']*1000:.2f} ms")
        >>> # Jitter measures alignment quality (difference between clocks)

    Example - Understanding Clock Drift:
        >>> # Your camera reports these timestamps (internal clock):
        >>> sample_times = [0.0, 1.0, 2.0, 3.0]  # Appears to be exactly 1 Hz
        >>>
        >>> # But hardware TTL shows actual times (ground truth):
        >>> reference_times = [0.0, 1.01, 2.02, 3.03]  # Camera is 1% slow!
        >>>
        >>> result = sync_stream_to_timebase(sample_times, reference_times, config)
        >>> result["aligned_times"]  # [0.0, 1.01, 2.02, 3.03]
        >>> # ^ These are your frames placed on the TRUE timeline
        >>> # NOT just reference_times copied - they're YOUR samples mapped correctly
    """
    # Perform alignment using generic strategy
    result = align_samples(sample_times, reference_times, config, enforce_budget)

    indices = result["indices"]

    # Extract aligned timestamps from reference
    # IMPORTANT: These are NOT just copying reference_times!
    # They are reference_times at the indices/interpolation points
    # that correspond to each sample_time
    if config.method == "nearest":
        # Snap each sample to nearest reference point
        aligned_times = [reference_times[idx] for idx in indices]
    elif config.method == "linear":
        # Interpolate between reference points
        aligned_times = []
        weights = result.get("weights", [])
        for (idx0, idx1), (w0, w1) in zip(indices, weights):
            # Weighted average: places sample between two reference points
            t_aligned = w0 * reference_times[idx0] + w1 * reference_times[idx1]
            aligned_times.append(t_aligned)
    else:
        # Fallback: use nearest (should be caught by align_samples)
        aligned_times = [reference_times[indices[0]] for _ in sample_times]

    return {
        "indices": indices,
        "aligned_times": aligned_times,
        "jitter_stats": result["jitter_stats"],
        "mapping": result["mapping"],
    }


def align_pose_frames_to_reference(
    pose_data: List[Dict],
    reference_times: List[float],
    mapping: str = "nearest",
) -> Dict[int, float]:
    """Map pose frame indices to reference timebase timestamps.

    This function is a specialized alignment utility for pose estimation data.
    Unlike sync_stream_to_timebase, it works with **frame indices** rather than
    timestamps, because DLC/SLEAP output typically only includes frame numbers.

    **Use Case:**
    After running DeepLabCut or SLEAP, you have pose data with frame indices
    (0, 1, 2, ...) but no absolute timestamps. This function uses synchronized
    video frame timestamps (from hardware TTL alignment) to assign timestamps
    to each pose frame.

    **Key Difference from sync_stream_to_timebase:**
    - sync_stream_to_timebase: Aligns one set of timestamps to another
    - align_pose_frames_to_reference: Maps frame INDEX → timestamp lookup

    The result is the same: timestamps on the reference timebase for your data.

    **Workflow:**
    1. Sync video frames to hardware TTL (using sync_stream_to_timebase)
       - Input: video sample_times, TTL reference_times
       - Output: video_aligned_times (video frames on TTL clock)
    2. Use video_aligned_times as reference_times here
    3. Map pose frame_index → corresponding video_aligned_time
    4. Result: pose timestamps on the same TTL clock as video

    Algorithm:
    ----------
    For each pose frame:
        1. Extract frame_index (which video frame this pose belongs to)
        2. Lookup reference_times[frame_index] (direct or interpolated)
        3. Return as pose timestamp

    Args:
        pose_data: Harmonized pose data from DLC/SLEAP. List of dicts with:
            - frame_index: Frame number in video (0-based integer)
            - keypoints: Pose keypoint data (can be empty if tracking failed)

        reference_times: Timestamps for video frames, already synchronized to
            hardware TTL clock. Obtained from:
            1. Hardware TTL pulses for camera triggers
            2. Video sample_times aligned to TTL (via sync_stream_to_timebase)

            Index i in reference_times = timestamp for video frame i.

        mapping: Lookup strategy:
            - "nearest": Direct lookup: frame_index → reference_times[frame_index]
            - "linear": Extrapolate if frame_index exceeds reference_times length

    Returns:
        Dictionary mapping frame_index → absolute_timestamp (seconds).
        These timestamps are on the same reference clock as reference_times.
        Example: {0: 10.5, 1: 10.533, 2: 10.566, ...}

    Raises:
        SyncError: If mapping strategy invalid or data malformed

    Example - Complete Synchronization Chain:
        >>> from w2t_bkin import ttl, sync, pose
        >>>
        >>> # Step 1: Get hardware clock (TTL pulses)
        >>> ttl_pulses = ttl.get_ttl_pulses(rawdata_dir, {"ttl_camera": "TTLs/*.xa_7_0*.txt"})
        >>> ttl_times = ttl_pulses["ttl_camera"]  # Ground truth: [0.0, 0.0334, 0.0667, ...]
        >>>
        >>> # Step 2: Align video to hardware clock
        >>> video_metadata = load_video_metadata("video.mp4")
        >>> video_sample_times = video_metadata["frame_timestamps"]  # Video's clock
        >>> video_result = sync.sync_stream_to_timebase(
        ...     sample_times=video_sample_times,  # Video clock
        ...     reference_times=ttl_times,         # Hardware clock
        ...     config=config
        ... )
        >>> video_aligned_times = video_result["aligned_times"]
        >>> # video_aligned_times: video frames on TTL clock [0.0, 0.0334, 0.0667, ...]
        >>>
        >>> # Step 3: Load pose data (only has frame indices, no timestamps)
        >>> pose_data, metadata = pose.import_dlc_pose("pose.h5")
        >>> # pose_data: [{'frame_index': 0, 'keypoints': ...}, {'frame_index': 1, ...}, ...]
        >>>
        >>> # Step 4: Map pose frame indices → video timestamps (already on TTL clock)
        >>> frame_timestamps = align_pose_frames_to_reference(
        ...     pose_data=pose_data,
        ...     reference_times=video_aligned_times,  # Video frames on TTL clock
        ...     mapping="nearest"
        ... )
        >>> # frame_timestamps: {0: 0.0, 1: 0.0334, 2: 0.0667, ...}
        >>> # These are pose frames on TTL clock (via video)
        >>>
        >>> # Step 5: Add timestamps to pose data
        >>> for frame in pose_data:
        ...     frame['timestamp'] = frame_timestamps[frame['frame_index']]
        >>>
        >>> # Result: Pose, video, and TTL are all on the same timebase!
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

        # Map frame index to reference timestamp
        if mapping == "nearest":
            if frame_idx < len(reference_times):
                # Direct lookup: frame N → reference_times[N]
                timestamp = reference_times[frame_idx]
            else:
                # Out of bounds - use last timestamp
                logger.warning(f"Frame {frame_idx} out of bounds, using last timestamp")
                timestamp = reference_times[-1]

        elif mapping == "linear":
            if frame_idx < len(reference_times):
                timestamp = reference_times[frame_idx]
            else:
                # Linear extrapolation beyond last frame
                if len(reference_times) >= 2:
                    dt = reference_times[-1] - reference_times[-2]
                    timestamp = reference_times[-1] + dt * (frame_idx - len(reference_times) + 1)
                else:
                    timestamp = reference_times[-1]

        frame_timestamps[frame_idx] = timestamp

    logger.debug(f"Aligned {len(frame_timestamps)} pose frames to reference timebase")
    return frame_timestamps


# =============================================================================
# Robust Synchronization Recovery
# =============================================================================


def fit_robust_linear_model(
    source_times: np.ndarray,
    target_times: np.ndarray,
    outlier_threshold_s: float = 0.1,
    min_valid_points: int = 2,
) -> Tuple[float, float, np.ndarray]:
    """Fit a robust linear model to align two timebases, handling missing data/outliers.

    Recovers the linear relationship: target = slope * source + intercept
    even when the correspondence is noisy or has missing points (e.g., dropped TTL pulses).

    Algorithm:
    1. Perform initial nearest-neighbor mapping
    2. Compute residuals (target - source)
    3. Identify outliers based on median residual and threshold
    4. Fit linear regression to valid pairs only

    Args:
        source_times: Timestamps from source clock (e.g., Bpod trial starts)
        target_times: Timestamps from target clock (e.g., recorded TTL pulses)
        outlier_threshold_s: Maximum residual deviation to consider valid (seconds)
        min_valid_points: Minimum number of valid points required for fit

    Returns:
        Tuple containing:
        - slope: Clock drift factor (approx 1.0)
        - intercept: Clock offset (seconds)
        - valid_mask: Boolean mask of source_times that were successfully matched

    Raises:
        SyncError: If too few valid points found to fit model
    """
    # 1. Naive Nearest Neighbor Mapping
    indices = map_nearest(source_times.tolist(), target_times.tolist())
    matched_target = target_times[indices]

    # 2. Calculate Residuals
    # diff = Target - Source
    # For correct matches: diff ≈ Intercept (constant offset)
    # For incorrect matches: diff ≈ Intercept ± Interval (outlier)
    diffs = matched_target - source_times
    median_diff = np.median(diffs)

    # 3. Filter Outliers
    valid_mask = np.abs(diffs - median_diff) < outlier_threshold_s
    n_valid = np.sum(valid_mask)

    if n_valid < min_valid_points:
        raise SyncError(f"Too few valid points ({n_valid}) to fit robust model (min={min_valid_points})")

    # 4. Robust Linear Regression on Valid Pairs
    valid_source = source_times[valid_mask]
    valid_target = matched_target[valid_mask]

    res = stats.linregress(valid_source, valid_target)

    return res.slope, res.intercept, valid_mask
