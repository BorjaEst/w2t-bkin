"""Ingest module for w2t-bkin pipeline.

Discovers session resources (videos, sync files, optional artifacts),
extracts video metadata using ffprobe, and builds a validated manifest.

Requirements: MR-1, MR-2, MR-3, MR-4, M-NFR-1, M-NFR-2
Design: ingest/design.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from w2t_bkin.config import Settings
from w2t_bkin.domain import Manifest, MissingInputError, VideoMetadata


def build_manifest(settings) -> Manifest:
    """Build session manifest by discovering and probing resources.

    Discovers five camera videos and associated sync files, extracts metadata
    using ffprobe without loading full videos, and builds a validated Manifest
    with absolute paths and provenance.

    Args:
        settings: Configuration settings (Settings object or compatible mock)

    Returns:
        Validated Manifest object with all discovered resources

    Raises:
        MissingInputError: When required files are missing or insufficient
        ValueError: When video metadata extraction fails

    Requirements:
        - MR-1: Discover five camera videos and associated sync files
        - MR-2: Extract per-video metadata and write manifest
        - MR-3: Fail with MissingInputError when required inputs missing
        - MR-4: Record optional artifacts when present
        - M-NFR-1: Avoid loading entire videos (use ffprobe)
        - M-NFR-2: Deterministic ordering and stable keys
    """
    # Extract session_root from settings
    session_root = _get_session_root(settings)

    # Verify session root exists
    if not session_root.exists():
        raise MissingInputError(f"Session root directory not found: {session_root.absolute()}")

    # Discover and validate videos (MR-1, MR-3)
    # Try direct attribute first (for test mocks), then nested video.pattern
    if hasattr(settings, "video_pattern"):
        video_pattern = settings.video_pattern
    elif hasattr(settings, "video") and hasattr(settings.video, "pattern"):
        video_pattern = settings.video.pattern
    else:
        video_pattern = "cam*.mp4"  # Default fallback

    video_files = _discover_files(session_root, video_pattern, required=True)

    if len(video_files) < 5:
        raise MissingInputError(f"Expected 5 camera videos but found {len(video_files)} " f"matching pattern '{video_pattern}' in {session_root.absolute()}")

    # Extract video metadata (MR-2, M-NFR-1)
    videos_metadata = []
    for video_path in video_files[:5]:  # Take exactly 5 cameras
        metadata = _extract_video_metadata(video_path)
        videos_metadata.append(metadata)

    # Sort by camera_id for deterministic ordering (M-NFR-2)
    videos_metadata.sort(key=lambda v: v.camera_id)

    # Discover sync files (MR-1, MR-3)
    # Handle both direct attributes (test mocks) and nested structures
    if hasattr(settings, "sync_pattern"):
        sync_pattern = settings.sync_pattern
    else:
        sync_pattern = "*.sync"  # Default

    if hasattr(settings, "sync_required"):
        sync_required = settings.sync_required
    else:
        sync_required = True  # Default: sync is required

    sync_files = _discover_files(session_root, sync_pattern, required=sync_required)

    if sync_required and len(sync_files) == 0:
        raise MissingInputError(f"No sync files found matching pattern '{sync_pattern}' " f"in {session_root.absolute()}")

    sync_entries = [{"path": path, "type": "ttl"} for path in sync_files]

    # Discover optional artifacts (MR-4)
    # Handle both direct attributes (test mocks) and nested structures
    events_pattern = getattr(settings, "events_pattern", None)
    events_entries = []
    if events_pattern:
        events_files = _discover_files(session_root, events_pattern, required=False)
        events_entries = [{"path": path, "kind": "ndjson"} for path in events_files]

    pose_pattern = getattr(settings, "pose_pattern", None)
    pose_entries = []
    if pose_pattern:
        pose_files = _discover_files(session_root, pose_pattern, required=False)
        pose_entries = [{"path": path, "format": "h5"} for path in pose_files]

    facemap_pattern = getattr(settings, "facemap_pattern", None)
    facemap_entries = []
    if facemap_pattern:
        facemap_files = _discover_files(session_root, facemap_pattern, required=False)
        facemap_entries = [{"path": path} for path in facemap_files]

    # Build config snapshot (Design - Provenance)
    config_snapshot = _build_config_snapshot(settings)

    # Build provenance metadata (Design - Provenance)
    provenance = _build_provenance()

    # Determine session_id (Design - Manifest structure)
    session_id = _get_session_id(settings, session_root)

    # Build and validate manifest
    manifest = Manifest(
        session_id=session_id,
        videos=videos_metadata,
        sync=sync_entries,
        events=events_entries,
        pose=pose_entries,
        facemap=facemap_entries,
        config_snapshot=config_snapshot,
        provenance=provenance,
    )

    return manifest


def _get_session_root(settings) -> Path:
    """Extract session root path from settings.

    Args:
        settings: Configuration settings (Settings object or mock)

    Returns:
        Absolute path to session root directory

    Raises:
        MissingInputError: When session_root cannot be determined
    """
    # Try multiple possible attributes (for test mocks and real Settings)
    if hasattr(settings, "session_root"):
        return Path(settings.session_root).absolute()

    if hasattr(settings, "paths") and settings.paths:
        if hasattr(settings.paths, "raw_root"):
            return Path(settings.paths.raw_root).absolute()

    raise MissingInputError("Cannot determine session_root from settings. " "Expected 'session_root' attribute or 'paths.raw_root'")


def _discover_files(root: Path, pattern: str, required: bool = False) -> list[Path]:
    """Discover files matching pattern in root directory.

    Args:
        root: Root directory to search
        pattern: Glob pattern for file discovery
        required: Whether to raise error if no files found

    Returns:
        List of absolute paths to discovered files, sorted for determinism

    Raises:
        MissingInputError: When required=True and no files found
    """
    files = sorted(root.glob(pattern))  # Sort for determinism (M-NFR-2)

    if required and len(files) == 0:
        raise MissingInputError(f"No files found matching pattern '{pattern}' in {root.absolute()}")

    # Ensure absolute paths (Design - absolute paths)
    return [f.absolute() for f in files]


def _extract_video_metadata(video_path: Path) -> VideoMetadata:
    """Extract video metadata using ffprobe without loading the video.

    Uses ffprobe to extract codec, fps, duration, and resolution efficiently
    without decoding video frames.

    Args:
        video_path: Absolute path to video file

    Returns:
        VideoMetadata with extracted information

    Raises:
        ValueError: When ffprobe fails or metadata cannot be parsed
        MissingInputError: When video file doesn't exist

    Requirements:
        - MR-2: Extract per-video metadata
        - M-NFR-1: Avoid loading entire videos
    """
    if not video_path.exists():
        raise MissingInputError(f"Video file not found: {video_path}")

    # Extract camera_id from filename (e.g., cam0.mp4 -> 0)
    camera_id = _extract_camera_id(video_path)

    # Run ffprobe to get video metadata as JSON (M-NFR-1)
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"ffprobe failed for {video_path}: {e.stderr}") from e
    except FileNotFoundError:
        raise ValueError("ffprobe not found. Please install ffmpeg/ffprobe.") from None
    except subprocess.TimeoutExpired:
        raise ValueError(f"ffprobe timed out for {video_path}") from None

    # Parse ffprobe JSON output
    try:
        probe_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse ffprobe output for {video_path}: {e}") from e

    # Extract video stream information
    video_stream = None
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError(f"No video stream found in {video_path}")

    # Extract metadata fields
    codec = video_stream.get("codec_name", "unknown")

    # Calculate FPS from frame rate ratio
    fps_str = video_stream.get("r_frame_rate", "30/1")
    fps = _parse_fps(fps_str)

    # Get duration (from format or stream)
    duration = float(probe_data.get("format", {}).get("duration", 0.0))
    if duration == 0.0:
        duration = float(video_stream.get("duration", 0.0))

    # Get resolution
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    resolution = (width, height)

    # Build VideoMetadata object
    return VideoMetadata(
        camera_id=camera_id,
        path=video_path.absolute(),
        codec=codec,
        fps=fps,
        duration=duration,
        resolution=resolution,
    )


def _extract_camera_id(video_path: Path) -> int:
    """Extract camera ID from video filename.

    Expects filename pattern like cam0.mp4, cam1.mp4, etc.

    Args:
        video_path: Path to video file

    Returns:
        Camera ID as integer

    Raises:
        ValueError: When camera ID cannot be extracted
    """
    filename = video_path.stem  # e.g., "cam0" from "cam0.mp4"

    # Try to extract numeric suffix
    import re

    match = re.search(r"(\d+)$", filename)

    if match:
        return int(match.group(1))

    # Fallback: look for any digits in filename
    match = re.search(r"(\d+)", filename)
    if match:
        return int(match.group(1))

    raise ValueError(f"Cannot extract camera_id from filename: {video_path.name}")


def _parse_fps(fps_str: str) -> float:
    """Parse FPS from ffprobe rational number format.

    Args:
        fps_str: FPS string in format "num/den" (e.g., "30/1", "30000/1001")

    Returns:
        FPS as float

    Raises:
        ValueError: When FPS string cannot be parsed
    """
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            return float(num) / float(den)
        else:
            return float(fps_str)
    except (ValueError, ZeroDivisionError) as e:
        raise ValueError(f"Cannot parse FPS from '{fps_str}': {e}") from e


def _build_config_snapshot(settings) -> dict[str, Any]:
    """Build configuration snapshot for provenance.

    Args:
        settings: Configuration settings (Settings object or mock)

    Returns:
        Dictionary representation of settings
    """
    # Try to use pydantic's model_dump if available
    if hasattr(settings, "model_dump"):
        return settings.model_dump(mode="json")
    elif hasattr(settings, "dict"):
        return settings.dict()
    else:
        # Fallback to minimal snapshot (for test mocks)
        return {"type": type(settings).__name__}


def _build_provenance() -> dict[str, Any]:
    """Build provenance metadata.

    Returns:
        Dictionary with timestamp and optional git commit hash
    """
    provenance = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": "ingest",
        "version": "1.0.0",
    }

    # Try to get git commit hash (optional)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        provenance["git_commit"] = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Git not available or not in a git repo - not critical
        pass

    return provenance


def _get_session_id(settings, session_root: Path) -> str:
    """Determine session ID from settings or directory name.

    Args:
        settings: Configuration settings (Settings object or mock)
        session_root: Session root directory path

    Returns:
        Session ID string
    """
    # Try to get from session config
    if hasattr(settings, "session") and settings.session:
        if hasattr(settings.session, "id"):
            return settings.session.id

    # Fallback to directory name
    return session_root.name


__all__ = [
    "build_manifest",
]
