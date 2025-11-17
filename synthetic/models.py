"""Data models for synthetic data generation.

This module defines Pydantic models that describe synthetic data generation
parameters and outputs. These models ensure type safety and validation for
the synthetic data generation process.

Models:
-------
- SyntheticCamera: Parameters for generating synthetic camera data
- SyntheticTTL: Parameters for generating synthetic TTL data
- SyntheticSessionParams: Parameters for generating complete sessions
- SyntheticSession: Output paths for generated synthetic session

Design Principles:
------------------
- Use Pydantic for validation and type safety
- Immutable models (frozen=True)
- Sensible defaults for common test scenarios
- Clear field descriptions
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SyntheticCamera(BaseModel):
    """Parameters for generating synthetic camera data.

    Attributes:
        camera_id: Unique camera identifier (e.g., 'cam0', 'cam1')
        ttl_id: TTL channel ID for this camera (None = no TTL sync)
        frame_count: Number of frames to generate
        fps: Frames per second (for video generation)
        resolution: Video resolution as (width, height)
    """

    camera_id: str = Field(..., description="Unique camera identifier")
    ttl_id: Optional[str] = Field(None, description="TTL channel ID")
    frame_count: int = Field(64, ge=1, description="Number of frames")
    fps: float = Field(30.0, gt=0, description="Frames per second")
    resolution: tuple[int, int] = Field((640, 480), description="Video resolution (width, height)")

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, v: str) -> str:
        """Ensure camera_id is non-empty."""
        if not v.strip():
            raise ValueError("camera_id cannot be empty")
        return v


class SyntheticTTL(BaseModel):
    """Parameters for generating synthetic TTL pulse data.

    Attributes:
        ttl_id: Unique TTL channel identifier
        pulse_count: Number of pulses to generate
        start_time_s: Start time in seconds
        period_s: Time between pulses in seconds
        jitter_s: Random jitter to add to pulse times (0 = no jitter)
    """

    ttl_id: str = Field(..., description="Unique TTL channel identifier")
    pulse_count: int = Field(64, ge=1, description="Number of pulses")
    start_time_s: float = Field(0.0, ge=0, description="Start time in seconds")
    period_s: float = Field(0.033, gt=0, description="Period between pulses")
    jitter_s: float = Field(0.0, ge=0, description="Random jitter in seconds")

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("ttl_id")
    @classmethod
    def validate_ttl_id(cls, v: str) -> str:
        """Ensure ttl_id is non-empty."""
        if not v.strip():
            raise ValueError("ttl_id cannot be empty")
        return v


class SyntheticSessionParams(BaseModel):
    """Parameters for generating a complete synthetic session.

    Attributes:
        session_id: Unique session identifier
        subject_id: Subject identifier
        experimenter: Experimenter name
        date: Session date (YYYY-MM-DD format)
        cameras: List of camera configurations
        ttls: List of TTL configurations
        with_bpod: Whether to generate Bpod trial data
        bpod_trial_count: Number of Bpod trials
        with_pose: Whether to generate pose estimation data
        with_facemap: Whether to generate facemap data
        seed: Random seed for deterministic generation
    """

    session_id: str = Field(..., description="Unique session identifier")
    subject_id: str = Field("test-subject", description="Subject identifier")
    experimenter: str = Field("test-experimenter", description="Experimenter name")
    date: str = Field("2025-01-01", description="Session date (YYYY-MM-DD)")
    cameras: List[SyntheticCamera] = Field(default_factory=list, description="Camera configurations")
    ttls: List[SyntheticTTL] = Field(default_factory=list, description="TTL configurations")
    with_bpod: bool = Field(False, description="Generate Bpod data")
    bpod_trial_count: int = Field(10, ge=1, description="Number of Bpod trials")
    with_pose: bool = Field(False, description="Generate pose data")
    pose_keypoints: Optional[List[str]] = Field(None, description="List of keypoint names for pose (uses defaults if None)")
    with_facemap: bool = Field(False, description="Generate facemap data")
    seed: int = Field(42, description="Random seed for reproducibility")

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("session_id", "subject_id", "experimenter")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure identifiers are non-empty."""
        if not v.strip():
            raise ValueError("Identifier cannot be empty")
        return v


class SyntheticSession(BaseModel):
    """Output paths for a generated synthetic session.

    This model captures all paths created during synthetic session generation,
    making it easy for tests to reference the generated files.

    Attributes:
        root_dir: Root directory containing the session
        raw_dir: Raw data directory (session-specific)
        config_path: Path to generated config.toml
        session_path: Path to generated session.toml
        camera_video_paths: Dictionary of camera_id -> list of video paths
        ttl_paths: Dictionary of ttl_id -> TTL file path
        bpod_path: Path to Bpod .mat file (if generated)
        pose_path: Path to pose CSV file (if generated)
        facemap_path: Path to facemap .npy file (if generated)
    """

    root_dir: Path = Field(..., description="Root directory")
    raw_dir: Path = Field(..., description="Raw data directory")
    config_path: Path = Field(..., description="Path to config.toml")
    session_path: Path = Field(..., description="Path to session.toml")
    camera_video_paths: dict[str, List[Path]] = Field(default_factory=dict, description="Camera video paths")
    ttl_paths: dict[str, Path] = Field(default_factory=dict, description="TTL file paths")
    bpod_path: Optional[Path] = Field(None, description="Bpod .mat file path")
    pose_path: Optional[Path] = Field(None, description="Pose CSV file path")
    facemap_path: Optional[Path] = Field(None, description="Facemap .npy file path")

    model_config = {"frozen": False, "extra": "forbid", "arbitrary_types_allowed": True}
