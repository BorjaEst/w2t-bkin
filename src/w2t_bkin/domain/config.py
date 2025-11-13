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

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Project identification."""

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="Project name for identification and reporting")


class PathsConfig(BaseModel):
    """Path configuration for data directories."""

    model_config = {"frozen": True, "extra": "forbid"}

    raw_root: str = Field(..., description="Root directory for raw input data")
    intermediate_root: str = Field(..., description="Root directory for intermediate processing outputs")
    output_root: str = Field(..., description="Root directory for final pipeline outputs")
    metadata_file: str = Field(..., description="Path to metadata file (e.g., session.toml)")
    models_root: str = Field(..., description="Root directory for ML models (DLC, SLEAP, etc.)")


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

    source: Literal["nominal_rate", "ttl", "neuropixels"] = Field(..., description="Timebase source: 'nominal_rate' | 'ttl' | 'neuropixels'")
    mapping: Literal["nearest", "linear"] = Field(..., description="Alignment mapping strategy: 'nearest' | 'linear'")
    jitter_budget_s: float = Field(..., description="Maximum acceptable jitter in seconds before aborting", gt=0)
    offset_s: float = Field(default=0.0, description="Time offset applied to timebase in seconds")
    ttl_id: Optional[str] = Field(default=None, description="TTL channel ID when source='ttl'")
    neuropixels_stream: Optional[str] = Field(default=None, description="Neuropixels stream name when source='neuropixels'")


class AcquisitionConfig(BaseModel):
    """Acquisition policies."""

    model_config = {"frozen": True, "extra": "forbid"}

    concat_strategy: str = Field(..., description="Video concatenation strategy (validated at load time)")


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

    mismatch_tolerance_frames: int = Field(..., description="Maximum acceptable frame/TTL mismatch", ge=0)
    warn_on_mismatch: bool = Field(..., description="Emit warning when mismatch is within tolerance")


class BpodConfig(BaseModel):
    """Bpod parsing configuration.

    Requirements:
        - FR-11: Optional Bpod parsing
    """

    model_config = {"frozen": True, "extra": "forbid"}

    parse: bool = Field(..., description="Enable parsing of Bpod behavioral data files")


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

    enabled: bool = Field(..., description="Enable video transcoding to mezzanine format")
    codec: str = Field(..., description="ffmpeg video codec (e.g., 'libx264', 'libx265')")
    crf: int = Field(..., description="Constant Rate Factor (0-51, lower=better quality)", ge=0, le=51)
    preset: str = Field(..., description="ffmpeg encoding preset (e.g., 'ultrafast', 'medium', 'veryslow')")
    keyint: int = Field(..., description="Keyframe interval in frames", gt=0)


class VideoConfig(BaseModel):
    """Video processing configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    transcode: TranscodeConfig = Field(..., description="Video transcoding settings")


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

    link_external_video: bool = Field(..., description="Use external_file links instead of embedding videos")
    lab: str = Field(..., description="Laboratory name for NWB metadata")
    institution: str = Field(..., description="Institution name for NWB metadata")
    file_name_template: str = Field(..., description="Template for NWB output filename (supports placeholders)")
    session_description_template: str = Field(..., description="Template for NWB session description")


class QCConfig(BaseModel):
    """QC report configuration.

    Requirements:
        - FR-8: QC HTML report generation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    generate_report: bool = Field(..., description="Enable QC HTML report generation")
    out_template: str = Field(..., description="Template for QC report output path")
    include_verification: bool = Field(..., description="Include frame/TTL verification results in report")


class LoggingConfig(BaseModel):
    """Logging configuration.

    Requirements:
        - NFR-3: Structured logging
    """

    model_config = {"frozen": True, "extra": "forbid"}

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(..., description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    structured: bool = Field(..., description="Enable structured JSON logging")


class DLCConfig(BaseModel):
    """DeepLabCut configuration.

    Requirements:
        - FR-5: Optional pose estimation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool = Field(..., description="Enable DeepLabCut pose inference")
    model: str = Field(..., description="Path to DeepLabCut model")


class SLEAPConfig(BaseModel):
    """SLEAP configuration.

    Requirements:
        - FR-5: Optional pose estimation
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool = Field(..., description="Enable SLEAP pose inference")
    model: str = Field(..., description="Path to SLEAP model")


class LabelsConfig(BaseModel):
    """Pose estimation labels configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    dlc: DLCConfig = Field(..., description="DeepLabCut configuration")
    sleap: SLEAPConfig = Field(..., description="SLEAP configuration")


class FacemapConfig(BaseModel):
    """Facemap configuration.

    Requirements:
        - FR-6: Optional Facemap processing
    """

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool = Field(..., description="Enable Facemap motion energy computation")
    ROIs: List[str] = Field(..., description="List of ROI names to analyze")


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

    project: ProjectConfig = Field(..., description="Project identification configuration")
    paths: PathsConfig = Field(..., description="Data directory paths configuration")
    timebase: TimebaseConfig = Field(..., description="Timebase alignment configuration")
    acquisition: AcquisitionConfig = Field(..., description="Acquisition policies")
    verification: VerificationConfig = Field(..., description="Frame/TTL verification policies")
    bpod: BpodConfig = Field(..., description="Bpod behavioral data configuration")
    video: VideoConfig = Field(..., description="Video processing configuration")
    nwb: NWBConfig = Field(..., description="NWB export configuration")
    qc: QCConfig = Field(..., description="Quality control report configuration")
    logging: LoggingConfig = Field(..., description="Logging configuration")
    labels: LabelsConfig = Field(..., description="Pose estimation configuration")
    facemap: FacemapConfig = Field(..., description="Facemap motion energy configuration")
