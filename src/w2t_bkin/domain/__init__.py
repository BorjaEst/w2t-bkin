"""Domain models and data contracts for W2T BKin pipeline.

Pure data structures representing the domain entities and contracts between
pipeline stages. As a Layer 0 foundation module, this package must not import
any other project packages.

Requirements: All FR and NFR
Design: design.md §3 (Data Contracts), §21.1 (Dependency Tree)
API: api.md §3.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "VideoMetadata",
    "Manifest",
    "TimestampSeries",
    "SyncSummary",
    "PoseSample",
    "PoseTable",
    "FacemapMetrics",
    "Trial",
    "Event",
    "NWBAssemblyOptions",
    "QCReportSummary",
    "DriftThresholdExceeded",
    "TimestampMismatchError",
    "MissingInputError",
]


# ============================================================================
# Custom Exceptions (Design §6)
# ============================================================================


class DriftThresholdExceeded(Exception):
    """Raised when inter-camera drift exceeds configured tolerance."""

    pass


class TimestampMismatchError(ValueError):
    """Raised when timestamps are non-monotonic or frame count mismatch."""

    pass


class MissingInputError(FileNotFoundError):
    """Raised when required input files are missing."""

    pass


# ============================================================================
# Video & Manifest Contracts (FR-1, FR-7, Design §3.1)
# ============================================================================


@dataclass(frozen=True)
class VideoMetadata:
    """Metadata for a single camera video.

    Requirements: FR-1 (Ingest five camera videos)
    Design: §3.1 (Manifest JSON)
    """

    camera_id: int
    path: Path
    codec: str
    fps: float
    duration: float  # seconds
    resolution: tuple[int, int]  # (width, height)

    def __post_init__(self) -> None:
        """Validate video metadata constraints."""
        if self.camera_id < 0:
            raise ValueError(f"camera_id must be non-negative, got {self.camera_id}")
        if self.fps <= 0:
            raise ValueError(f"fps must be positive, got {self.fps}")
        if self.duration < 0:
            raise ValueError(f"duration must be non-negative, got {self.duration}")
        if len(self.resolution) != 2 or any(r <= 0 for r in self.resolution):
            raise ValueError(f"resolution must be (width>0, height>0), got {self.resolution}")


@dataclass(frozen=True)
class Manifest:
    """Session manifest describing all available inputs.

    Requirements: FR-1 (Ingest assets), NFR-1 (Reproducibility)
    Design: §3.1 (Manifest JSON)
    """

    session_id: str
    videos: list[VideoMetadata]
    sync: list[dict[str, Any]]  # Flexible sync source descriptors
    events: list[dict[str, Any]] = field(default_factory=list)  # Optional
    pose: list[dict[str, Any]] = field(default_factory=list)  # Optional
    facemap: list[dict[str, Any]] = field(default_factory=list)  # Optional
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate manifest constraints."""
        if not self.session_id:
            raise ValueError("session_id cannot be empty")
        if not self.videos:
            raise ValueError("videos list cannot be empty")
        # Ensure at least one sync source
        if not self.sync:
            raise ValueError("sync list cannot be empty")


# ============================================================================
# Synchronization Contracts (FR-2, FR-3, Design §3.2)
# ============================================================================


@dataclass(frozen=True)
class TimestampSeries:
    """Per-camera frame timestamps.

    Requirements: FR-2 (Compute per-frame timestamps)
    Design: §3.2 (Timestamp CSV)
    """

    frame_index: list[int]
    timestamp_sec: list[float]

    def __post_init__(self) -> None:
        """Validate timestamp series constraints."""
        if len(self.frame_index) != len(self.timestamp_sec):
            raise ValueError("frame_index and timestamp_sec must have equal length")
        if not self.frame_index:
            raise ValueError("TimestampSeries cannot be empty")
        # Verify monotonic increase
        for i in range(1, len(self.timestamp_sec)):
            if self.timestamp_sec[i] <= self.timestamp_sec[i - 1]:
                raise ValueError(f"Timestamps must be strictly monotonic increasing at index {i}: " f"{self.timestamp_sec[i-1]} >= {self.timestamp_sec[i]}")

    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        return self.timestamp_sec[-1] - self.timestamp_sec[0] if self.timestamp_sec else 0.0

    @property
    def n_frames(self) -> int:
        """Number of frames."""
        return len(self.frame_index)


