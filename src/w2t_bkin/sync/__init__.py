"""Temporal synchronization utilities.

Provides timebase providers, sample alignment, and stream synchronization
for video, pose, facemap, and behavioral data.

Note: TTL pulse loading has been moved to the ttl module.

Example:
    >>> from w2t_bkin.sync import create_timebase_provider, align_samples
    >>> provider = create_timebase_provider(source="nominal_rate", rate=30.0)
    >>> timestamps = provider.get_timestamps(n_samples=100)
"""

# Exceptions
from w2t_bkin.exceptions import JitterExceedsBudgetError, SyncError

# Core synchronization (formerly primitives, streams, protocols)
from w2t_bkin.sync.core import (
    TimebaseConfigProtocol,
    align_pose_frames_to_reference,
    align_samples,
    compute_jitter_stats,
    enforce_jitter_budget,
    fit_robust_linear_model,
    map_linear,
    map_nearest,
    sync_stream_to_timebase,
)

# Alignment statistics (formerly models, stats)
from w2t_bkin.sync.stats import AlignmentStats, compute_alignment, create_alignment_stats, load_alignment_manifest, write_alignment_stats

# Timebase providers
from w2t_bkin.sync.timebase import NeuropixelsProvider, NominalRateProvider, TimebaseProvider, TTLProvider, create_timebase_provider, create_timebase_provider_from_config

# TTL synchronization
from w2t_bkin.sync.ttl import align_bpod_trials_to_ttl, get_sync_time_from_bpod_trial

__all__ = [
    # Exceptions
    "SyncError",
    "JitterExceedsBudgetError",
    # Models
    "AlignmentStats",
    # Timebase
    "TimebaseProvider",
    "NominalRateProvider",
    "TTLProvider",
    "NeuropixelsProvider",
    "create_timebase_provider",
    "create_timebase_provider_from_config",
    # Mapping (Primitives)
    "map_nearest",
    "map_linear",
    "compute_jitter_stats",
    "enforce_jitter_budget",
    "align_samples",
    # TTL
    "align_bpod_trials_to_ttl",
    "get_sync_time_from_bpod_trial",
    # Streams
    "sync_stream_to_timebase",
    "align_pose_frames_to_reference",
    "fit_robust_linear_model",
    # Stats
    "create_alignment_stats",
    "write_alignment_stats",
    "load_alignment_manifest",
    "compute_alignment",
    # Protocols
    "TimebaseConfigProtocol",
]
