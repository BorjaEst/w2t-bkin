"""Immutable data models for session configuration and results."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pynwb import NWBFile

from w2t_bkin.config import SessionConfig


@dataclass
class SessionResult:
    success: bool
    subject_dir: str
    session_dir: str
    nwb_path: Optional[Path] = None
    validation: Optional[List[Dict[str, Any]]] = None
    artifacts: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass(frozen=True)
class SessionInfo:
    metadata: Dict[str, Any]  # Parsed metadata.toml content
    subject_dir: str  # Path to subject director
    session_dir: str  # Path to session directory
    processed_dir: Path  # Path to processed output directory
    interim_dir: Path  # Path to interim data directory
    raw_dir: Path  # Path to raw data directory
    models_dir: Path  # Path to pose models directory


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


# =============================================================================
# Pose Metadata Models (Pydantic for validation)
# =============================================================================


class SkeletonNode(BaseModel, extra="forbid"):
    """Single node in a pose skeleton."""

    name: str = Field(..., description="Body part name (must be unique within skeleton)")


class SkeletonEdge(BaseModel, extra="forbid"):
    """Edge connecting two nodes in a pose skeleton."""

    source: str = Field(..., description="Source node name")
    target: str = Field(..., description="Target node name")


class PoseSkeleton(BaseModel, extra="forbid"):
    """Skeleton definition for pose visualization.

    Attributes:
        id: Unique identifier for this skeleton
        name: Human-readable name
        description: Optional description
        nodes: List of body part nodes
        edges: Optional list of connections between nodes
    """

    id: str = Field(..., description="Unique skeleton identifier")
    name: str = Field(..., description="Human-readable skeleton name")
    description: Optional[str] = Field(None, description="Optional skeleton description")
    nodes: List[SkeletonNode] = Field(..., description="Body part nodes")
    edges: Optional[List[SkeletonEdge]] = Field(None, description="Optional edges between nodes")


class PoseMapping(BaseModel, extra="forbid"):
    """Body part name mapping for harmonization.

    Attributes:
        id: Unique identifier for this mapping
        description: Optional description
        map: Dictionary mapping source names to canonical names
    """

    id: str = Field(..., description="Unique mapping identifier")
    description: Optional[str] = Field(None, description="Optional mapping description")
    map: Dict[str, str] = Field(..., description="Source name → canonical name mapping")


class PoseCameraConfig(BaseModel, extra="forbid"):
    """Pose configuration for a specific camera.

    H5 files are discovered by stem-matching video files in interim/{dlc-pose|sleap-pose}/<camera_id>/

    Attributes:
        source: Pose estimation source (dlc or sleap)
        model_id: Model identifier for generate mode (references pose.models.<model_id>)
        mapping_id: Optional reference to pose mapping
        skeleton_id: Optional reference to skeleton definition
    """

    source: Literal["dlc", "sleap"] = Field(..., description="Pose estimation source")
    model_id: Optional[str] = Field(None, description="Model ID for generate mode (references pose.models.<id>)")
    mapping_id: Optional[str] = Field(None, description="Optional mapping ID for name harmonization")
    skeleton_id: Optional[str] = Field(None, description="Optional skeleton ID for visualization")


class PoseMetadata(BaseModel, extra="forbid"):
    """Complete pose metadata section from metadata.toml.

    Attributes:
        models: Pose estimation models (source + path)
        cameras: Pose configuration per camera (dict keyed by camera_id)
        mappings: Optional body part name mappings (dict keyed by mapping_id)
        skeletons: Optional skeleton definitions (dict keyed by skeleton_id)
    """

    models: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Pose models: {model_id: {source, path}}")
    cameras: Dict[str, PoseCameraConfig] = Field(default_factory=dict, description="Pose config per camera: {camera_id: config}")
    mappings: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="Optional mappings: {mapping_id: {src: dst}}")
    skeletons: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Optional skeletons: {skeleton_id: definition}")