@dataclass(frozen=True)
class SyncSummary:
    """Summary statistics for synchronization quality.

    Requirements: FR-3 (Detect drops/duplicates/drift)
    Design: §3.6 (QC Summary JSON - sync section)
    """

    per_camera_stats: dict[str, dict[str, Any]]  # camera_id -> stats
    drift_stats: dict[str, float]  # max, mean, std drift in ms
    drop_counts: dict[str, int]  # camera_id -> dropped frames
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate sync summary constraints."""
        if not self.per_camera_stats:
            raise ValueError("per_camera_stats cannot be empty")


# ============================================================================
# Pose Contracts (FR-5, Design §3.3)
# ============================================================================


@dataclass(frozen=True)
class PoseSample:
    """Single pose keypoint observation.

    Requirements: FR-5 (Import/harmonize pose with confidence)
    Design: §3.3 (Pose Harmonized Table)
    """

    time: float  # seconds in session timebase
    keypoint: str
    x_px: float
    y_px: float
    confidence: float  # [0, 1]

    def __post_init__(self) -> None:
        """Validate pose sample constraints."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if not self.keypoint:
            raise ValueError("keypoint name cannot be empty")


@dataclass(frozen=True)
class PoseTable:
    """Harmonized pose table with metadata.

    Requirements: FR-5 (Harmonize pose outputs to canonical schema)
    Design: §3.3 (Pose Harmonized Table)
    """

    records: list[PoseSample]
    skeleton_meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate pose table constraints."""
        if not self.records:
            raise ValueError("PoseTable records cannot be empty")

    @property
    def n_samples(self) -> int:
        """Number of pose samples."""
        return len(self.records)

    @property
    def keypoints(self) -> set[str]:
        """Unique keypoint names in table."""
        return {sample.keypoint for sample in self.records}


# ============================================================================
# Facemap Contracts (FR-6, Design §3.4)
# ============================================================================


@dataclass(frozen=True)
class FacemapMetrics:
    """Facial metrics time series.

    Requirements: FR-6 (Import/compute facial metrics)
    Design: §3.4 (Facemap Metrics)
    """

    time: list[float]  # seconds in session timebase
    metric_columns: dict[str, list[float]]  # metric_name -> series

    def __post_init__(self) -> None:
        """Validate facemap metrics constraints."""
        if not self.time:
            raise ValueError("time series cannot be empty")
        # Verify all metric columns have same length as time
        time_len = len(self.time)
        for metric_name, values in self.metric_columns.items():
            if len(values) != time_len:
                raise ValueError(f"Metric '{metric_name}' length {len(values)} != time length {time_len}")

    @property
    def n_samples(self) -> int:
        """Number of time samples."""
        return len(self.time)

    @property
    def metrics(self) -> list[str]:
        """List of metric names."""
        return list(self.metric_columns.keys())


# ============================================================================
# Events & Trials Contracts (FR-11, Design §3.5)
# ============================================================================


@dataclass(frozen=True)
class Event:
    """Behavioral event.

    Requirements: FR-11 (Import events as BehavioralEvents)
    Design: §3.5 (Events table)
    """

    time: float  # seconds in session timebase
    kind: str  # event type
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate event constraints."""
        if not self.kind:
            raise ValueError("kind cannot be empty")
        if self.time < 0:
            raise ValueError(f"time must be non-negative, got {self.time}")


@dataclass(frozen=True)
class Trial:
    """Trial interval with QC metadata.

    Requirements: FR-11 (Import events as Trials TimeIntervals)
    Design: §3.5 (Trials Table)
    """

    trial_id: int
    start_time: float  # seconds
    stop_time: float  # seconds
    phase_first: str = ""
    phase_last: str = ""
    declared_duration: float = 0.0
    observed_span: float = 0.0
    duration_delta: float = 0.0
    qc_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate trial constraints."""
        if self.start_time < 0:
            raise ValueError(f"start_time must be non-negative, got {self.start_time}")
        if self.stop_time <= self.start_time:
            raise ValueError(f"stop_time ({self.stop_time}) must be > start_time ({self.start_time})")

    @property
    def duration(self) -> float:
        """Trial duration in seconds."""
        return self.stop_time - self.start_time


# ============================================================================
# NWB Assembly Contracts (FR-7, Design §2)
# ============================================================================


@dataclass(frozen=True)
class NWBAssemblyOptions:
    """Options for NWB file assembly.

    Requirements: FR-7 (Export NWB), FR-10 (Configuration-driven)
    Design: §3.7 (NWB Assembly)
    """

    link_external_video: bool = True
    file_name: str = ""
    session_description: str = ""
    lab: str = ""
    institution: str = ""

    def __post_init__(self) -> None:
        """Validate NWB assembly options."""
        # file_name can be empty (will be auto-generated)
        pass


# ============================================================================
# QC Report Contracts (FR-8, Design §3.6)
# ============================================================================


@dataclass(frozen=True)
class QCReportSummary:
    """Quality control report summary.

    Requirements: FR-8 (Generate QC HTML report)
    Design: §3.6 (QC Summary JSON)
    """

    sync_overview: dict[str, Any] = field(default_factory=dict)
    pose_overview: dict[str, Any] = field(default_factory=dict)
    facemap_overview: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def has_pose(self) -> bool:
        """Check if pose data is present."""
        return bool(self.pose_overview)

    @property
    def has_facemap(self) -> bool:
        """Check if facemap data is present."""
        return bool(self.facemap_overview)
