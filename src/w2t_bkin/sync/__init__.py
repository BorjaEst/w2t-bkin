"""Synchronization module for W2T-BKIN pipeline (Phase 2 - Temporal Alignment).

This package provides temporal synchronization utilities organized by functional area:

- **timebase**: Timebase providers (nominal rate, TTL, Neuropixels)
- **mapping**: Sample alignment strategies and jitter computation
- **ttl**: Generic TTL pulse loading utilities
- **behavior**: Behavioral data synchronization (Bpod-TTL alignment)
- **video**: Video frame synchronization helpers
- **facemap**: FaceMap output synchronization helpers
- **pose**: Pose estimation synchronization helpers
- **stats**: Alignment statistics and persistence

Public API:
-----------
All public functions are re-exported at the package level for convenience:

    from w2t_bkin.sync import (
        create_timebase_provider,
        align_samples,
        get_ttl_pulses,
        align_bpod_trials_to_ttl,
    )

See individual modules for detailed documentation.
"""

# Behavioral synchronization
from .behavior import align_bpod_trials_to_ttl, get_sync_time_from_bpod_trial

# Exceptions
from .exceptions import JitterBudgetExceeded, SyncError

# FaceMap synchronization
from .facemap import sync_facemap_to_timebase

# Mapping strategies
from .mapping import align_samples, compute_jitter_stats, enforce_jitter_budget, map_linear, map_nearest

# Pose synchronization
from .pose import sync_pose_to_timebase

# Alignment statistics
from .stats import compute_alignment, create_alignment_stats, load_alignment_manifest, write_alignment_stats

# Timebase providers
from .timebase import NeuropixelsProvider, NominalRateProvider, TimebaseProvider, TTLProvider, create_timebase_provider

# TTL utilities (generic)
from .ttl import get_ttl_pulses, load_ttl_file

# Video synchronization
from .video import sync_video_frames_to_timebase

__all__ = [
    # Exceptions
    "SyncError",
    "JitterBudgetExceeded",
    # Timebase
    "TimebaseProvider",
    "NominalRateProvider",
    "TTLProvider",
    "NeuropixelsProvider",
    "create_timebase_provider",
    # Mapping
    "map_nearest",
    "map_linear",
    "compute_jitter_stats",
    "enforce_jitter_budget",
    "align_samples",
    # TTL
    "get_ttl_pulses",
    "load_ttl_file",
    # Behavior
    "get_sync_time_from_bpod_trial",
    "align_bpod_trials_to_ttl",
    # Video
    "sync_video_frames_to_timebase",
    # FaceMap
    "sync_facemap_to_timebase",
    # Pose
    "sync_pose_to_timebase",
    # Stats
    "create_alignment_stats",
    "write_alignment_stats",
    "load_alignment_manifest",
    "compute_alignment",
]
