"""Domain models for W2T-BKIN pipeline (Phase 0).

This module provides Pydantic-based domain models for the entire W2T-BKIN data processing
pipeline. All models are immutable (frozen) to ensure data integrity and support deterministic
hashing for provenance tracking.

Model Categories:
-----------------
1. **Configuration Models** (Phase 0):
   - Config: Top-level pipeline configuration
   - ProjectConfig, PathsConfig, TimebaseConfig, etc.: Configuration subsections
   - Loaded from config.toml files

2. **Session Models** (Phase 0):
   - Session: Session metadata and file patterns
   - SessionMetadata, Camera, TTL, BpodSession: Session components
   - Loaded from session.toml files

3. **Manifest Models** (Phase 1):
   - Manifest: Discovered files with optional frame/TTL counts
   - ManifestCamera, ManifestTTL: Manifest components
   - Built by ingest.build_manifest()

4. **Verification Models** (Phase 1):
   - VerificationResult, VerificationSummary: Frame/TTL verification results
   - CameraVerificationResult: Per-camera verification details

5. **Alignment Models** (Phase 2):
   - AlignmentStats: Timebase alignment statistics and jitter metrics
   - Provenance: Config/session hashes for reproducibility

6. **Behavioral Models** (Phase 3):
   - TrialData, BehavioralEvent, BpodSummary: Bpod behavioral data

7. **Optional Modality Models** (Phase 3):
   - PoseBundle, PoseFrame, PoseKeypoint: Pose estimation (DLC/SLEAP)
   - FacemapBundle, FacemapROI, FacemapSignal: Facemap motion energy
   - TranscodedVideo, TranscodeOptions: Video transcoding metadata

Key Features:
-------------
- **Immutability**: All models use `frozen=True` to prevent accidental modification
- **Strict Schemas**: All models use `extra="forbid"` to reject unknown fields
- **Type Safety**: Full type annotations with runtime validation
- **Deterministic Hashing**: Frozen models support stable hash computation
- **Validation**: Custom validators for cross-field validation (e.g., FacemapBundle)

Design Principles:
------------------
1. **Single Responsibility**: Each model represents one concept
2. **Composition over Inheritance**: Models compose other models (no inheritance)
3. **Explicit over Implicit**: All fields and constraints are explicit
4. **Fail Fast**: Invalid data raises exceptions at model creation time
5. **Read-Only by Default**: Immutability prevents bugs and enables caching

Usage Patterns:
---------------
1. **Loading from files**: Use config.py and session loaders
2. **Creating programmatically**: Instantiate with keyword arguments
3. **Validation**: Pydantic validates on creation, raises ValidationError
4. **Serialization**: Use .model_dump() for dict, .model_dump_json() for JSON
5. **Hashing**: Use utils.stable_hash() for deterministic provenance

Common Gotchas:
---------------
- Models are frozen - use .model_copy(update={...}) to create modified copies
- Optional[int] fields in ManifestCamera: None = not counted, int >= 0 = counted
- All paths in manifest models are absolute (converted during build_manifest)
- Validation errors provide detailed context - read the full traceback

Requirements: FR-12 (Domain models), NFR-7 (Immutability)
Acceptance: A18 (Supports deterministic hashing for provenance)

See Also:
---------
- config.py: Configuration and session loaders
- ingest.py: Manifest building and verification
- utils.py: Hashing and serialization utilities
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
    """Camera entry in manifest.

    Note: frame_count and ttl_pulse_count are Optional[int]:
    - None = not counted yet (fast discovery mode)
    - int >= 0 = counted value
    """

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str
    ttl_id: str
    video_files: List[str]
    frame_count: Optional[int] = None  # None = not counted yet
    ttl_pulse_count: Optional[int] = None  # None = not counted yet


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


if __name__ == "__main__":
    """Simplified usage examples for domain models.

    Run with: python -m w2t_bkin.domain
    """
    from datetime import datetime

    print("W2T-BKIN Domain Models - Quick Start Examples")
    print("=" * 60)

    # Example 1: Session Model
    print("\n1. Creating a Session with cameras and TTLs:")
    session = Session(
        session=SessionMetadata(
            id="Session-000001",
            subject_id="Mouse-123",
            date="2025-01-15",
            experimenter="Dr. Smith",
            description="Behavioral training",
            sex="M",
            age="P60",
            genotype="WT",
        ),
        bpod=BpodSession(path="Bpod/*.mat", order="name_asc"),
        TTLs=[TTL(id="ttl_camera", description="Camera sync", paths="TTLs/*.txt")],
        cameras=[
            Camera(
                id="cam0",
                description="Top view",
                paths="Video/top/*.avi",
                order="name_asc",
                ttl_id="ttl_camera",
            )
        ],
    )
    print(f"   ✓ Session: {session.session.id}")
    print(f"   ✓ Cameras: {len(session.cameras)}, TTLs: {len(session.TTLs)}")

    # Example 2: Manifest with Optional Counts
    print("\n2. Creating a Manifest (with and without counts):")
    manifest = Manifest(
        session_id="Session-000001",
        cameras=[
            ManifestCamera(
                camera_id="cam0",
                ttl_id="ttl_camera",
                video_files=["video.avi"],
                frame_count=8580,  # Counted
                ttl_pulse_count=8580,  # Counted
            )
        ],
    )
    print(f"   ✓ Manifest: {manifest.session_id}")
    print(f"   ✓ Camera frames: {manifest.cameras[0].frame_count}")
    print(f"   ✓ Sync status: {'PERFECT' if manifest.cameras[0].frame_count == manifest.cameras[0].ttl_pulse_count else 'MISMATCH'}")

    # Fast discovery (no counts)
    manifest_fast = Manifest(
        session_id="Session-000002",
        cameras=[
            ManifestCamera(
                camera_id="cam0",
                ttl_id="ttl_camera",
                video_files=["video.avi"],
                frame_count=None,  # Not counted yet
                ttl_pulse_count=None,
            )
        ],
    )
    print(f"   ✓ Fast manifest: {manifest_fast.cameras[0].frame_count} (None = not counted)")

    # Example 3: Model Features
    print("\n3. Key Model Features:")

    # Immutability
    try:
        session.session.id = "Modified"
    except Exception:
        print("   ✓ Immutable: Cannot modify frozen models")

    # Serialization
    session_dict = session.model_dump()
    session_json = session.model_dump_json()
    print(f"   ✓ Serialization: dict keys = {list(session_dict.keys())}")

    # Validation
    try:
        invalid = Camera(
            id="cam0",
            description="Test",
            paths="*.avi",
            order="name_asc",
            ttl_id="ttl",
            extra_field="forbidden",
        )
    except Exception:
        print("   ✓ Validation: Extra fields rejected")

    print("\n" + "=" * 60)
    print("✓ Examples completed!")
    print("\nProduction usage:")
    print("  from w2t_bkin.config import load_config, load_session")
    print("  from w2t_bkin.ingest import build_manifest")
    print("\nSee module docstring for complete model reference.")
