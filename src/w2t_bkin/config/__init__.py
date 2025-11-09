"""Configuration module for W2T BKin pipeline.

Load and validate TOML configuration with Pydantic models and environment overrides.
As a Layer 1 module, may import: domain, utils.

Requirements: FR-10 (Configuration-driven), NFR-10 (Type safety)
Design: design.md §2 (Module Breakdown), §21.1 (Dependency Tree)
API: api.md §3.3
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomli as tomllib  # Python < 3.11
except ImportError:
    import tomllib  # Python >= 3.11

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "Settings",
    "load_settings",
    "ENV_PREFIX",
]

ENV_PREFIX = "W2T_"


# ============================================================================
# Configuration Models (FR-10, NFR-10)
# ============================================================================


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    name: str = Field(default="w2t-bkin-pipeline")
    n_cameras: int = Field(default=5, ge=1, le=10)


class PathsConfig(BaseModel):
    """Directory paths configuration."""

    raw_root: Path = Field(default=Path("data/raw"))
    intermediate_root: Path = Field(default=Path("data/interim"))
    output_root: Path = Field(default=Path("data/processed"))
    models_root: Path = Field(default=Path("models"))

    @field_validator("raw_root", "intermediate_root", "output_root", "models_root", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand environment variables and user home in paths."""
        if isinstance(v, str):
            return Path(os.path.expandvars(os.path.expanduser(v)))
        return v


class SessionConfig(BaseModel):
    """Session metadata configuration."""

    id: str = Field(default="")
    subject_id: str = Field(default="")
    date: str = Field(default="")
    experimenter: str = Field(default="")
    description: str = Field(default="")
    sex: str = Field(default="")
    age: str = Field(default="")
    genotype: str = Field(default="")


class TranscodeConfig(BaseModel):
    """Video transcoding configuration."""

    enabled: bool = Field(default=False)
    codec: str = Field(default="libx264")
    crf: int = Field(default=18, ge=0, le=51)
    preset: str = Field(default="medium")
    keyint: int = Field(default=30, ge=1)


class VideoConfig(BaseModel):
    """Video processing configuration."""

    pattern: str = Field(default="**/*.mp4")
    fps: float = Field(default=30.0, gt=0)
    transcode: TranscodeConfig = Field(default_factory=TranscodeConfig)


class TTLChannelConfig(BaseModel):
    """TTL channel configuration for sync."""

    path: str = Field(default="")
    name: str = Field(default="")
    polarity: str = Field(default="rising")

    @field_validator("polarity")
    @classmethod
    def validate_polarity(cls, v: str) -> str:
        """Validate polarity is either 'rising' or 'falling'."""
        if v not in ["rising", "falling"]:
            raise ValueError(f"polarity must be 'rising' or 'falling', got '{v}'")
        return v


class SyncConfig(BaseModel):
    """Synchronization configuration."""

    ttl_channels: list[TTLChannelConfig] = Field(default_factory=list)
    tolerance_ms: float = Field(default=2.0, ge=0)
    drop_frame_max_gap_ms: float = Field(default=100.0, ge=0)
    primary_clock: str = Field(default="cam0")


class DLCConfig(BaseModel):
    """DeepLabCut configuration."""

    model: str = Field(default="")
    run_inference: bool = Field(default=False)


class SLEAPConfig(BaseModel):
    """SLEAP configuration."""

    model: str = Field(default="")
    run_inference: bool = Field(default=False)


class LabelsConfig(BaseModel):
    """Pose labeling configuration."""

    dlc: DLCConfig = Field(default_factory=DLCConfig)
    sleap: SLEAPConfig = Field(default_factory=SLEAPConfig)


class FacemapConfig(BaseModel):
    """Facemap configuration."""

    run: bool = Field(default=False)
    roi: str = Field(default="")


class NWBConfig(BaseModel):
    """NWB export configuration."""

    link_external_video: bool = Field(default=True)
    file_name: str = Field(default="")
    session_description: str = Field(default="")
    lab: str = Field(default="")
    institution: str = Field(default="")


class QCConfig(BaseModel):
    """Quality control configuration."""

    generate_report: bool = Field(default=True)
    out: str = Field(default="qc")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO")
    structured: bool = Field(default=False)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}, got '{v}'")
        return v_upper


class EventsConfig(BaseModel):
    """Events configuration."""

    patterns: list[str] = Field(
        default_factory=lambda: ["**/*_training.ndjson", "**/*_trial_stats.ndjson"]
    )
    format: str = Field(default="ndjson")


class Settings(BaseModel):
    """Complete pipeline settings.
    
    Requirements: FR-10 (Configuration-driven via TOML)
    Design: requirements.md (Configuration keys)
    """

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    labels: LabelsConfig = Field(default_factory=LabelsConfig)
    facemap: FacemapConfig = Field(default_factory=FacemapConfig)
    nwb: NWBConfig = Field(default_factory=NWBConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    events: EventsConfig = Field(default_factory=EventsConfig)

    model_config = {"extra": "forbid"}  # Reject unknown keys


# ============================================================================
# Loading Functions (FR-10, NFR-10)
# ============================================================================


def load_settings(
    toml_path: Path | str | None = None,
    env_prefix: str = ENV_PREFIX,
) -> Settings:
    """Load and validate settings from TOML and environment.
    
    Args:
        toml_path: Path to TOML configuration file (optional)
        env_prefix: Environment variable prefix (default: W2T_)
        
    Returns:
        Validated Settings object
        
    Raises:
        FileNotFoundError: If toml_path specified but doesn't exist
        ValueError: If configuration is invalid
        
    Requirements: FR-10 (TOML + Pydantic), NFR-10 (Environment overrides)
    Design: api.md §3.3
    """
    config_dict: dict[str, Any] = {}

    # Load from TOML if provided
    if toml_path is not None:
        toml_path = Path(toml_path)
        if not toml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {toml_path}")

        with open(toml_path, "rb") as f:
            config_dict = tomllib.load(f)

    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict, env_prefix)

    # Validate and return
    return Settings(**config_dict)


def _apply_env_overrides(config: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Apply environment variable overrides to config dict.
    
    Supports nested keys with double underscore notation:
    W2T_PROJECT__NAME=my-project
    W2T_SYNC__TOLERANCE_MS=5.0
    
    Args:
        config: Configuration dictionary
        prefix: Environment variable prefix
        
    Returns:
        Configuration with environment overrides applied
    """
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Remove prefix and split nested keys
        config_key = key[len(prefix) :].lower()
        parts = config_key.split("__")

        # Navigate/create nested structure
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value (try to parse as appropriate type)
        final_key = parts[-1]
        current[final_key] = _parse_env_value(value)

    return config


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type.
    
    Args:
        value: String value from environment
        
    Returns:
        Parsed value (bool, int, float, or str)
    """
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Numeric
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # String (default)
    return value
