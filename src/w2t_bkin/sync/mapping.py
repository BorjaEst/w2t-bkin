"""Sample alignment strategies and jitter computation.

Provides nearest neighbor and linear interpolation mapping with jitter
statistics and budget enforcement.

Example:
    >>> result = align_samples(sample_times, reference_times, config)
"""

from typing import Dict, List, Tuple
import warnings

import numpy as np

from ..exceptions import JitterExceedsBudgetError, SyncError
from .protocols import TimebaseConfigProtocol

__all__ = [
    "map_nearest",
    "map_linear",
    "compute_jitter_stats",
    "enforce_jitter_budget",
    "align_samples",
]


# =============================================================================
# Mapping Strategies
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
        >>> enforce_jitter_budget(
        ...     max_jitter=0.015,
        ...     p95_jitter=0.008,
        ...     budget=0.010
        ... )  # Raises JitterExceedsBudgetError
    """
    if max_jitter > budget or p95_jitter > budget:
        raise JitterExceedsBudgetError(f"Jitter exceeds budget: max={max_jitter:.6f}s, " f"p95={p95_jitter:.6f}s, budget={budget:.6f}s")


# =============================================================================
# High-Level Alignment
# =============================================================================


def align_samples(sample_times: List[float], reference_times: List[float], config: TimebaseConfigProtocol, enforce_budget: bool = False) -> Dict:
    """Align samples to reference timebase using configured strategy.

    High-level function that performs alignment according to config.mapping
    strategy (nearest or linear) and optionally enforces jitter budget.

    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        config: Timebase configuration with mapping strategy and jitter budget
        enforce_budget: Whether to enforce jitter budget (raises on exceed)

    Returns:
        Dictionary with:
        - indices: Alignment indices (list of int or list of tuple for linear)
        - jitter_stats: Dict with max_jitter_s and p95_jitter_s
        - mapping: Strategy used ("nearest" or "linear")

    Raises:
        JitterExceedsBudgetError: If enforce_budget=True and budget exceeded
        SyncError: If invalid mapping strategy

    Example:
        >>> config = TimebaseConfig(
        ...     source="nominal_rate",
        ...     mapping="nearest",
        ...     jitter_budget_s=0.010,
        ...     offset_s=0.0
        ... )
        >>> result = align_samples(
        ...     sample_times=[0.1, 0.5, 1.2],
        ...     reference_times=[0.0, 0.5, 1.0, 1.5],
        ...     config=config,
        ...     enforce_budget=True
        ... )
        >>> indices = result["indices"]
        >>> jitter = result["jitter_stats"]["max_jitter_s"]
    """
    mapping = config.mapping

    if mapping == "nearest":
        indices = map_nearest(sample_times, reference_times)
        jitter_stats = compute_jitter_stats(sample_times, reference_times, indices)
    elif mapping == "linear":
        indices, weights = map_linear(sample_times, reference_times)
        # For jitter computation with linear, use nearest for simplicity
        nearest_indices = [idx[0] for idx in indices]
        jitter_stats = compute_jitter_stats(sample_times, reference_times, nearest_indices)
    else:
        raise SyncError(f"Invalid mapping strategy: {mapping}")

    if enforce_budget:
        enforce_jitter_budget(jitter_stats["max_jitter_s"], jitter_stats["p95_jitter_s"], config.jitter_budget_s)

    return {"indices": indices, "jitter_stats": jitter_stats, "mapping": mapping}
