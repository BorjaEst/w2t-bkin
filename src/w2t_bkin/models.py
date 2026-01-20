"""Immutable data models for session configuration and results."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pynwb import NWBFile

from w2t_bkin.config import SessionConfig
from w2t_bkin.metadata import BpodSyncTrialTypeMeta, Metadata
from w2t_bkin.utils import convert_matlab_struct


@dataclass
class SessionResult:
    """Result of a session processing flow.

    Attributes:
        success: Whether processing succeeded
        subject_id: Subject identifier
        session_id: Session identifier
        nwb_path: Path to generated NWB file (if successful)
        validation: Validation results
        artifacts: Generated artifacts metadata
        error: Error message (if failed)
        duration_seconds: Processing duration
    """

    success: bool
    subject_id: str
    session_id: str
    nwb_path: Optional[Path] = None
    validation: Optional[List[Dict[str, Any]]] = None
    artifacts: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass(frozen=True)
class SessionInfo:
    """Immutable session configuration and paths.

    Attributes:
        subject_id: Subject identifier (e.g., 'subject-001')
        session_id: Session identifier (e.g., 'session-001')
        metadata: Parsed and merged metadata from TOML files
        raw_dir: Path to raw session directory ($W2T_RAW_ROOT/<subject>/<session>)
        interim_dir: Path to interim data directory ($W2T_INTERMEDIATE_ROOT/<subject>/<session>)
        processed_dir: Path to processed output directory ($W2T_OUTPUT_ROOT/<subject>/<session>)
        models_dir: Path to pose models directory ($W2T_MODELS_ROOT)
    """

    subject_id: str  # Subject identifier
    session_id: str  # Session identifier
    metadata: Metadata  # Parsed + validated merged metadata
    raw_dir: Path  # Path to raw session directory
    interim_dir: Path  # Path to interim data directory
    processed_dir: Path  # Path to processed output directory
    models_dir: Path  # Path to pose models directory


@dataclass
class DiscoveryResult:
    camera_files: Dict[str, List[Path]]
    bpod_files: Dict[str, List[Path]]
    ttl_files: Dict[str, List[Path]]
    pose_files: Dict[str, List[Path]]
    models_files: Dict[str, Path]


@dataclass
class ArtifactsResult:
    """Resolved intermediate artifacts for a session.

    This is primarily used to pass pose artifact file paths (DLC/SLEAP outputs)
    from Phase 2 (artifacts) into Phase 3 (ingestion).

    Notes:
        - Prefect can persist dataclass results via pickling; Path objects are OK.
        - Downstream code should key by camera_id.
    """

    pose_h5_by_camera: Dict[str, List[Path]]
    pose_csv_by_camera: Dict[str, List[Path]]
    status_by_camera: Dict[str, Dict[str, Any]]


@dataclass
class TTLData:
    """Ingested TTL pulse data for a single channel.

    Attributes:
        channel_id: TTL channel identifier (e.g., 'ttl_camera')
        timestamps: Sorted list of pulse timestamps in seconds
        source_files: Paths to files that contributed pulses
    """

    channel_id: str
    timestamps: List[float]
    source_files: List[Path]

    @property
    def pulse_count(self) -> int:
        """Total number of pulses."""
        return len(self.timestamps)


@dataclass
class VideoChunk:
    """Single video file metadata.

    Attributes:
        path: Path to video file
        frame_count: Number of frames in this video
    """

    path: Path
    frame_count: int


@dataclass
class VideoData:
    """Ingested video metadata for a single camera.

    Attributes:
        camera_id: Camera identifier (e.g., 'camera_0')
        videos: List of video chunks (multiple files per camera supported)
        fps: Nominal frames per second (may be None if only TTL sync)
        ttl_id: TTL channel used for frame sync (optional)
    """

    camera_id: str
    videos: List[VideoChunk]
    fps: Optional[float] = None
    ttl_id: Optional[str] = None

    @property
    def total_frames(self) -> int:
        """Total frame count across all video chunks."""
        return sum(v.frame_count for v in self.videos)

    @property
    def frame_counts(self) -> List[int]:
        """Per-file frame counts (for NWB ImageSeries.starting_frame)."""
        return [v.frame_count for v in self.videos]

    @property
    def video_paths(self) -> List[Path]:
        """Paths to all video files."""
        return [v.path for v in self.videos]


@dataclass
class BpodData:
    """Ingested Bpod behavioral data.

    Attributes:
        data: Parsed Bpod data dictionary (from parse_bpod)
        source_files: Paths to .mat files that were merged
        sync_trial_types: Trial type sync configuration from metadata (for TTL alignment)
    """

    data: Dict[str, Any]
    source_files: List[Path]
    sync_trial_types: List[BpodSyncTrialTypeMeta] = None  # Default to None for backward compatibility

    def __post_init__(self):
        """Initialize sync_trial_types to empty list if None."""
        if self.sync_trial_types is None:
            self.sync_trial_types = []

    @property
    def n_trials(self) -> int:
        """Number of trials in the session."""
        session_data = convert_matlab_struct(self.data.get("SessionData", {}))
        return int(session_data.get("nTrials", 0))


@dataclass
class PoseData:
    """Ingested pose estimation data for one camera/video.

    Attributes:
        camera_id: Camera identifier
        video_path: Path to video file this pose data corresponds to
        pose_path: Path to pose estimation file (H5 or CSV)
        frames: List of frame dicts with keypoints (from import_dlc_pose/import_sleap_pose)
        metadata: PoseMetadata object with scorer, source_software, etc.
    """

    camera_id: str
    video_path: Path
    pose_path: Path
    frames: List[Dict[str, Any]]
    metadata: Any  # PoseMetadata from ingest.pose
