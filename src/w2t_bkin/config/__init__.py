"""Configuration module for w2t-bkin.

Provides strongly-typed configuration loading and validation (TOML + env overrides)
for all pipeline stages.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("tomli is required for Python < 3.11. Install with: pip install tomli")

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


# Configuration Models (Pydantic BaseModel with frozen=True for immutability)


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    model_config = {"frozen": True}

    name: str = Field(..., description="Project name")
    n_cameras: int = Field(..., ge=1, description="Number of cameras")


class PathsConfig(BaseModel):
    """Path configuration for data directories."""

    model_config = {"frozen": True}

    raw_root: Path = Field(..., description="Raw data root directory")
    intermediate_root: Path = Field(..., description="Intermediate data root directory")
    output_root: Path = Field(..., description="Output data root directory")
    models_root: Path = Field(..., description="Models root directory")


class SessionConfig(BaseModel):
    """Session metadata configuration."""

    model_config = {"frozen": True}

    id: str = Field(..., description="Session ID")
    subject_id: str = Field(..., description="Subject ID")
    date: str = Field(..., description="Session date")
    experimenter: str = Field(..., description="Experimenter name")
    description: str = Field(..., description="Session description")
    sex: str = Field(..., description="Subject sex")
    age: str = Field(..., description="Subject age")
    genotype: str = Field(..., description="Subject genotype")


class VideoTranscodeConfig(BaseModel):
    """Video transcoding configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable transcoding")
    codec: str = Field(default="h264", description="Video codec")
    crf: int = Field(default=23, ge=0, le=51, description="Constant rate factor")
    preset: str = Field(default="medium", description="Encoding preset")
    keyint: int = Field(default=30, ge=1, description="Keyframe interval")


class VideoConfig(BaseModel):
    """Video configuration."""

    model_config = {"frozen": True}

    pattern: str = Field(default="cam*.mp4", description="Video file pattern")
    fps: float = Field(default=30.0, gt=0, description="Frames per second")
    transcode: VideoTranscodeConfig = Field(default_factory=VideoTranscodeConfig, description="Transcode settings")


class TTLChannelConfig(BaseModel):
    """TTL channel configuration for synchronization."""

    model_config = {"frozen": True}

    path: Path = Field(..., description="Path to TTL data file")
    name: str = Field(..., description="Channel name")
    polarity: str = Field(..., description="Edge polarity (rising/falling)")


class SyncConfig(BaseModel):
    """Synchronization configuration."""

    model_config = {"frozen": True}

    tolerance_ms: float = Field(default=2.0, gt=0, description="Sync tolerance in ms")
    drop_frame_max_gap_ms: float = Field(default=100.0, gt=0, description="Max gap for dropped frames in ms")
    primary_clock: str = Field(default="cam0", description="Primary clock source")
    ttl_channels: list[TTLChannelConfig] = Field(default_factory=list, description="TTL channel configurations")


class DLCConfig(BaseModel):
    """DeepLabCut configuration."""

    model_config = {"frozen": True}

    model: Path = Field(..., description="Path to DLC model")
    run_inference: bool = Field(default=False, description="Run DLC inference")


class SLEAPConfig(BaseModel):
    """SLEAP configuration."""

    model_config = {"frozen": True}

    model: Path = Field(..., description="Path to SLEAP model")
    run_inference: bool = Field(default=False, description="Run SLEAP inference")


class LabelsConfig(BaseModel):
    """Pose estimation labels configuration."""

    model_config = {"frozen": True}

    dlc: DLCConfig = Field(..., description="DeepLabCut configuration")
    sleap: SLEAPConfig = Field(..., description="SLEAP configuration")


class FacemapConfig(BaseModel):
    """Facemap configuration."""

    model_config = {"frozen": True}

    run: bool = Field(default=False, description="Run Facemap")
    roi: list[int] = Field(default_factory=list, description="Region of interest [x, y, w, h]")


