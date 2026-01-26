# TODO: add module docstring

from typing import Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Prefect Flow Configuration Models (UI Parameters)
# =============================================================================


class TTLsConfig(BaseModel, extra="forbid"):
    """Parameters controlling camera-TTL mismatch checking."""

    enable_loading: bool = Field(
        default=True,
        description="If True, verify frame/TTL synchronization for cameras configured with TTL sync.",
    )


class VideoConfig(BaseModel, extra="forbid"):
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


class PoseConfig(BaseModel, extra="forbid"):
    enable_loading: bool = Field(
        default=True,
        description="If True, parse pose estimation H5 files when present in the session raw data.",
    )
    file_type: Literal["h5", "csv"] = Field(
        default="h5",
        description="Preferred pose estimation file type to load (h5 or csv).",
    )


class BaseAssembleConfig(BaseModel, extra="forbid"):
    """How normal data streams are assembled into NWB structures."""

    mode: Literal["skip", "assemble"] = Field(
        default="assemble",
        description="How to handle this data type during NWB assembly: 'skip' disables assembly of this data type into NWB; 'assemble' enables assembly into NWB.",
    )


class BaseLinkConfig(BaseModel, extra="forbid"):
    """How normal data streams are assembled into NWB structures."""

    mode: Literal["skip", "link"] = Field(
        default="assemble",
        description="How to handle this data type during NWB assembly: 'skip' disables assembly of this data type into NWB; 'link' creates external links to pre-existing NWB",
    )


# =============================================================================
# Configuration Models - Session Level
# =============================================================================


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


class DiscoveryConfig(BaseModel, extra="forbid"):
    """File discovery patterns and policies."""

    discover_cameras: bool = Field(
        default=True,
        description="Enable discovery of camera video files",
    )
    discover_ttl_signals: bool = Field(
        default=True,
        description="Enable discovery of TTL signal files",
    )
    discover_bpod: bool = Field(
        default=True,
        description="Enable discovery of Bpod behavioral files",
    )
    discover_pose: bool = Field(
        default=True,
        description="Enable discovery of pose data files",
    )
    discover_models: bool = Field(
        default=True,
        description="Enable discovery of pose estimation models",
    )


class ArtifactsConfig(BaseModel, extra="forbid"):
    """Policies for handling intermediate artifacts (pose, TTL, etc.)."""

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


class IngestionConfig(BaseModel, extra="forbid"):
    """How raw data files are ingested and parsed."""

    ttl_signals: TTLsConfig = Field(
        default_factory=TTLsConfig,
        description="Parameters controlling camera-TTL mismatch checking.",
    )
    video: VideoConfig = Field(
        default_factory=VideoConfig,
        description="Settings for ingesting camera video files.",
    )
    bpod: BpodConfig = Field(
        default_factory=BpodConfig,
        description="Settings for ingesting Bpod behavioral data.",
    )
    pose: PoseConfig = Field(
        default_factory=PoseConfig,
        description="Settings for ingesting pose estimation data.",
    )


class SynchronizationConfig(BaseModel, extra="forbid"):
    """How modalities (video/TTL/Bpod) are aligned to a common timebase."""

    strategy: Literal[
        "rate_based",
        "hardware_pulse",
        "hardware_pulse_robust",
        "network_stream",
    ] = Field(
        default="hardware_pulse",
        description=(
            "Synchronization strategy used for data:"
            "'rate_based' uses sampling rates; "
            "'hardware_pulse' aligns using TTL pulses; "
            "'network_stream' aligns using a streamed reference."
        ),
    )
    reference_channel: str = Field(
        default="ttl_camera",
        description=("Reference channel name/ID used as the timebase for " "'hardware_pulse' and 'network_stream'."),
    )
    alignment_method: Literal["nearest", "linear"] = Field(
        default="nearest",
        description=("Timestamp mapping method: 'none' disables alignment; " "'nearest' snaps to the closest sample; 'linear' " "interpolates between samples."),
    )
    tolerance: float = Field(
        default=0.01,
        ge=0.0,
        description=("Maximum allowed absolute alignment error (seconds) used " "for validation/QC."),
    )
    global_offset: float = Field(
        default=0.0,
        description=("Constant offset (seconds) added before alignment. " "Useful for known fixed delays."),
    )
    robust_min_matches: int = Field(
        default=3,
        ge=1,
        description=("Minimum number of anchor matches required before drift " "fitting for robust TTL alignment."),
    )
    robust_max_start_trial_search: int = Field(
        default=50,
        ge=1,
        description=("Maximum starting trial index to consider when bootstrapping " "robust TTL alignment."),
    )


class AssemblyConfig(BaseModel, extra="forbid"):
    """How ingested data streams are combined into unified datasets."""

    ttls: BaseAssembleConfig = Field(
        default_factory=BaseAssembleConfig,
        description="How TTL pulse data streams are assembled into NWB structures.",
    )
    behavior: BaseAssembleConfig = Field(
        default_factory=BaseAssembleConfig,
        description="How behavioral data streams are assembled into NWB structures.",
    )
    videos: BaseLinkConfig = Field(
        default_factory=BaseLinkConfig,
        description="How video data streams are assembled into NWB structures.",
    )
    pose: BaseAssembleConfig = Field(
        default_factory=BaseAssembleConfig,
        description="How pose estimation data streams are assembled into NWB structures.",
    )


class FinalizationConfig(BaseModel, extra="forbid"):
    """Final processing steps before output (NWB export, QC generation)."""

    qc_report: bool = Field(
        default=True,
        description="If True, generate a QC report after NWB creation.",
    )
    alignment_stats: bool = Field(
        default=True,
        description="If True, include alignment statistics in the NWB file.",
    )
    provenance: bool = Field(
        default=True,
        description="If True, include data provenance information in NWB.",
    )
    skip_validation: bool = Field(
        default=False,
        description="If True, skip NWB validation with nwbinspector.",
    )


# =============================================================================
# Configuration Models - Batch and Session Levels
# =============================================================================


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
