"""Domain models for W2T-BKIN pipeline.

This package provides Pydantic-based domain models for the entire W2T-BKIN
data processing pipeline. Models are organized by responsibility and pipeline
phase, but all are re-exported here for compatibility.

Package Structure:
-----------------
- exceptions: Exception hierarchy (W2TError and subclasses)
- config: Configuration models (Config, ProjectConfig, TimebaseConfig, etc.)
- session: Session models (Session, Camera, TTL, SessionMetadata, etc.)
- manifest: Manifest and verification models (Manifest, VerificationSummary, etc.)
- alignment: Alignment and provenance models (AlignmentStats, Provenance)
- bpod: Behavioral events models (TrialData, BehavioralEvent, BpodSummary)
- pose: Pose estimation models (PoseBundle, PoseFrame, PoseKeypoint)
- facemap: Facemap models (FacemapBundle, FacemapROI, FacemapSignal)
- transcode: Transcoding models (TranscodeOptions, TranscodedVideo)

Design Principles:
------------------
1. **Single Responsibility**: Each module represents one domain concept
2. **Immutability**: All models use frozen=True
3. **Strict Validation**: All models use extra="forbid"
4. **Type Safety**: Full type annotations with runtime validation
5. **Composition**: Models compose other models (no inheritance)

Key Features:
-------------
- **Phase Alignment**: Models organized by pipeline phase
- **Deterministic Hashing**: Frozen models support stable hashing
- **Fail Fast**: Invalid data raises exceptions at creation time

Import Patterns:
---------------
# Direct module imports
from w2t_bkin.domain.config import Config, TimebaseConfig
from w2t_bkin.domain.session import Session, Camera
from w2t_bkin.domain.exceptions import W2TError, ConfigError

# Package root imports
from w2t_bkin.domain import Config, Session, W2TError

Requirements:
-------------
- FR-12: Domain models for type-safe data contracts
- NFR-7: Immutability for data integrity

Acceptance Criteria:
-------------------
- A18: Supports deterministic hashing for provenance

Example:
--------
>>> from w2t_bkin.domain import Session, Camera, Config
>>> from w2t_bkin.domain.exceptions import ConfigError
>>>
>>> # Create models
>>> session = Session(...)
>>> config = Config(...)
>>>
>>> # Serialize
>>> session_json = session.model_dump_json()
>>>
>>> # Handle errors
>>> try:
...     invalid_config = Config(...)
... except ConfigError as e:
...     print(f"Configuration error: {e.message}")
"""

# Alignment and provenance models (Phase 2)
from w2t_bkin.domain.alignment import AlignmentStats, Provenance

# Behavioral events models (Phase 3 - Optional)
from w2t_bkin.domain.bpod import BehavioralEvent, BpodSummary, TrialData

# Configuration models (Phase 0)
from w2t_bkin.domain.config import (
    AcquisitionConfig,
    BpodConfig,
    Config,
    DLCConfig,
    FacemapConfig,
    LabelsConfig,
    LoggingConfig,
    NWBConfig,
    PathsConfig,
    ProjectConfig,
    QCConfig,
    SLEAPConfig,
    TimebaseConfig,
    TranscodeConfig,
    VerificationConfig,
    VideoConfig,
)

# Exception hierarchy
from w2t_bkin.domain.exceptions import (
    AlignmentError,
    BpodParseError,
    CameraUnverifiableError,
    ConfigError,
    ConfigExtraKeyError,
    ConfigMissingKeyError,
    ConfigValidationError,
    EventsError,
    ExternalToolError,
    FacemapError,
    FileNotFoundError,
    IngestError,
    JitterExceedsBudgetError,
    MismatchExceedsToleranceError,
    NWBError,
    PoseError,
    QCError,
    SessionError,
    SessionExtraKeyError,
    SessionMissingKeyError,
    SessionValidationError,
    SyncError,
    TimebaseProviderError,
    TranscodeError,
    ValidationError,
    VerificationError,
    W2TError,
)

# Facemap models (Phase 3 - Optional)
from w2t_bkin.domain.facemap import FacemapBundle, FacemapROI, FacemapSignal

# Manifest and verification models (Phase 1)
from w2t_bkin.domain.manifest import (
    CameraVerificationResult,
    Manifest,
    ManifestCamera,
    ManifestTTL,
    VerificationResult,
    VerificationSummary,
)

# Pose estimation models (Phase 3 - Optional)
from w2t_bkin.domain.pose import PoseBundle, PoseFrame, PoseKeypoint

# Session models (Phase 0)
from w2t_bkin.domain.session import TTL, BpodSession, Camera, Session, SessionMetadata

# Transcoding models (Phase 3 - Optional)
from w2t_bkin.domain.transcode import TranscodedVideo, TranscodeOptions

# Public API (alphabetically ordered within categories)
__all__ = [
    # Exceptions
    "W2TError",
    "ConfigError",
    "ConfigMissingKeyError",
    "ConfigExtraKeyError",
    "ConfigValidationError",
    "SessionError",
    "SessionMissingKeyError",
    "SessionExtraKeyError",
    "SessionValidationError",
    "IngestError",
    "FileNotFoundError",
    "VerificationError",
    "MismatchExceedsToleranceError",
    "CameraUnverifiableError",
    "SyncError",
    "TimebaseProviderError",
    "JitterExceedsBudgetError",
    "AlignmentError",
    "EventsError",
    "BpodParseError",
    "TranscodeError",
    "PoseError",
    "FacemapError",
    "NWBError",
    "ExternalToolError",
    "ValidationError",
    "QCError",
    # Configuration models
    "Config",
    "ProjectConfig",
    "PathsConfig",
    "TimebaseConfig",
    "AcquisitionConfig",
    "VerificationConfig",
    "BpodConfig",
    "TranscodeConfig",
    "VideoConfig",
    "NWBConfig",
    "QCConfig",
    "LoggingConfig",
    "DLCConfig",
    "SLEAPConfig",
    "LabelsConfig",
    "FacemapConfig",
    # Session models
    "Session",
    "SessionMetadata",
    "BpodSession",
    "TTL",
    "Camera",
    # Manifest models
    "Manifest",
    "ManifestCamera",
    "ManifestTTL",
    "CameraVerificationResult",
    "VerificationSummary",
    "VerificationResult",
    # Alignment models
    "AlignmentStats",
    "Provenance",
    # Bpod models
    "TrialData",
    "BehavioralEvent",
    "BpodSummary",
    # Pose models
    "PoseBundle",
    "PoseFrame",
    "PoseKeypoint",
    # Facemap models
    "FacemapBundle",
    "FacemapROI",
    "FacemapSignal",
    # Transcode models
    "TranscodeOptions",
    "TranscodedVideo",
]