class NWBConfig(BaseModel):
    """NWB output configuration."""

    model_config = {"frozen": True}

    link_external_video: bool = Field(default=True, description="Link external video files")
    file_name: str = Field(default="session.nwb", description="Output NWB file name")
    session_description: str = Field(default="Multi-camera behavioral session", description="Session description")
    lab: str = Field(..., description="Lab name")
    institution: str = Field(..., description="Institution name")


class QCConfig(BaseModel):
    """Quality control configuration."""

    model_config = {"frozen": True}

    generate_report: bool = Field(default=True, description="Generate QC report")
    out: Path = Field(..., description="QC output directory")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = {"frozen": True}

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", description="Logging level")


class EventsConfig(BaseModel):
    """Events configuration."""

    model_config = {"frozen": True}

    patterns: list[str] = Field(default_factory=list, description="Event file patterns")
    format: str = Field(default="ndjson", description="Event file format")


class Settings(BaseSettings):
    """Main settings container with environment override support.

    Environment variables override TOML values using prefix ``W2T_BKIN_`` and the
    double underscore nested delimiter (``__``). For example:

    - ``W2T_BKIN_PROJECT__NAME`` overrides ``[project].name``
    - ``W2T_BKIN_SYNC__TOLERANCE_MS`` overrides ``[sync].tolerance_ms``
    - ``W2T_BKIN_VIDEO__TRANSCODE__CRF`` overrides ``[video.transcode].crf``

    Deterministic precedence (M-NFR-1): ENV > TOML file > defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="W2T_BKIN_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    # Root sections / models
    project: ProjectConfig
    paths: PathsConfig | None = None
    session: SessionConfig | None = None
    video: VideoConfig = Field(default_factory=VideoConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    labels: LabelsConfig | None = None
    facemap: FacemapConfig = Field(default_factory=FacemapConfig)
    nwb: NWBConfig | None = None
    qc: QCConfig | None = None
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    events: EventsConfig = Field(default_factory=EventsConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        """Prioritize environment variables over TOML init values.

        By default pydantic-settings v2 loads init values first, then env vars.
        For configuration we want env vars to *override* file-provided values.
        Returning sources in this order enforces ENV > INIT > SECRETS which
        satisfies deterministic precedence (M-NFR-1) and allows overrides for
        nested fields like ``SYNC__TOLERANCE_MS``.
        """
        return (
            env_settings,  # highest precedence
            init_settings,  # values parsed from TOML
            file_secret_settings,  # (unused currently) retained for future layered configs
        )


def load_settings(path: str | Path) -> Settings:
    """Load and validate configuration from TOML file with environment overrides.

    Args:
        path: Path to TOML configuration file (string or Path object)

    Returns:
        Immutable Settings object with validated configuration

    Raises:
        ConfigValidationError: On file not found, parse errors, or validation failures

    Requirements:
        - MR-1: Load configuration from TOML and environment overrides
        - MR-2: Validate all keys and types using Pydantic models
        - MR-3: Provide an immutable settings object
        - MR-4: Raise descriptive ConfigValidationError on errors
    """
    config_path = Path(path)

    # Check file exists
    if not config_path.exists():
        raise ConfigValidationError(f"Configuration file not found: {config_path}")

    # Load and parse TOML
    try:
        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)
    except Exception as e:
        raise ConfigValidationError(f"Failed to parse TOML file {config_path}: {e}") from e

    # Validate and create settings with environment overrides
    # Environment variables will take precedence due to settings_customise_sources
    try:
        settings = Settings(**toml_data)
    except Exception as e:
        # Extract field name from validation error if possible
        error_msg = str(e)
        raise ConfigValidationError(f"Configuration validation failed: {error_msg}") from e

    return settings


__all__ = [
    "Settings",
    "ProjectConfig",
    "PathsConfig",
    "SessionConfig",
    "VideoConfig",
    "VideoTranscodeConfig",
    "SyncConfig",
    "TTLChannelConfig",
    "DLCConfig",
    "SLEAPConfig",
    "LabelsConfig",
    "FacemapConfig",
    "NWBConfig",
    "QCConfig",
    "LoggingConfig",
    "EventsConfig",
    "ConfigValidationError",
    "load_settings",
]
