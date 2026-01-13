"""Immutable data models for session configuration and results."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pynwb import NWBFile

from w2t_bkin.config import SessionFlowConfig


@dataclass(frozen=True)
class SessionInfo:
    """Immutable configuration for a session processing run.

    This replaces the mutable PipelineContext. All configuration is loaded
    once and never modified during pipeline execution.

    Attributes:
        subject_id: Subject identifier
        session_id: Session identifier
        session_config: Pipeline configuration from configuration.toml
        metadata: Session metadata from TOML files
        session_dir: Path to raw data in session directory
        interim_dir: Path to intermediate session artifacts directory
        output_dir: Path to output session NWB directory
        models_root: Path to pose estimation models directory (from env)
    """

    subject_id: str
    session_id: str
    config: SessionFlowConfig
    metadata: Dict[str, Any]
    session_dir: Path
    interim_dir: Path
    output_dir: Path
    models_root: Path


@dataclass(frozen=True)
class DLCArtifact:
    """Result of DLC pose estimation for one video.

    Attributes:
        path: Path to generated H5 file
        camera_id: Camera identifier
        model_name: DLC model name
        generated_at: Timestamp of generation
        cached: Whether this was loaded from cache
    """

    path: Path
    camera_id: str
    model_name: str
    generated_at: datetime
    cached: bool = False


@dataclass(frozen=True)
class SLEAPArtifact:
    """Result of SLEAP pose estimation for one video.

    Attributes:
        path: Path to generated SLEAP file
        camera_id: Camera identifier
        model_name: SLEAP model name
        generated_at: Timestamp of generation
        cached: Whether this was loaded from cache
    """

    path: Path
    camera_id: str
    model_name: str
    generated_at: datetime
    cached: bool = False


@dataclass
class DiscoveryResult:
    """Result of file discovery phase.

    Attributes:
        camera_files: Video files per camera
        bpod_files: Bpod data files
        ttl_files: TTL channel files
    """

    camera_files: Dict[str, List[Path]]
    bpod_files: Dict[str, List[Path]]
    ttl_files: Dict[str, List[Path]]


@dataclass
class BpodData:
    """Parsed Bpod behavioral data.

    Attributes:
        data: Complete Bpod data structure
        n_trials: Number of trials extracted
    """

    data: Dict[str, Any]
    n_trials: int


@dataclass
class PoseData:
    """Pose estimation data for one video.

    Attributes:
        video_path: Path to video file
        frames: Pose coordinates per frame
        metadata: Pose model metadata (bodyparts, scorer, etc.)
    """

    video_path: Path
    frames: Any  # numpy array or similar
    metadata: Dict[str, Any]


@dataclass
class TTLData:
    """TTL pulse timestamps.

    Attributes:
        ttl_id: TTL channel identifier
        timestamps: Pulse timestamps in seconds
    """

    ttl_id: str
    timestamps: List[float]


@dataclass
class TrialAlignment:
    """Trial alignment result.

    Attributes:
        trial_offsets: Mapping from trial number to offset time (seconds)
        warnings: Alignment warnings
    """

    trial_offsets: Dict[int, float]
    warnings: List[str]


@dataclass
class SessionResult:
    """Final result of session processing.

    Attributes:
        success: Whether processing completed successfully
        subject_id: Subject identifier
        session_id: Session identifier
        nwb_path: Path to written NWB file
        validation: NWB validation results
        artifacts: Generated artifacts (DLC, SLEAP, etc.)
        error: Error message if failed
        duration_seconds: Total processing time
    """

    success: bool
    subject_id: str
    session_id: str
    nwb_path: Optional[Path] = None
    validation: Optional[List[Dict[str, Any]]] = None
    artifacts: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
