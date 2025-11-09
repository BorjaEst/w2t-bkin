"""Domain models for the W2T BKin pipeline.

Provides shared typed models used across pipeline stages including VideoMetadata,
TimestampSeries, PoseTable, MetricsTable, Manifest, TrialsTable, and QCSummary.
All models use Pydantic for validation and serialization.

Requirements: MR-1, MR-2, M-NFR-1, M-NFR-2
Design: domain/design.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Custom Exceptions (Design §6)
# ============================================================================


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    pass


class MissingInputError(PipelineError):
    """Required input file is missing."""

    pass


class TimestampMismatchError(PipelineError):
    """Timestamp data is non-monotonic or length mismatched."""

    pass


class DataIntegrityWarning(Warning):
    """Data contains gaps or NaNs beyond expected thresholds."""

    pass


# ============================================================================
# Domain Models
# ============================================================================


class VideoMetadata(BaseModel):
    """Video file metadata model (MR-1, Design §3.1).
    
    Represents metadata for a single camera video file in the session.
    All models are frozen (immutable) for safety.
    """

    model_config = {"frozen": True}

    camera_id: int = Field(..., ge=0, description="Camera identifier, must be non-negative")
    path: Path = Field(..., description="Absolute path to video file")
    codec: str = Field(..., description="Video codec (e.g., h264, h265)")
    fps: float = Field(..., gt=0, description="Frames per second, must be positive")
    duration: float = Field(..., ge=0, description="Duration in seconds, must be non-negative")
    resolution: tuple[int, int] = Field(..., description="Video resolution (width, height)")


class TimestampSeries(BaseModel):
    """Frame timestamp series with monotonicity validation (MR-2, Design §3.2).
    
    Represents per-frame timestamps for a camera with strict validation:
    - Monotonically increasing timestamps
    - Equal length arrays
    - Non-negative timestamps
    """

    model_config = {"frozen": True}

    frame_indices: list[int] = Field(..., description="Frame indices")
    timestamps: list[float] = Field(..., description="Timestamps in seconds")

    @field_validator("timestamps")
    @classmethod
    def validate_non_negative(cls, v: list[float]) -> list[float]:
        """Validate all timestamps are non-negative (MR-2)."""
        if any(t < 0 for t in v):
            raise ValueError("All timestamps must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_monotonic_and_length(self) -> TimestampSeries:
        """Validate monotonicity and equal lengths (MR-2)."""
        if len(self.frame_indices) != len(self.timestamps):
            raise ValueError(f"frame_indices and timestamps must have equal length: {len(self.frame_indices)} != {len(self.timestamps)}")

        # Check strict monotonic increase
        for i in range(1, len(self.timestamps)):
            if self.timestamps[i] <= self.timestamps[i - 1]:
                raise ValueError(f"Timestamps must be strictly monotonic increasing. " f"Found {self.timestamps[i]} <= {self.timestamps[i-1]} at index {i}")

        return self


class PoseTable(BaseModel):
    """Pose keypoint data with validation (MR-1, MR-2, Design §3.3).
    
    Represents harmonized pose estimation outputs with:
    - Equal length arrays
    - Confidence values in [0, 1]
    - Optional metadata sidecar
    """

    model_config = {"frozen": True}

    time: list[float] = Field(..., description="Timestamps in seconds")
    keypoint: list[str] = Field(..., description="Keypoint names")
    x_px: list[float] = Field(..., description="X coordinates in pixels")
    y_px: list[float] = Field(..., description="Y coordinates in pixels")
    confidence: list[float] = Field(..., description="Confidence scores [0, 1]")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata sidecar (skeleton, model hash)")

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: list[float]) -> list[float]:
        """Validate confidence values are in [0, 1] (MR-2)."""
        for conf in v:
            if conf < 0 or conf > 1:
                raise ValueError(f"Confidence values must be in [0, 1], got {conf}")
        return v

    @model_validator(mode="after")
    def validate_equal_lengths(self) -> PoseTable:
        """Validate all arrays have equal length (MR-2)."""
        lengths = {
            "time": len(self.time),
            "keypoint": len(self.keypoint),
            "x_px": len(self.x_px),
            "y_px": len(self.y_px),
            "confidence": len(self.confidence),
        }

        if len(set(lengths.values())) > 1:
            raise ValueError(f"All arrays must have equal length. Got: {lengths}")

        return self


class MetricsTable(BaseModel):
    """Facemap metrics table with dynamic columns (MR-1, Design §3.4).
    
    Supports wide table format with variable metric columns.
    Missing samples are preserved as NaN.
    """

    model_config = {"frozen": True, "extra": "allow"}

    time: list[float] = Field(..., description="Timestamps in seconds")

    @model_validator(mode="after")
    def validate_equal_lengths(self) -> MetricsTable:
        """Validate all metric arrays have equal length (MR-2)."""
        time_length = len(self.time)

        for field_name, field_value in self.model_dump().items():
            if field_name != "time" and isinstance(field_value, list):
                if len(field_value) != time_length:
                    raise ValueError(f"All metric arrays must have length {time_length}. " f"Field '{field_name}' has length {len(field_value)}")

        return self


class TrialsTable(BaseModel):
    """Behavioral trials table (MR-1, Design §3.5).
    
    Represents normalized trial data with validation:
    - Unique trial IDs
    - Positive trial durations (stop_time > start_time)
    """

    model_config = {"frozen": True}

    trial_id: list[int] = Field(..., description="Unique trial identifiers")
    start_time: list[float] = Field(..., description="Trial start times in seconds")
    stop_time: list[float] = Field(..., description="Trial stop times in seconds")
    phase_first: list[str] = Field(..., description="First phase in trial")
    phase_last: list[str] = Field(..., description="Last phase in trial")
    declared_duration: list[float] = Field(..., description="Declared trial duration")
    observed_span: list[float] = Field(..., description="Observed trial span")
    duration_delta: list[float] = Field(..., description="Difference between declared and observed")
    qc_flags: list[str] = Field(..., description="QC flags for each trial")

    @model_validator(mode="after")
    def validate_trials(self) -> TrialsTable:
        """Validate trial constraints (MR-2)."""
        # Validate unique trial IDs
        if len(set(self.trial_id)) != len(self.trial_id):
            raise ValueError("Trial IDs must be unique")

        # Validate positive durations
        for i, (start, stop) in enumerate(zip(self.start_time, self.stop_time)):
            if stop <= start:
                raise ValueError(f"Trial {self.trial_id[i]}: stop_time ({stop}) must be > start_time ({start})")

        return self


class Manifest(BaseModel):
    """Session manifest model (MR-1, Design §3.1).
    
    Contains all session metadata and references to data files.
    All paths must be absolute (validated).
    """

    model_config = {"frozen": True}

    session_id: str = Field(..., description="Unique session identifier")
    videos: list[VideoMetadata] = Field(..., description="Video metadata for all cameras")
    sync: list[dict[str, Any]] = Field(default_factory=list, description="Sync log references")
    events: list[dict[str, Any]] = Field(default_factory=list, description="Event log references")
    pose: list[dict[str, Any]] = Field(default_factory=list, description="Pose file references")
    facemap: list[dict[str, Any]] = Field(default_factory=list, description="Facemap file references")
    config_snapshot: dict[str, Any] = Field(default_factory=dict, description="Configuration snapshot")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Provenance information")

    @model_validator(mode="after")
    def validate_absolute_paths(self) -> Manifest:
        """Validate all paths are absolute (MR-2, Design §3.1)."""
        # Check video paths
        for video in self.videos:
            if not video.path.is_absolute():
                raise ValueError(f"Video path must be absolute: {video.path}")

        # Check sync paths
        for sync_entry in self.sync:
            if "path" in sync_entry:
                path = sync_entry["path"]
                if isinstance(path, Path) and not path.is_absolute():
                    raise ValueError(f"Sync path must be absolute: {path}")

        # Check other resource paths (events, pose, facemap)
        for resource_list in [self.events, self.pose, self.facemap]:
            for entry in resource_list:
                if "path" in entry:
                    path = entry["path"]
                    if isinstance(path, Path) and not path.is_absolute():
                        raise ValueError(f"Resource path must be absolute: {path}")

        return self


class QCSummary(BaseModel):
    """QC summary data (MR-1, Design §3.6).
    
    Contains quality control metrics and summaries from all pipeline stages.
    All sections are optional to support partial QC reports.
    """

    model_config = {"frozen": True}

    sync: dict[str, Any] = Field(default_factory=dict, description="Sync QC metrics")
    pose: dict[str, Any] = Field(default_factory=dict, description="Pose QC metrics")
    facemap: dict[str, Any] = Field(default_factory=dict, description="Facemap QC metrics")
    events: dict[str, Any] = Field(default_factory=dict, description="Events QC metrics")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Provenance information")


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Exceptions
    "PipelineError",
    "MissingInputError",
    "TimestampMismatchError",
    "DataIntegrityWarning",
    # Models
    "VideoMetadata",
    "TimestampSeries",
    "PoseTable",
    "MetricsTable",
    "TrialsTable",
    "Manifest",
    "QCSummary",
]
