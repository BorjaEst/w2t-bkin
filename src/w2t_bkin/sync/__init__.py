"""Temporal synchronization utilities.

Provides timebase providers, sample alignment, TTL pulse loading, and
modality-specific synchronization for video, pose, facemap, and behavioral data.

Example:
    >>> from w2t_bkin.sync import create_timebase_provider, align_samples
    >>> provider = create_timebase_provider(source="nominal_rate", rate=30.0)
    >>> timestamps = provider.get_timestamps(n_samples=100)
"""

# Exceptions
from ..exceptions import JitterExceedsBudgetError, SyncError

# Behavioral synchronization
from .behavior import align_bpod_trials_to_ttl, get_sync_time_from_bpod_trial

# FaceMap synchronization
from .facemap import sync_facemap_to_timebase

# Mapping strategies
from .mapping import align_samples, compute_jitter_stats, enforce_jitter_budget, map_linear, map_nearest

# Module-local models
from .models import AlignmentStats

# Pose synchronization
from .pose import sync_pose_to_timebase

# Alignment statistics
from .stats import compute_alignment, create_alignment_stats, load_alignment_manifest, write_alignment_stats

# Timebase providers
from .timebase import NeuropixelsProvider, NominalRateProvider, TimebaseProvider, TTLProvider, create_timebase_provider, create_timebase_provider_from_config

# TTL utilities (generic)
from .ttl import get_ttl_pulses, load_ttl_file

# Video synchronization
from .video import sync_video_frames_to_timebase

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
