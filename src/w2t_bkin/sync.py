"""Sync module for W2T-BKIN pipeline (Phase 2).

Timebase provider abstraction, mapping strategies, jitter computation,
and alignment stats persistence.

Requirements: FR-TB-1..6, FR-17
Acceptance: A8, A9, A10, A11, A12, A17, A19, A20
"""

import logging
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .domain import AlignmentStats, Config, Manifest, TimebaseConfig
from .utils import write_json

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class SyncError(Exception):
    """Error during synchronization/alignment."""
    pass


class JitterBudgetExceeded(SyncError):
    """Jitter exceeds configured budget."""
    pass


# =============================================================================
# Timebase Provider Abstraction
# =============================================================================


class TimebaseProvider(ABC):
    """Abstract base class for timebase providers."""

    def __init__(self, source: str, offset_s: float = 0.0):
        self.source = source
        self.offset_s = offset_s

    @abstractmethod
    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from this timebase.
        
        Args:
            n_samples: Number of samples (for synthetic timebases)
            
        Returns:
            List of timestamps in seconds
        """
        pass


class NominalRateProvider(TimebaseProvider):
    """Nominal rate timebase provider (synthetic timestamps)."""

    def __init__(self, rate: float, offset_s: float = 0.0):
        super().__init__(source="nominal_rate", offset_s=offset_s)
        self.rate = rate

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Generate synthetic timestamps from nominal rate.
        
        Args:
            n_samples: Number of samples to generate
            
        Returns:
            List of timestamps starting at offset_s
        """
        if n_samples is None:
            raise ValueError("n_samples required for NominalRateProvider")
        
        timestamps = [self.offset_s + i / self.rate for i in range(n_samples)]
        return timestamps


class TTLProvider(TimebaseProvider):
    """TTL-based timebase provider (load from files)."""

    def __init__(self, ttl_id: str, ttl_files: List[str], offset_s: float = 0.0):
        super().__init__(source="ttl", offset_s=offset_s)
        self.ttl_id = ttl_id
        self.ttl_files = ttl_files
        self._timestamps = None
        self._load_timestamps()

    def _load_timestamps(self):
        """Load timestamps from TTL files."""
        timestamps = []
        
        for ttl_file in self.ttl_files:
            path = Path(ttl_file)
            if not path.exists():
                raise SyncError(f"TTL file not found: {ttl_file}")
            
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            timestamps.append(float(line))
            except Exception as e:
                raise SyncError(f"Failed to parse TTL file {ttl_file}: {e}")
        
        # Apply offset
        self._timestamps = [t + self.offset_s for t in sorted(timestamps)]

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from TTL files.
        
        Args:
            n_samples: Ignored for TTL provider
            
        Returns:
            List of timestamps from TTL files
        """
        return self._timestamps


class NeuropixelsProvider(TimebaseProvider):
    """Neuropixels timebase provider (stub for Phase 2)."""

    def __init__(self, stream: str, offset_s: float = 0.0):
        super().__init__(source="neuropixels", offset_s=offset_s)
        self.stream = stream

    def get_timestamps(self, n_samples: Optional[int] = None) -> List[float]:
        """Get timestamps from Neuropixels stream (stub).
        
        Args:
            n_samples: Number of samples
            
        Returns:
            Stub timestamps (30 kHz sampling)
        """
        if n_samples is None:
            n_samples = 1000
        
        # Stub: 30 kHz sampling
        rate = 30000.0
        timestamps = [self.offset_s + i / rate for i in range(n_samples)]
        return timestamps


# =============================================================================
# Factory Function
# =============================================================================


def create_timebase_provider(
    config: Config,
    manifest: Optional[Manifest] = None
) -> TimebaseProvider:
    """Create timebase provider from config.
    
    Args:
        config: Pipeline configuration
        manifest: Session manifest (required for TTL provider)
        
    Returns:
        TimebaseProvider instance
        
    Raises:
        SyncError: If invalid source or missing required data
    """
    source = config.timebase.source
    offset_s = config.timebase.offset_s
    
    if source == "nominal_rate":
        # Default to 30 Hz for cameras
        rate = 30.0
        return NominalRateProvider(rate=rate, offset_s=offset_s)
    
    elif source == "ttl":
        if manifest is None:
            raise SyncError("Manifest required for TTL timebase provider")
        
        ttl_id = config.timebase.ttl_id
        if not ttl_id:
            raise SyncError("timebase.ttl_id required when source='ttl'")
        
        # Find TTL files in manifest
        ttl_files = None
        for ttl in manifest.ttls:
            if ttl.ttl_id == ttl_id:
                ttl_files = ttl.files
                break
        
        if not ttl_files:
            raise SyncError(f"TTL {ttl_id} not found in manifest")
        
        return TTLProvider(ttl_id=ttl_id, ttl_files=ttl_files, offset_s=offset_s)
    
    elif source == "neuropixels":
        stream = config.timebase.neuropixels_stream
        if not stream:
            raise SyncError("timebase.neuropixels_stream required when source='neuropixels'")
        
        return NeuropixelsProvider(stream=stream, offset_s=offset_s)
    
    else:
        raise SyncError(f"Invalid timebase source: {source}")


# =============================================================================
# Mapping Strategies
# =============================================================================


def map_nearest(
    sample_times: List[float],
    reference_times: List[float]
) -> List[int]:
    """Map sample times to nearest reference times.
    
    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        
    Returns:
        List of indices into reference_times
        
    Raises:
        SyncError: If reference is empty or not monotonic
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


