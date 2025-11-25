"""Configuration models for W2T-BKIN pipeline.

Pydantic models for config.toml validation with strict schema enforcement.
These models replace the old domain.config module.

All models use extra="forbid" to prevent typos and enforce strict schemas.
"""

from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Project Configuration
# =============================================================================


class ProjectConfig(BaseModel, extra="forbid"):
    """Project-level configuration."""

    name: str = Field(..., description="Project name")


# =============================================================================
# Paths Configuration
# =============================================================================


class PathsConfig(BaseModel, extra="forbid"):
    """File system paths configuration."""

    raw_root: str = Field(..., description="Raw data root directory")
    intermediate_root: str = Field(..., description="Intermediate processing outputs")
    output_root: str = Field(..., description="Output data root directory")
    metadata_file: str = Field(default="session.toml", description="Session metadata filename")
    models_root: str = Field(default="models", description="Pose estimation models directory")


# =============================================================================
# Timebase Configuration
# =============================================================================


class TimebaseConfig(BaseModel, extra="forbid"):
    """Reference timebase configuration for aligning derived data.

    Note: ImageSeries remain rate-based; this timebase is for pose/behavior alignment.
    """

    source: Literal["nominal_rate", "ttl", "neuropixels"] = Field(..., description="Timebase source")
    mapping: Literal["nearest", "linear"] = Field(..., description="Mapping strategy")
    jitter_budget_s: float = Field(..., ge=0.0, description="Max allowed jitter in seconds")
    offset_s: float = Field(default=0.0, description="Global offset before mapping")
    ttl_id: Optional[str] = Field(None, description="TTL ID (required when source='ttl')")
    neuropixels_stream: Optional[str] = Field(None, description="Neuropixels stream (required when source='neuropixels')")


# =============================================================================
# Acquisition Configuration
# =============================================================================


class AcquisitionConfig(BaseModel, extra="forbid"):
    """Acquisition policies (session-agnostic)."""

    concat_strategy: Literal["ffconcat", "streamlist"] = Field(default="ffconcat", description="Video concatenation strategy")


# =============================================================================
# Verification Configuration
# =============================================================================


class VerificationConfig(BaseModel, extra="forbid"):
    """Hardware sync verification policy."""

    mismatch_tolerance_frames: int = Field(default=0, ge=0, description="Abort if frame_count - ttl_pulse_count > tolerance")
    warn_on_mismatch: bool = Field(default=False, description="Warn instead of abort if within tolerance")


# =============================================================================
# Bpod Configuration
# =============================================================================


class BpodConfig(BaseModel, extra="forbid"):
    """Bpod behavioral system configuration."""

    parse: bool = Field(default=True, description="Parse Bpod .mat files if present")


# =============================================================================
# Video/Transcode Configuration
# =============================================================================


class TranscodeConfig(BaseModel, extra="forbid"):
    """Video transcoding configuration."""

    enabled: bool = Field(default=True, description="Enable transcoding")
    codec: str = Field(default="h264", description="FFmpeg codec name")
    crf: int = Field(default=20, ge=0, le=51, description="Quality factor (0-51)")
    preset: str = Field(default="fast", description="FFmpeg preset")
    keyint: int = Field(default=15, ge=1, description="GOP length")


class VideoConfig(BaseModel, extra="forbid"):
    """Global video defaults."""

    transcode: TranscodeConfig = Field(default_factory=TranscodeConfig)


# =============================================================================
# NWB Configuration
# =============================================================================


class NWBConfig(BaseModel, extra="forbid"):
    """NWB export configuration."""

    link_external_video: bool = Field(default=True, description="Link videos externally")
    lab: str = Field(default="Lab Name", description="Lab name")
    institution: str = Field(default="Institution Name", description="Institution name")
    file_name_template: str = Field(default="{session.id}.nwb", description="NWB filename template")
    session_description_template: str = Field(
        default="Session {session.id} on {session.date}",
        description="Session description template",
    )


# =============================================================================
# QC Configuration
# =============================================================================


class QCConfig(BaseModel, extra="forbid"):
    """QC report configuration."""

    generate_report: bool = Field(default=True, description="Generate QC report")
    out_template: str = Field(default="qc/{session.id}", description="Output path template")
    include_verification: bool = Field(default=True, description="Include frame/TTL verification in report")


# =============================================================================
# Logging Configuration
# =============================================================================


class LoggingConfig(BaseModel, extra="forbid"):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", description="Logging level")
    structured: bool = Field(default=False, description="Use structured (JSON) logging")


# =============================================================================
# Pose Labels Configuration (DLC/SLEAP)
# =============================================================================


class DLCConfig(BaseModel, extra="forbid"):
    """DeepLabCut inference configuration."""

    run_inference: bool = Field(default=False, description="Run DLC inference")
    model: str = Field(default="model.pb", description="Path to DLC model file")
    gputouse: Optional[int] = Field(None, description="GPU index (-1 for CPU, None for auto)")


class SLEAPConfig(BaseModel, extra="forbid"):
    """SLEAP inference configuration."""

    run_inference: bool = Field(default=False, description="Run SLEAP inference")
    model: str = Field(default="sleap.h5", description="Path to SLEAP model file")


class LabelsConfig(BaseModel, extra="forbid"):
    """Pose labels inference configuration."""

    dlc: DLCConfig = Field(default_factory=DLCConfig)
    sleap: SLEAPConfig = Field(default_factory=SLEAPConfig)


# =============================================================================
# Facemap Configuration
# =============================================================================


class FacemapConfig(BaseModel, extra="forbid"):
    """Facemap facial tracking configuration."""

    run_inference: bool = Field(default=False, description="Run Facemap inference")
    ROIs: List[str] = Field(default_factory=lambda: ["face", "left_eye", "right_eye"], description="ROIs to process")


# =============================================================================
# Main Config Model
# =============================================================================


class Config(BaseModel, extra="forbid"):
    """Main pipeline configuration model.

    Loaded from config.toml with strict schema validation.
    """

    project: ProjectConfig
    paths: PathsConfig
    timebase: TimebaseConfig
    acquisition: AcquisitionConfig = Field(default_factory=AcquisitionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    bpod: BpodConfig = Field(default_factory=BpodConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    nwb: NWBConfig = Field(default_factory=NWBConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    labels: LabelsConfig = Field(default_factory=LabelsConfig)
    facemap: FacemapConfig = Field(default_factory=FacemapConfig)

    @field_validator("timebase")
    @classmethod
    def validate_timebase_conditionals(cls, v: TimebaseConfig) -> TimebaseConfig:
        """Validate conditional requirements for timebase."""
        if v.source == "ttl" and v.ttl_id is None:
            raise ValueError("timebase.ttl_id is required when source='ttl'")
        if v.source == "neuropixels" and v.neuropixels_stream is None:
            raise ValueError("timebase.neuropixels_stream is required when source='neuropixels'")
        return v
