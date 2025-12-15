"""API models for w2t-bkin pipeline.

This module defines user-facing API models for Prefect flows and future REST APIs.
These models provide structured, validated configuration with auto-generated UI forms
in Prefect. They replace raw JSON parameters with type-safe, documented configuration
objects.

Architecture:
- api.py: User-facing interface models (Pydantic schemas for validation)
- models.py: Internal domain models (business logic data structures)
- flows/: Orchestration logic that consumes API models

Benefits:
- Auto-generated UI forms with validation in Prefect
- Type safety and IDE autocompletion
- Clear documentation in Prefect UI
- Default values and constraints
- Consistent parameter structure across all interfaces
- Separation of API concerns from domain logic

Example:
    >>> from w2t_bkin.api import SessionFlowConfig
    >>> config = SessionFlowConfig(
    ...     config_path="/configs/standard.toml",
    ...     subject_id="subject-001",
    ...     session_id="session-001"
    ... )
    >>> # Use with flows
    >>> from w2t_bkin.flows import process_session_flow
    >>> result = process_session_flow(config)
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionFlowConfig(BaseModel):
    """Configuration for single session processing flow.

    This model defines all parameters for the process_session_flow, providing
    validation and documentation for the Prefect UI.

    Configuration Hierarchy:
        The configuration system uses a 2-layer hierarchy where the project layer
        overrides the base layer:
        1. base_config_path: Package defaults (configs/standard.toml)
        2. project_config_path: User/experiment settings (from 'w2t-bkin data init')

        Runtime overrides are handled via individual flow parameters (skip_*, force_rerun, etc.)
        rather than a third config file.

    Attributes:
        base_config_path: Base configuration file (package defaults, optional)
        project_config_path: Project configuration (from 'data init', optional)
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")
        skip_bpod: Skip Bpod behavioral data processing
        skip_pose: Skip all pose estimation processing
        skip_dlc: Skip DeepLabCut pose estimation only
        skip_sleap: Skip SLEAP pose estimation only
        skip_ecephys: Skip electrophysiology processing
        skip_camera_sync: Skip camera synchronization verification
        skip_nwb_validation: Skip NWB file validation step

    Example:
        >>> # Minimal usage with package defaults only
        >>> config = SessionFlowConfig(
        ...     subject_id="subject-001",
        ...     session_id="session-001"
        ... )
        >>>
        >>> # With project config (typical usage)
        >>> config = SessionFlowConfig(
        ...     project_config_path="/data/project/config.toml",
        ...     subject_id="subject-001",
        ...     session_id="session-001",
        ...     skip_nwb_validation=True
        ... )
    """

    subject_id: str = Field(
        ...,
        description="Subject identifier (e.g., subject-001, SNA-12345)",
        examples=["subject-001", "SNA-12345"],
        pattern=r"^[\w\-]+$",
    )
    session_id: str = Field(
        ...,
        description="Session identifier (e.g., session-001, 2024-01-15)",
        examples=["session-001", "2024-01-15"],
        pattern=r"^[\w\-]+$",
    )
    skip_bpod: bool = Field(
        False,
        description="Skip Bpod behavioral data processing",
    )
    skip_pose: bool = Field(
        False,
        description="Skip all pose estimation processing (DLC + SLEAP)",
    )
    skip_dlc: bool = Field(
        False,
        description="Skip DeepLabCut pose estimation only",
    )
    skip_sleap: bool = Field(
        False,
        description="Skip SLEAP pose estimation only",
    )
    skip_ecephys: bool = Field(
        False,
        description="Skip extracellular electrophysiology (Neuropixels) processing",
    )
    skip_camera_sync: bool = Field(
        False,
        description="Skip camera-TTL frame counting and synchronization verification (speeds up processing)",
    )
    skip_nwb_validation: bool = Field(
        False,
        description="Skip NWB file validation with nwbinspector",
    )

    # Configuration overrides (optional - override TOML config values)
    force_rerun: Optional[bool] = Field(
        None,
        description="Override preprocessing.force_rerun from config file. "
        "Set to true to regenerate all cached artifacts (pose estimates). "
        "WARNING: Significantly increases processing time (requires GPU inference).",
    )
    check_sync_mismatch: Optional[bool] = Field(
        None,
        description="Override verification.check_sync_mismatch from config file. " "Set to false to skip TTL synchronization checks (useful for sessions without TTL data).",
    )
    mismatch_tolerance_frames: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Override verification.mismatch_tolerance_frames from config file. " "Maximum allowed frame/TTL pulse count difference (0-100 frames).",
    )
    gpu_index: Optional[int] = Field(
        None,
        ge=0,
        le=7,
        description="GPU device to use for pose estimation (0-7). Overrides auto-detection. " "Leave empty to auto-detect available GPU.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "title": "Session Processing Configuration",
            "description": "Configuration for processing a single experimental session",
        }
    )


class BatchFlowConfig(BaseModel):
    """Configuration for batch session processing flow.

    This model defines all parameters for the batch_process_flow, enabling
    parallel processing of multiple sessions with filtering and concurrency control.

    Configuration Hierarchy:
        Uses the same 2-layer hierarchy as SessionFlowConfig:
        1. base_config_path: Package defaults (configs/standard.toml)
        2. project_config_path: Experiment settings (from 'data init')

    Attributes:
        base_config_path: Base configuration file (package defaults, optional)
        project_config_path: Project configuration (from 'data init', optional)
        subject_filter: Subject ID filter pattern (glob syntax, e.g., "subject-*")
        session_filter: Session ID filter pattern (glob syntax, e.g., "session-00*")
        max_parallel: Maximum number of sessions to process concurrently
        skip_bpod: Skip Bpod behavioral data processing
        skip_pose: Skip all pose estimation processing
        skip_ecephys: Skip electrophysiology processing
        skip_camera_sync: Skip camera synchronization verification
        skip_nwb_validation: Skip NWB file validation step

    Example:
        >>> config = BatchFlowConfig(
        ...     subject_filter="subject-*",
        ...     session_filter="session-00*",
        ...     max_parallel=4
        ... )
    """

    subject_filter: Optional[str] = Field(
        None,
        description="Subject ID filter pattern (glob syntax, e.g., 'subject-*', 'SNA-*')",
        examples=["subject-*", "SNA-*", "subject-001"],
    )
    session_filter: Optional[str] = Field(
        None,
        description="Session ID filter pattern (glob syntax, e.g., 'session-00*', '2024-*')",
        examples=["session-*", "session-00*", "2024-01-*"],
    )
    max_parallel: int = Field(
        4,
        description="Maximum number of sessions to process in parallel",
        ge=1,
        le=16,
    )
    skip_bpod: bool = Field(
        False,
        description="Skip Bpod behavioral data processing for all sessions",
    )
    skip_pose: bool = Field(
        False,
        description="Skip all pose estimation processing for all sessions",
    )
    skip_ecephys: bool = Field(
        False,
        description="Skip electrophysiology processing for all sessions",
    )
    skip_camera_sync: bool = Field(
        False,
        description="Skip camera synchronization verification for all sessions (speeds up batch processing)",
    )
    skip_nwb_validation: bool = Field(
        False,
        description="Skip NWB file validation for all sessions",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "title": "Batch Processing Configuration",
            "description": "Configuration for parallel processing of multiple sessions",
        }
    )


__all__ = [
    "SessionFlowConfig",
    "BatchFlowConfig",
]