def map_linear(
    sample_times: List[float],
    reference_times: List[float]
) -> Tuple[List[Tuple[int, int]], List[Tuple[float, float]]]:
    """Map sample times using linear interpolation.
    
    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        
    Returns:
        Tuple of (indices, weights) where:
        - indices: List of (idx0, idx1) tuples for interpolation
        - weights: List of (w0, w1) tuples for interpolation weights
        
    Raises:
        SyncError: If reference is empty or not monotonic
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
            # Before first reference point
            indices.append((0, 0))
            weights.append((1.0, 0.0))
        elif idx_after >= len(ref_array):
            # After last reference point
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
                w0, w1 = 0.5, 0.5
            
            indices.append((idx0, idx1))
            weights.append((w0, w1))
    
    return indices, weights


# =============================================================================
# Jitter Computation
# =============================================================================


def compute_jitter_stats(
    sample_times: List[float],
    reference_times: List[float],
    indices: List[int]
) -> Dict[str, float]:
    """Compute jitter statistics for alignment.
    
    Args:
        sample_times: Original sample times
        reference_times: Reference timebase
        indices: Mapping indices from map_nearest()
        
    Returns:
        Dictionary with max_jitter_s and p95_jitter_s
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
    
    return {
        "max_jitter_s": float(np.max(jitter_array)),
        "p95_jitter_s": float(np.percentile(jitter_array, 95))
    }


# =============================================================================
# Jitter Budget Enforcement
# =============================================================================


def enforce_jitter_budget(
    max_jitter: float,
    p95_jitter: float,
    budget: float
) -> None:
    """Enforce jitter budget before NWB assembly.
    
    Args:
        max_jitter: Maximum jitter observed
        p95_jitter: 95th percentile jitter
        budget: Configured jitter budget
        
    Raises:
        JitterBudgetExceeded: If jitter exceeds budget
    """
    if max_jitter > budget or p95_jitter > budget:
        raise JitterBudgetExceeded(
            f"Jitter exceeds budget: max={max_jitter:.6f}s, "
            f"p95={p95_jitter:.6f}s, budget={budget:.6f}s"
        )


# =============================================================================
# Alignment Workflow
# =============================================================================


def align_samples(
    sample_times: List[float],
    reference_times: List[float],
    config: TimebaseConfig,
    enforce_budget: bool = False
) -> Dict:
    """Align samples to reference timebase.
    
    Args:
        sample_times: Times to align
        reference_times: Reference timebase
        config: Timebase configuration
        enforce_budget: Whether to enforce jitter budget
        
    Returns:
        Dictionary with indices, jitter_stats, and mapping strategy
        
    Raises:
        JitterBudgetExceeded: If enforce_budget=True and budget exceeded
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
        enforce_jitter_budget(
            jitter_stats["max_jitter_s"],
            jitter_stats["p95_jitter_s"],
            config.jitter_budget_s
        )
    
    return {
        "indices": indices,
        "jitter_stats": jitter_stats,
        "mapping": mapping
    }


# =============================================================================
# AlignmentStats Creation and Persistence
# =============================================================================


def create_alignment_stats(
    timebase_source: str,
    mapping: str,
    offset_s: float,
    max_jitter_s: float,
    p95_jitter_s: float,
    aligned_samples: int
) -> AlignmentStats:
    """Create alignment stats instance.
    
    Args:
        timebase_source: Source of timebase (nominal_rate, ttl, neuropixels)
        mapping: Mapping strategy used (nearest, linear)
        offset_s: Offset applied to timebase
        max_jitter_s: Maximum jitter observed
        p95_jitter_s: 95th percentile jitter
        aligned_samples: Number of samples aligned
        
    Returns:
        AlignmentStats instance
    """
    return AlignmentStats(
        timebase_source=timebase_source,
        mapping=mapping,
        offset_s=offset_s,
        max_jitter_s=max_jitter_s,
        p95_jitter_s=p95_jitter_s,
        aligned_samples=aligned_samples
    )


def write_alignment_stats(stats: AlignmentStats, output_path: Path) -> None:
    """Write alignment stats to JSON sidecar.
    
    Args:
        stats: AlignmentStats instance
        output_path: Output file path
    """
    data = stats.model_dump()
    data["generated_at"] = datetime.utcnow().isoformat()
    write_json(data, output_path)
