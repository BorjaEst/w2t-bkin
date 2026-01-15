"""Configuration management for W2T-BKIN pipeline.

This module provides Pydantic models for validating configuration files (config.toml)
and functions for loading, validating, and hashing configurations.

The configuration system enforces strict schema validation to catch errors early,
supports deterministic hashing for reproducibility, and provides clear error messages.

Key Configuration Sections:
    - Synchronization: Hardware sync strategy and alignment settings
    - Preprocessing: Pose estimation (DLC, SLEAP) and other preprocessing tasks
    - Verification: Runtime checks for frame counts and sync validation
    - Video: Video analysis and transcoding settings
    - Bpod: Behavioral trial synchronization mappings
    - NWB: Neurodata Without Borders export configuration
    - QC: Quality control report generation
    - Logging: Log level and format settings

Model Path Resolution:
    Pose estimation model paths in PreprocessingConfig are resolved relative
    to paths.models_root. Use the resolve_model_path() method on DLCConfig
    or SLEAPConfig to get absolute paths.

Typical usage example:
    >>> from w2t_bkin.config import SessionConfig
    >>> from pathlib import Path
    >>>
    >>> # SessionConfig is used for Prefect flow parameters
    >>> print(config.synchronization.strategy)
    >>>
    >>> # Resolve DLC model path
    >>> if config.preprocessing.dlc.enabled:
    ...     # models_root is supplied separately (e.g., via env vars / deployment)
    ...     model_path = config.preprocessing.dlc.resolve_model_path(Path("models"))
    ...     print(f"DLC model: {model_path}")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from w2t_bkin.utils import compute_hash, read_toml, recursive_dict_update

# =============================================================================
# Constants
# =============================================================================

VALID_SYNC_STRATEGIES = frozenset({"rate_based", "hardware_pulse", "network_stream"})
VALID_ALIGNMENT_METHODS = frozenset({"nearest", "linear"})
VALID_LOGGING_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# =============================================================================
# Configuration Models - Core
# =============================================================================


class PathsConfig(BaseModel, extra="forbid"):
    """Filesystem roots used by the pipeline.

    Prefect shows these values under **Quick run**/**Custom run**; each path is
    normalized to an absolute path during validation to avoid worker/host
    differences.
    """

    raw_root: Path = Field(
        ...,
        description=("Root directory containing raw session folders (inputs)."),
    )
    intermediate_root: Path = Field(
        ...,
        description=("Root directory for intermediate artifacts (recomputable outputs)."),
    )
    output_root: Path = Field(
        ...,
        description=("Root directory for final outputs (e.g., NWB files, QC reports, figures)."),
    )
    models_root: Path = Field(
        default="models",
        description=(
            "Directory containing pose estimation models. Relative paths are resolved "
            "from the working directory."  # noqa: E501
        ),
    )
    root_metadata: Optional[Path] = Field(
        None,
        description=("Optional global metadata file applied as a base layer before per-session metadata."),
    )

    @model_validator(mode="after")
    def resolve_paths(self) -> "PathsConfig":
        """Resolve all paths to absolute paths.

        Converts relative paths to absolute paths based on current working directory.
        This ensures consistent path handling regardless of execution context.

        Note: If paths are already absolute (e.g., from deployment config), they are
        kept as-is. This allows deployments to pre-resolve paths at deployment time.
        """
        # Only resolve if path is relative
        if not self.raw_root.is_absolute():
            self.raw_root = self.raw_root.resolve()
        if not self.intermediate_root.is_absolute():
            self.intermediate_root = self.intermediate_root.resolve()
        if not self.output_root.is_absolute():
            self.output_root = self.output_root.resolve()
        if not self.models_root.is_absolute():
            self.models_root = self.models_root.resolve()
        if self.root_metadata and not self.root_metadata.is_absolute():
            self.root_metadata = self.root_metadata.resolve()
        return self


class AlignmentConfig(BaseModel, extra="forbid"):
    """How timestamps are mapped between devices.

    Used by synchronization to convert event times from one timebase to another
    and to validate the quality of that mapping.
    """

    method: Literal["nearest", "linear"] = Field(
        ...,
        description=(
            "Timestamp mapping method: 'nearest' snaps to the closest sample; "
            "'linear' interpolates between samples."  # noqa: E501
        ),
    )
    tolerance_s: float = Field(
        ...,
        ge=0.0,
        description=("Maximum allowed absolute alignment error (seconds) used for validation/QC."),
    )
    global_offset_s: float = Field(
        default=0.0,
        description=("Constant offset (seconds) added before alignment. Useful for known fixed delays."),
    )


class SynchronizationConfig(BaseModel, extra="forbid"):
    """How different data streams are aligned onto a common timebase."""

    strategy: Literal["rate_based", "hardware_pulse", "network_stream"] = Field(
        ...,
        description=(
            "Synchronization strategy: 'rate_based' uses sampling rates; "
            "'hardware_pulse' aligns using TTL pulses; 'network_stream' aligns using a streamed reference."  # noqa: E501
        ),
    )
    reference_channel: Optional[str] = Field(
        None,
        description=("Reference channel name/ID used as the timebase for 'hardware_pulse' and 'network_stream'."),
    )
    alignment: AlignmentConfig = Field(
        ...,
        description=("Parameters controlling timestamp mapping and tolerance used during alignment."),
    )


class AcquisitionConfig(BaseModel, extra="forbid"):
    """Policies for handling raw acquisitions (e.g., multi-file videos)."""

    concat_strategy: Literal["ffconcat", "streamlist"] = Field(
        default="ffconcat",
        description=(
            "How to concatenate multi-file videos: 'ffconcat' uses the FFmpeg concat demuxer; "
            "'streamlist' uses a list of stream paths."  # noqa: E501
        ),
    )


class VerificationConfig(BaseModel, extra="forbid"):
    """Runtime consistency checks for synchronization and video integrity."""

    enabled: bool = Field(
        default=True,
        description="If True, run verification checks during session processing.",
    )
    check_frame_counts: bool = Field(
        default=True,
        description=("If True, count video frames (accurate but can be slow for large/remote files)."),
    )
    check_sync_mismatch: bool = Field(
        default=True,
        description=("If True, compare video frame counts against TTL pulse counts for the reference channel."),
    )
    mismatch_tolerance_frames: int = Field(
        default=0,
        ge=0,
        description=("Allowed absolute mismatch (frames) between frame_count and ttl_pulse_count before failing."),
    )
    warn_on_mismatch: bool = Field(
        default=False,
        description=("If True, warn (and continue) when mismatch is within tolerance; otherwise raise an error."),
    )


# =============================================================================
# Configuration Models - Bpod
# =============================================================================


class BpodSyncTrialType(BaseModel, extra="forbid"):
    """Per-trial mapping used to align Bpod timestamps to a TTL timebase."""

    trial_type: int = Field(
        ...,
        ge=0,
        description="Numeric trial type label produced by Bpod trial classification.",
    )
    sync_signal: str = Field(
        ...,
        description=("Bpod state/event name whose onset should align to TTL pulses (e.g., 'W2T_Audio')."),
    )
    sync_ttl: str = Field(
        ...,
        description="TTL channel name/ID that carries the pulses for sync_signal.",
    )


class BpodSyncConfig(BaseModel, extra="forbid"):
    """Bpod-to-TTL synchronization mappings."""

    trial_types: List[BpodSyncTrialType] = Field(
        default_factory=list,
        description=("List of per-trial-type synchronization rules used to convert Bpod times to absolute time."),
    )


class BpodConfig(BaseModel, extra="forbid"):
    """Settings for parsing and synchronizing Bpod behavioral data."""

    parse: bool = Field(
        default=True,
        description="Parse Bpod .mat files when present in the session raw data.",
    )
    pattern: str = Field(
        default="Bpod/*.mat",
        description="Glob pattern for Bpod MAT files (relative to the session directory). This is used when session metadata does not provide a [bpod] section.",
    )

    order: Literal["name_asc", "name_desc", "time_asc", "time_desc"] = Field(
        default="time_asc",
        description="Sort order used when multiple Bpod files match the pattern.",
    )
    continuous_time: bool = Field(
        default=True,
        description="If True, offsets timestamps to form a continuous timeline across multiple Bpod files. This only matters when more than one MAT file is merged.",
    )
    sync: BpodSyncConfig = Field(
        default_factory=BpodSyncConfig,
        description="Mappings that define how Bpod trial events align to TTL/video time.",
    )


# =============================================================================
# Configuration Models - Video
# =============================================================================


class TranscodeConfig(BaseModel, extra="forbid"):
    """FFmpeg transcoding parameters for derived videos."""

    enabled: bool = Field(
        default=True,
        description="If True, transcode raw videos into a standardized codec/format for downstream tools.",
    )
    codec: str = Field(
        default="h264",
        description="FFmpeg video codec name used for transcoding (e.g., 'libx264').",
    )
    crf: int = Field(
        default=20,
        ge=0,
        le=51,
        description="FFmpeg CRF quality value (0–51); lower means higher quality/larger files.",
    )
    preset: str = Field(
        default="fast",
        description="FFmpeg encoder preset controlling speed vs compression ratio.",
    )
    keyint: int = Field(
        default=15,
        ge=1,
        description="Keyframe interval (GOP size) in frames; impacts seeking and compression.",
    )


class VideoAnalysisConfig(BaseModel, extra="forbid"):
    """Performance controls for video probing tasks."""

    frame_count_timeout: int = Field(
        default=30,
        ge=1,
        description=("Timeout (seconds) for frame counting/probing per file; increase for long/slow-to-open videos."),
    )


class VideoConfig(BaseModel, extra="forbid"):
    """Video analysis and transcoding settings."""

    analysis: VideoAnalysisConfig = Field(
        default_factory=VideoAnalysisConfig,
        description="Settings for probing/counting frames and other lightweight video analysis.",
    )
    transcode: TranscodeConfig = Field(
        default_factory=TranscodeConfig,
        description="Settings for producing derived/transcoded videos.",
    )


# =============================================================================
# Configuration Models - Output & Logging
# =============================================================================


class NWBConfig(BaseModel, extra="forbid"):
    """Parameters used when exporting NWB files."""

    link_external_video: bool = Field(
        default=True,
        description=("If True, store videos as external file references in NWB (recommended) instead of embedding video bytes."),
    )
    lab: str = Field(
        default="Lab Name",
        description="Lab name written into NWB metadata.",
    )
    institution: str = Field(
        default="Institution Name",
        description="Institution name written into NWB metadata.",
    )
    file_name_template: str = Field(
        default="{session.id}.nwb",
        description="Output NWB filename template (supports '{session.*}' placeholders).",
    )
    session_description_template: str = Field(
        default="Session {session.id} on {session.date}",
        description="Human-readable NWB session description template (supports '{session.*}' placeholders).",
    )


class QCConfig(BaseModel, extra="forbid"):
    """Options for QC summary generation."""

    generate_report: bool = Field(
        default=True,
        description="If True, generate QC outputs (plots/metrics) for each processed session.",
    )
    out_template: str = Field(
        default="qc/{session.id}",
        description="Output path template (relative to output_root) for QC artifacts.",
    )
    include_verification: bool = Field(
        default=True,
        description="If True, include verification results (frame counts, TTL mismatch checks) in QC outputs.",
    )


class LoggingConfig(BaseModel, extra="forbid"):
    """Runtime logging behavior."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum log severity to emit.",
    )
    structured: bool = Field(
        default=False,
        description="If True, emit logs as structured JSON (better for log aggregation).",
    )


# =============================================================================
# Configuration Models - Pose Estimation (Preprocessing)
# =============================================================================


class DLCConfig(BaseModel, extra="forbid"):
    """DeepLabCut (DLC) pose estimation settings.

    Mode Controls:
        - off: Skip DLC processing entirely
        - discover: Use pre-existing H5 files via stem-based discovery
                   H5s must be in interim/dlc-pose/<camera_id>/ with names {video_stem}DLC*.h5
        - generate: Run DLC inference to create H5 files (requires metadata.pose.cameras + metadata.pose.models)
        - auto: Generate if metadata.pose.models exists, otherwise discover

    Note:
        Model selection is per-camera via metadata.pose.cameras.<camera_id>.model_id,
        which references metadata.pose.models.<model_id>.path (relative to paths.models_root).
    """

    mode: Literal["off", "discover", "generate", "auto"] = Field(
        default="auto",
        description=(
            "Pose source policy: 'off' disables DLC, 'discover' uses pre-existing H5 files, "
            "'generate' runs DLC inference (requires metadata.pose with model definitions), 'auto' decides based on metadata."
        ),
    )
    gpu: Optional[int] = Field(
        None,
        description="GPU index to use (None = default/auto, -1 = force CPU).",
    )
    save_csv: bool = Field(
        default=False,
        description="If True, export pose results as CSV in addition to HDF5.",
    )


class SLEAPConfig(BaseModel, extra="forbid"):
    """SLEAP pose estimation settings.

    Mode Controls:
        - off: Skip SLEAP processing entirely
        - discover: Use pre-existing H5 files via stem-based discovery
                   H5s must be in interim/sleap-pose/<camera_id>/ with names *{video_stem}*.h5
        - generate: Run SLEAP inference (NOT IMPLEMENTED - will raise error)
        - auto: Defaults to discover (generate mode not yet supported)

    Note:
        Model selection is per-camera via metadata.pose.cameras.<camera_id>.model_id,
        which references metadata.pose.models.<model_id>.path (relative to paths.models_root).
    """

    mode: Literal["off", "discover", "generate", "auto"] = Field(
        default="auto",
        description=("Pose source policy: 'off' disables SLEAP, 'discover' uses pre-existing H5 files, " "'generate' is NOT IMPLEMENTED, 'auto' defaults to discover."),
    )
    gpu: Optional[int] = Field(
        None,
        description="GPU index to use (None = default/auto, -1 = force CPU).",
    )

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "SLEAPConfig":
        """Ensure mode is valid.

        Raises:
            ValueError: If mode='generate' (not implemented for SLEAP).

        Note:
            Model validation is deferred to runtime since models are defined
            per-camera in metadata, not in pipeline config.
        """
        # SLEAP generate mode not implemented
        if self.mode == "generate":
            raise ValueError("SLEAP mode='generate' is not yet implemented. " "Use mode='discover' to ingest pre-existing SLEAP H5 files.")

        return self


class PreprocessingConfig(BaseModel, extra="forbid"):
    """Optional preprocessing steps that create intermediate artifacts."""

    force_rerun: bool = Field(
        default=False,
        description="If True, recompute preprocessing outputs even if cached intermediates exist.",
    )
    dlc: DLCConfig = Field(
        default_factory=DLCConfig,
        description="DeepLabCut pose estimation configuration.",
    )
    sleap: SLEAPConfig = Field(
        default_factory=SLEAPConfig,
        description="SLEAP pose estimation configuration.",
    )


# =============================================================================
# Prefect Flow Configuration Models (UI Parameters)
# =============================================================================


class TTLsConfig(BaseModel, extra="forbid"):
    """Parameters controlling camera-TTL mismatch checking."""

    enable: bool = Field(
        default=True,
        description=("If True, verify frame/TTL synchronization for cameras configured with TTL sync."),
    )


class CamerasConfig(BaseModel, extra="forbid"):
    enable_loading: bool = Field(
        default=True,
        description="If True, parse camera video files when present in the session raw data.",
    )
    ttl_validation: bool = Field(
        default=True,
        description=("If True, compare video frame counts against TTL pulse counts for the reference channel."),
    )
    ttl_tolerance: int = Field(
        default=0,
        ge=0,
        description=("Allowed absolute mismatch (frames) between frame_count and ttl_pulse_count before failing."),
    )
    mismatch_warn_only: bool = Field(
        default=False,
        description=("If True, warn (and continue) when mismatch is within tolerance; otherwise raise an error."),
    )


class BpodConfig(BaseModel, extra="forbid"):
    enable_loading: bool = Field(
        default=True,
        description="If True, parse Bpod .mat files when present in the session raw data.",
    )
    continuous_time: bool = Field(
        default=True,
        description="If True, offsets timestamps to form a continuous timeline across multiple Bpod files. This only matters when more than one MAT file is merged.",
    )


class PoseProcessingConfig(BaseModel, extra="forbid"):
    """DeepLabCut or SLEAP pose estimation configuration."""

    mode: Literal["off", "discover", "generate", "auto"] = Field(
        default="auto",
        description=(
            "off: disables pose estimation, 'discover' uses pre-existing H5 files; "
            "discover: Use pre-existing H5 files via stem-based discovery; "
            "generate: Forces pose estimation to run; "
            "auto: Generate if metadata.pose.models exists and no pre-existing files are found, otherwise discover;"
        ),
    )
    gpu: Optional[int] = Field(
        None,
        description="GPU index to use (None = default/auto, -1 = force CPU).",
    )
    save_csv: bool = Field(
        default=False,
        description="If True, export pose results as CSV in addition to HDF5.",
    )


# =============================================================================
# Configuration Models - Session Level
# =============================================================================


class DiscoveryConfig(BaseModel, extra="forbid"):
    """File discovery patterns and policies."""

    ttl_signals: TTLsConfig = Field(
        default_factory=TTLsConfig,
        description=("Parameters controlling TTL channel discovery and validation."),
    )
    cameras: CamerasConfig = Field(
        default_factory=CamerasConfig,
        description=("Parameters controlling camera-TTL mismatch checking."),
    )
    bpod: BpodConfig = Field(
        default_factory=BpodConfig,
        description=("Settings for parsing and synchronizing Bpod behavioral data."),
    )


class ArtifactsConfig(BaseModel, extra="forbid"):
    dlc: PoseProcessingConfig = Field(
        default_factory=PoseProcessingConfig,
        description="DeepLabCut pose estimation configuration.",
    )
    sleap: PoseProcessingConfig = Field(
        default_factory=PoseProcessingConfig,
        description="SLEAP pose estimation configuration.",
    )


class IngestionConfig(BaseModel, extra="forbid"):
    pass


class AssemblyConfig(BaseModel, extra="forbid"):
    pass


class FinalizationConfig(BaseModel, extra="forbid"):
    pass


class SessionConfig(BaseModel, extra="forbid"):
    """Per-session pipeline configuration (shown in Prefect UI).

    This model intentionally excludes filesystem paths (handled via environment
    variables / deployment config). Keep defaults deterministic: avoid loading
    files in default factories.
    """

    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging verbosity and output format.",
    )
    discovery: DiscoveryConfig = Field(
        default_factory=DiscoveryConfig,
        description="File discovery patterns and policies.",
    )
    artifacts: ArtifactsConfig = Field(
        default_factory=ArtifactsConfig,
        description="Policies for handling intermediate artifacts (pose, TTL, sync).",
    )
    ingestion: IngestionConfig = Field(
        default_factory=IngestionConfig,
        description="How raw data files are ingested and parsed.",
    )
    synchronization: SynchronizationConfig = Field(
        default_factory=SynchronizationConfig,
        description="How modalities (video/TTL/Bpod) are aligned to a common timebase.",
    )
    assembly: AssemblyConfig = Field(
        default_factory=AssemblyConfig,
        description="How ingested data streams are combined into unified datasets.",
    )
    finalization: FinalizationConfig = Field(
        default_factory=FinalizationConfig,
        description="Final processing steps before output (NWB export, QC generation).",
    )


class BatchFlowConfig(BaseModel, extra="forbid"):
    """Batch-run parameters: select sessions and control concurrency."""

    subject_filter: Optional[str] = Field(
        None,
        description="Optional glob used to select subject IDs (e.g., 'subject-*').",
    )
    session_filter: Optional[str] = Field(
        None,
        description="Optional glob used to select session IDs (e.g., 'session-001*').",
    )
    max_parallel: int = Field(
        4,
        ge=1,
        le=32,
        description="Maximum number of sessions processed concurrently.",
    )
    configuration: SessionConfig = Field(
        ...,
        description="Session-level configuration applied to every selected session.",
    )


# =============================================================================
# Configuration Loading
# =============================================================================


def _load_paths_from_env() -> Dict[str, Any]:
    """Load path configuration from environment variables.

    Environment variables override configuration file settings.
    Supported variables:
    - W2T_RAW_ROOT
    - W2T_INTERMEDIATE_ROOT
    - W2T_OUTPUT_ROOT
    - W2T_MODELS_ROOT
    - W2T_ROOT_METADATA
    """
    paths = {}
    if raw := os.getenv("W2T_RAW_ROOT"):
        paths["raw_root"] = raw
    if interim := os.getenv("W2T_INTERMEDIATE_ROOT"):
        paths["intermediate_root"] = interim
    if output := os.getenv("W2T_OUTPUT_ROOT"):
        paths["output_root"] = output
    if models := os.getenv("W2T_MODELS_ROOT"):
        paths["models_root"] = models
    if metadata := os.getenv("W2T_ROOT_METADATA"):
        paths["root_metadata"] = metadata

    return {"paths": paths} if paths else {}


# =============================================================================
# Private Validation Helpers
# =============================================================================


def _validate_config_enums(data: Dict[str, Any]) -> None:
    """Validate enum constraints before Pydantic validation.

    Pre-validates enum fields to provide clearer error messages than
    Pydantic's default validation.

    Args:
        data: Raw configuration dict from TOML.

    Raises:
        ValueError: If any enum value is invalid.
    """
    sync = data.get("synchronization", {})
    alignment = sync.get("alignment", {})

    # Validate synchronization.strategy
    strategy = sync.get("strategy")
    if strategy and strategy not in VALID_SYNC_STRATEGIES:
        raise ValueError(f"Invalid synchronization.strategy: '{strategy}'. " f"Must be one of {sorted(VALID_SYNC_STRATEGIES)}")

    # Validate synchronization.alignment.method
    method = alignment.get("method")
    if method and method not in VALID_ALIGNMENT_METHODS:
        raise ValueError(f"Invalid synchronization.alignment.method: '{method}'. " f"Must be one of {sorted(VALID_ALIGNMENT_METHODS)}")

    # Validate tolerance_s >= 0
    tolerance = alignment.get("tolerance_s")
    if tolerance is not None and tolerance < 0:
        raise ValueError(f"Invalid synchronization.alignment.tolerance_s: {tolerance}. " f"Must be >= 0")

    # Validate logging.level
    logging_config = data.get("logging", {})
    level = logging_config.get("level")
    if level and level not in VALID_LOGGING_LEVELS:
        raise ValueError(f"Invalid logging.level: '{level}'. " f"Must be one of {sorted(VALID_LOGGING_LEVELS)}")


def _validate_config_conditionals(data: Dict[str, Any]) -> None:
    """Validate conditional requirements before Pydantic validation.

    Checks that required fields are present based on other field values.

    Args:
        data: Raw configuration dict from TOML.

    Raises:
        ValueError: If conditional requirements are not met.
    """
    sync = data.get("synchronization", {})
    strategy = sync.get("strategy")

    if strategy == "hardware_pulse" and not sync.get("reference_channel"):
        raise ValueError("synchronization.reference_channel is required when synchronization.strategy='hardware_pulse'")

    if strategy == "network_stream" and not sync.get("reference_channel"):
        raise ValueError("synchronization.reference_channel is required when " "synchronization.strategy='network_stream'")
