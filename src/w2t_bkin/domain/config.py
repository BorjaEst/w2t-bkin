"""Configuration domain models for W2T-BKIN pipeline (Phase 0).

This module defines Pydantic models for pipeline configuration loaded from config.toml.
All models are immutable (frozen=True) and use strict validation (extra="forbid") to
catch typos and schema drift early.

Model Hierarchy:
---------------
- Config (top-level)
  ├── ProjectConfig
  ├── PathsConfig
  ├── TimebaseConfig
  ├── AcquisitionConfig
  ├── VerificationConfig
  ├── BpodConfig
  ├── VideoConfig (contains TranscodeConfig)
  ├── NWBConfig
  ├── QCConfig
  ├── LoggingConfig
  ├── LabelsConfig (contains DLCConfig, SLEAPConfig)
  └── FacemapConfig

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Hashable**: Supports deterministic provenance tracking

Requirements:
-------------
- FR-10: Configuration-driven via TOML
- NFR-10: Type safety via Pydantic
- NFR-11: Environment overrides via pydantic-settings

Acceptance Criteria:
-------------------
- A18: Supports deterministic hashing

Usage:
------
>>> from w2t_bkin.config import load_config
>>> config = load_config("config.toml")
>>> print(config.timebase.source)  # "nominal_rate" | "ttl" | "neuropixels"

See Also:
---------
- w2t_bkin.config: Loading and validation logic
- spec/spec-config-toml.md: Schema specification
"""

from typing import List, Optional

from pydantic import BaseModel


class ProjectConfig(BaseModel):
    """Project identification."""

    model_config = {"frozen": True, "extra": "forbid"}

    name: str


class PathsConfig(BaseModel):
    """Path configuration for data directories."""

    model_config = {"frozen": True, "extra": "forbid"}

    raw_root: str
    intermediate_root: str
    output_root: str
    metadata_file: str
    models_root: str


class TimebaseConfig(BaseModel):
    """Timebase configuration for session reference clock.

    Determines the reference timebase for aligning derived data (pose, facemap, etc).
    ImageSeries timing is always rate-based and independent of this setting.

    Attributes:
        source: "nominal_rate" | "ttl" | "neuropixels"
        mapping: "nearest" | "linear"
        jitter_budget_s: Maximum acceptable jitter before aborting
        offset_s: Time offset applied to timebase
        ttl_id: TTL channel to use (required when source="ttl")
        neuropixels_stream: Neuropixels stream name (required when source="neuropixels")

    Requirements:
        - FR-TB-1..6: Timebase strategy
        - FR-17: Provenance of timebase choice
    """

    model_config = {"frozen": True, "extra": "forbid"}

    source: str  # Enum validated at load time: nominal_rate|ttl|neuropixels
    mapping: str  # Enum validated at load time: nearest|linear
    jitter_budget_s: float
    offset_s: float
    ttl_id: Optional[str] = None
    neuropixels_stream: Optional[str] = None


class AcquisitionConfig(BaseModel):
    """Acquisition policies."""

    model_config = {"frozen": True, "extra": "forbid"}

    concat_strategy: str  # Enum validated at load time


class VerificationConfig(BaseModel):
    """Verification policies for frame/TTL matching.

    Attributes:
        mismatch_tolerance_frames: Maximum acceptable frame/TTL count difference
        warn_on_mismatch: Emit warning when mismatch ≤ tolerance

    Requirements:
        - FR-2, FR-3: Frame/TTL verification
        - FR-16: Tolerance and warning behavior
    """

    model_config = {"frozen": True, "extra": "forbid"}

    mismatch_tolerance_frames: int
    warn_on_mismatch: bool


class BpodConfig(BaseModel):
    """Bpod parsing configuration.

    Requirements:
        - FR-11: Optional Bpod parsing
    """

    model_config = {"frozen": True, "extra": "forbid"}

    parse: bool


class TranscodeConfig(BaseModel):
    """Video transcoding configuration.

    Attributes:
        enabled: Enable transcoding to mezzanine format
        codec: ffmpeg codec (e.g., "libx264")
        crf: Constant Rate Factor (quality, 0-51, lower=better)
        preset: ffmpeg preset (e.g., "medium")
        keyint: Keyframe interval (frames)

    Requirements:
        - FR-4: Optional transcoding
    """

    model_config = {"frozen": True, "extra": "forbid"}

    enabled: bool
    codec: str
    crf: int
    preset: str
    keyint: int


class VideoConfig(BaseModel):
    """Video processing configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    transcode: TranscodeConfig


class NWBConfig(BaseModel):
    """NWB export configuration.

    Attributes:
        link_external_video: Use external_file links (vs embedding)
        lab: Laboratory name
        institution: Institution name
        file_name_template: Template for NWB filename
        session_description_template: Template for session description

    Requirements:
        - FR-7: NWB export with ImageSeries
        - NFR-6: Rate-based timing
    """

    model_config = {"frozen": True, "extra": "forbid"}

    link_external_video: bool
    lab: str
    institution: str
    file_name_template: str
    session_description_template: str


class QCConfig(BaseModel):
    """QC report configuration.

    Requirements:
        - FR-8: QC HTML report generation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    generate_report: bool
    out_template: str
    include_verification: bool


class LoggingConfig(BaseModel):
    """Logging configuration.

    Requirements:
        - NFR-3: Structured logging
    """

    model_config = {"frozen": True, "extra": "forbid"}

    level: str
    structured: bool


class DLCConfig(BaseModel):
    """DeepLabCut configuration.

    Requirements:
        - FR-5: Optional pose estimation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str


class SLEAPConfig(BaseModel):
    """SLEAP configuration.

    Requirements:
        - FR-5: Optional pose estimation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str


class LabelsConfig(BaseModel):
    """Pose estimation labels configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    dlc: DLCConfig
    sleap: SLEAPConfig


class FacemapConfig(BaseModel):
    """Facemap configuration.

    Requirements:
        - FR-6: Optional Facemap processing
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    ROIs: List[str]


class Config(BaseModel):
    """Top-level pipeline configuration (strict schema).

    Loaded from config.toml and validated against this schema.
    All nested models use frozen=True and extra="forbid" for immutability
    and strict validation.

    Requirements:
        - FR-10: Configuration-driven pipeline
        - NFR-10: Type safety
        - NFR-11: Provenance via deterministic hashing

    Example:
        >>> from w2t_bkin.config import load_config
        >>> config = load_config("config.toml")
        >>> config.timebase.source
        'nominal_rate'
    """

    model_config = {"frozen": True, "extra": "forbid"}

    project: ProjectConfig
    paths: PathsConfig
    timebase: TimebaseConfig
    acquisition: AcquisitionConfig
    verification: VerificationConfig
    bpod: BpodConfig
    video: VideoConfig
    nwb: NWBConfig
    qc: QCConfig
    logging: LoggingConfig
    labels: LabelsConfig
    facemap: FacemapConfig
