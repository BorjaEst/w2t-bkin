"""Domain models for W2T-BKIN pipeline (Phase 0).

Pydantic models for configuration, session metadata, and pipeline artifacts.
All models are immutable (frozen) to ensure data integrity.

Requirements: FR-12, NFR-7
Acceptance: A18 (supports deterministic hashing)
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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
    """Timebase configuration for session reference clock."""

    model_config = {"frozen": True, "extra": "forbid"}

    source: str  # Will be validated as enum
    mapping: str  # Will be validated as enum
    jitter_budget_s: float
    offset_s: float
    ttl_id: Optional[str] = None
    neuropixels_stream: Optional[str] = None


class AcquisitionConfig(BaseModel):
    """Acquisition policies."""

    model_config = {"frozen": True, "extra": "forbid"}

    concat_strategy: str


class VerificationConfig(BaseModel):
    """Verification policies for frame/TTL matching."""

    model_config = {"frozen": True, "extra": "forbid"}

    mismatch_tolerance_frames: int
    warn_on_mismatch: bool


class BpodConfig(BaseModel):
    """Bpod parsing configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    parse: bool


class TranscodeConfig(BaseModel):
    """Video transcoding configuration."""

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
    """NWB export configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    link_external_video: bool
    lab: str
    institution: str
    file_name_template: str
    session_description_template: str


class QCConfig(BaseModel):
    """QC report configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    generate_report: bool
    out_template: str
    include_verification: bool


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    level: str
    structured: bool


class DLCConfig(BaseModel):
    """DeepLabCut configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str


class SLEAPConfig(BaseModel):
    """SLEAP configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    model: str


class LabelsConfig(BaseModel):
    """Pose estimation labels configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    dlc: DLCConfig
    sleap: SLEAPConfig


class FacemapConfig(BaseModel):
    """Facemap configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool
    ROIs: List[str]


class Config(BaseModel):
    """Top-level configuration model (strict schema)."""

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


# Session models


class SessionMetadata(BaseModel):
    """Session metadata."""

    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    subject_id: str
    date: str
    experimenter: str
    description: str
    sex: str
    age: str
    genotype: str


class BpodSession(BaseModel):
    """Bpod file configuration for session."""

    model_config = {"frozen": True, "extra": "forbid"}

    path: str
    order: str


class TTL(BaseModel):
    """TTL configuration (immutable)."""

    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    description: str
    paths: str


class Camera(BaseModel):
    """Camera configuration (immutable)."""

    model_config = {"frozen": True, "extra": "forbid"}

    id: str
    description: str
    paths: str
    order: str
    ttl_id: str


class Session(BaseModel):
    """Session configuration model (strict schema)."""

    model_config = {"frozen": True, "extra": "forbid"}

    session: SessionMetadata
    bpod: BpodSession
    TTLs: List[TTL]
    cameras: List[Camera]


# Artifact models (Phase 1 enhanced)


class ManifestCamera(BaseModel):
    """Camera entry in manifest."""

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    ttl_id: str
    video_files: List[str]
    frame_count: int = 0
    ttl_pulse_count: int = 0


class ManifestTTL(BaseModel):
    """TTL entry in manifest."""

    model_config = {"frozen": True, "extra": "forbid"}

    ttl_id: str
    files: List[str]


class Manifest(BaseModel):
    """Manifest tracking discovered files."""

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    cameras: List[ManifestCamera] = Field(default_factory=list)
    ttls: List[ManifestTTL] = Field(default_factory=list)
    bpod_files: Optional[List[str]] = None


class CameraVerificationResult(BaseModel):
    """Verification result for a single camera."""

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    ttl_id: str
    frame_count: int
    ttl_pulse_count: int
    mismatch: int
    verifiable: bool
    status: str


class VerificationSummary(BaseModel):
    """Verification summary for frame/TTL counts."""

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    cameras: List[CameraVerificationResult]
    generated_at: str


class VerificationResult(BaseModel):
    """Result of manifest verification."""

    model_config = {"frozen": True, "extra": "forbid"}

    status: str
    camera_results: List[CameraVerificationResult] = Field(default_factory=list)


class Provenance(BaseModel):
    """Provenance metadata."""

    model_config = {"frozen": True, "extra": "forbid"}

    config_hash: str
    session_hash: str


class AlignmentStats(BaseModel):
    """Alignment statistics for timebase (Phase 2)."""

    model_config = {"frozen": True, "extra": "forbid"}

    timebase_source: str
    mapping: str
    offset_s: float
    max_jitter_s: float
    p95_jitter_s: float
    aligned_samples: int


# Bpod/Events models (Phase 3)


class TrialData(BaseModel):
    """Trial data extracted from Bpod."""

    model_config = {"frozen": True, "extra": "forbid"}

    trial_number: int
    start_time: float
    stop_time: float
    outcome: str


class BehavioralEvent(BaseModel):
    """Behavioral event extracted from Bpod."""

    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str
    timestamp: float
    trial_number: int


class BpodSummary(BaseModel):
    """Bpod summary for QC report."""

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    total_trials: int
    outcome_counts: dict
    event_categories: List[str]
    bpod_files: List[str]
    generated_at: str


# Phase 3: Optional modalities (pose, facemap, transcode)


class PoseKeypoint(BaseModel):
    """Single keypoint in pose estimation."""

    model_config = {"frozen": True, "extra": "forbid"}

    name: str
    x: float
    y: float
    confidence: float


class PoseFrame(BaseModel):
    """Pose data for a single frame."""

    model_config = {"frozen": True, "extra": "forbid"}

    frame_index: int
    timestamp: float  # Aligned timestamp
    keypoints: List[PoseKeypoint]
    source: str  # "dlc" or "sleap"


class PoseBundle(BaseModel):
    """Harmonized pose data bundle aligned to reference timebase."""

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    camera_id: str
    model_name: str
    skeleton: str  # Canonical skeleton name
    frames: List[PoseFrame]
    alignment_method: str  # "nearest" or "linear"
    mean_confidence: float
    generated_at: str


class FacemapROI(BaseModel):
    """Region of interest for Facemap analysis."""

    model_config = {"frozen": True, "extra": "forbid"}

    name: str
    x: int
    y: int
    width: int
    height: int


class FacemapSignal(BaseModel):
    """Time series signal from Facemap ROI."""

    model_config = {"frozen": True, "extra": "forbid"}

    roi_name: str
    timestamps: List[float]  # Aligned timestamps
    values: List[float]
    sampling_rate: float


class FacemapBundle(BaseModel):
    """Facemap data bundle aligned to reference timebase."""

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    camera_id: str
    rois: List[FacemapROI]
    signals: List[FacemapSignal]
    alignment_method: str  # "nearest" or "linear"
    generated_at: str

    @model_validator(mode="after")
    def validate_signals_match_rois(self) -> "FacemapBundle":
        """Validate that all signals reference defined ROIs."""
        roi_names = {roi.name for roi in self.rois}
        for signal in self.signals:
            if signal.roi_name not in roi_names:
                raise ValueError(f"Signal references undefined ROI: {signal.roi_name}. " f"Defined ROIs: {roi_names}")
        return self


class TranscodeOptions(BaseModel):
    """Transcoding configuration options."""

    model_config = {"frozen": True, "extra": "forbid"}

    codec: str
    crf: int
    preset: str
    keyint: int


class TranscodedVideo(BaseModel):
    """Metadata for a transcoded video file."""

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    original_path: Path
    output_path: Path  # Transcoded file path
    codec: str
    checksum: str  # Content-addressed hash
    frame_count: int
