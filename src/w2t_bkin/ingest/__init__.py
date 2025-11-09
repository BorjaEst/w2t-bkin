"""Ingest module for W2T BKin pipeline.

Discover session assets, extract video metadata, and build manifest.
As a Layer 2 module, may import: config, domain, utils.

Requirements: FR-1 (Ingest five camera videos), NFR-8 (Data integrity)
Design: design.md §2 (Module Breakdown), §3.1 (Manifest), §21.1 (Layer 2)
API: api.md §3.4
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
from typing import Any

from w2t_bkin.config import Settings
from w2t_bkin.domain import Manifest, VideoMetadata
from w2t_bkin.utils import file_hash, get_commit, write_json

__all__ = [
    "build_manifest",
    "extract_video_metadata",
    "discover_videos",
    "discover_sync_files",
    "discover_events",
    "discover_pose",
    "discover_facemap",
]

logger = logging.getLogger(__name__)


# ============================================================================
# Main API (FR-1, API §3.4)
# ============================================================================


def build_manifest(
    session_dir: Path | str,
    settings: Settings,
    output_dir: Path | str | None = None,
) -> Path:
    """Build manifest from session directory and configuration.

    Args:
        session_dir: Path to session directory containing raw files
        settings: Validated settings object
        output_dir: Optional output directory (default: session_dir)

    Returns:
        Path to created manifest.json

    Raises:
        FileNotFoundError: If session_dir doesn't exist
        ValueError: If required files are missing

    Requirements: FR-1 (Ingest assets), NFR-1 (Reproducibility), NFR-8 (Data integrity)
    Design: §3.1 (Manifest JSON), API §3.4
    """
    session_dir = Path(session_dir).resolve()
    output_dir = Path(output_dir or session_dir).resolve()

    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    logger.info(f"Building manifest for session: {session_dir}")

    # Discover all assets
    videos = discover_videos(session_dir, settings)
    sync_files = discover_sync_files(session_dir, settings)
    events = discover_events(session_dir, settings)
    pose_files = discover_pose(session_dir, settings)
    facemap_files = discover_facemap(session_dir, settings)

    # Validate minimum requirements
    if not videos:
        raise ValueError(f"No videos found matching pattern '{settings.video.pattern}' in {session_dir}")

    if not sync_files:
        raise ValueError(f"No sync files found in {session_dir}")

    # Extract video metadata
    video_metadata_list = []
    for camera_id, video_path in enumerate(sorted(videos)):
        try:
            metadata = extract_video_metadata(video_path, camera_id)
            video_metadata_list.append(metadata)
        except Exception as e:
            logger.error(f"Failed to extract metadata from {video_path}: {e}")
            raise

    logger.info(f"Discovered {len(video_metadata_list)} videos")

    # Build config snapshot (convert to JSON-serializable format)
    config_snapshot = settings.model_dump(mode="json")

    # Build provenance
    provenance = {
        "git_commit": get_commit(),
        "session_dir": str(session_dir),
        "output_dir": str(output_dir),
    }

    # Determine session_id
    session_id = settings.session.id or session_dir.name

    # Create manifest
    manifest = Manifest(
        session_id=session_id,
        videos=video_metadata_list,
        sync=sync_files,
        events=events,
        pose=pose_files,
        facemap=facemap_files,
        config_snapshot=config_snapshot,
        provenance=provenance,
    )

    # Write manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    manifest_dict = _manifest_to_dict(manifest)
    write_json(manifest_path, manifest_dict)

    logger.info(f"Manifest written to: {manifest_path}")

    return manifest_path


# ============================================================================
# Video Discovery & Metadata (FR-1, Design §3.1)
# ============================================================================


def discover_videos(session_dir: Path, settings: Settings) -> list[Path]:
    """Discover video files in session directory.

    Args:
        session_dir: Session directory to search
        settings: Settings with video.pattern

    Returns:
        Sorted list of absolute video paths

    Requirements: FR-1 (Ingest five camera videos)
    """
    session_dir = Path(session_dir)
    pattern = settings.video.pattern

    videos = sorted(session_dir.glob(pattern))

    logger.info(f"Found {len(videos)} videos matching '{pattern}'")

    return videos


def extract_video_metadata(
    video_path: Path | str,
    camera_id: int,
) -> VideoMetadata:
    """Extract metadata from video file using ffprobe.

    Args:
        video_path: Path to video file
        camera_id: Camera identifier

    Returns:
        VideoMetadata object

    Raises:
        FileNotFoundError: If video doesn't exist
        RuntimeError: If ffprobe fails

    Requirements: FR-1 (Extract video metadata), NFR-8 (Data integrity)
    Design: §3.1 (VideoMetadata contract)
    """
    video_path = Path(video_path).resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Run ffprobe to extract metadata
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,r_frame_rate,duration,width,height",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        probe_data = json.loads(result.stdout)

        if not probe_data.get("streams"):
            raise RuntimeError(f"No video stream found in {video_path}")

        stream = probe_data["streams"][0]

        # Parse frame rate (e.g., "30/1" -> 30.0)
        fps_str = stream.get("r_frame_rate", "30/1")
        num, den = map(int, fps_str.split("/"))
        fps = num / den if den != 0 else 30.0

        # Parse duration
        duration = float(stream.get("duration", 0.0))

        # Parse resolution
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))

        # Get codec
        codec = stream.get("codec_name", "unknown")

        return VideoMetadata(
            camera_id=camera_id,
            path=video_path,
            codec=codec,
            fps=fps,
            duration=duration,
            resolution=(width, height),
        )

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed for {video_path}: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ffprobe timeout for {video_path}") from e
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to parse ffprobe output for {video_path}: {e}") from e


# ============================================================================
# Sync Discovery (FR-2, Design §3.1)
# ============================================================================


def discover_sync_files(session_dir: Path, settings: Settings) -> list[dict[str, Any]]:
    """Discover synchronization files.

    Args:
        session_dir: Session directory to search
        settings: Settings with sync configuration

    Returns:
        List of sync file descriptors with path and type

    Requirements: FR-2 (Sync inputs discovery)
    """
    session_dir = Path(session_dir)
    sync_descriptors = []

    # Discover from configured TTL channels
    for channel in settings.sync.ttl_channels:
        if channel.path:
            sync_path = session_dir / channel.path
            if sync_path.exists():
                sync_descriptors.append(
                    {
                        "path": str(sync_path.resolve()),
                        "type": "ttl",
                        "name": channel.name,
                        "polarity": channel.polarity,
                    }
                )

    # Fallback: discover common sync file patterns
    if not sync_descriptors:
        common_patterns = ["**/sync*.bin", "**/sync*.csv", "**/ttl*.bin"]
        for pattern in common_patterns:
            for sync_path in session_dir.glob(pattern):
                sync_descriptors.append(
                    {
                        "path": str(sync_path.resolve()),
                        "type": "auto_detected",
                    }
                )

    logger.info(f"Found {len(sync_descriptors)} sync files")

    return sync_descriptors


# ============================================================================
# Events Discovery (FR-11, Design §3.1)
# ============================================================================


def discover_events(session_dir: Path, settings: Settings) -> list[dict[str, Any]]:
    """Discover behavioral event files (optional).

    Args:
        session_dir: Session directory to search
        settings: Settings with events.patterns

    Returns:
        List of event file descriptors (empty if none found)

    Requirements: FR-11 (Optional events import)
    """
    session_dir = Path(session_dir)
    event_descriptors = []

    for pattern in settings.events.patterns:
        for event_path in session_dir.glob(pattern):
            event_descriptors.append(
                {
                    "path": str(event_path.resolve()),
                    "kind": "behavioral",
                    "format": settings.events.format,
                }
            )

    logger.info(f"Found {len(event_descriptors)} event files")

    return event_descriptors


# ============================================================================
# Pose Discovery (FR-5, Design §3.1)
# ============================================================================


def discover_pose(session_dir: Path, settings: Settings) -> list[dict[str, Any]]:
    """Discover pose files (optional).

    Args:
        session_dir: Session directory to search
        settings: Settings with labels configuration

    Returns:
        List of pose file descriptors (empty if none found)

    Requirements: FR-5 (Optional pose import)
    """
    session_dir = Path(session_dir)
    pose_descriptors = []

    # DLC outputs
    if settings.labels.dlc.model:
        dlc_pattern = "**/*DLC*.h5"
        for dlc_path in session_dir.glob(dlc_pattern):
            pose_descriptors.append(
                {
                    "path": str(dlc_path.resolve()),
                    "format": "dlc",
                    "model": settings.labels.dlc.model,
                }
            )

    # SLEAP outputs
    if settings.labels.sleap.model:
        sleap_pattern = "**/*.slp"
        for sleap_path in session_dir.glob(sleap_pattern):
            pose_descriptors.append(
                {
                    "path": str(sleap_path.resolve()),
                    "format": "sleap",
                    "model": settings.labels.sleap.model,
                }
            )

    logger.info(f"Found {len(pose_descriptors)} pose files")

    return pose_descriptors


# ============================================================================
# Facemap Discovery (FR-6, Design §3.1)
# ============================================================================


def discover_facemap(session_dir: Path, settings: Settings) -> list[dict[str, Any]]:
    """Discover facemap files (optional).

    Args:
        session_dir: Session directory to search
        settings: Settings with facemap configuration

    Returns:
        List of facemap file descriptors (empty if none found)

    Requirements: FR-6 (Optional facemap import)
    """
    session_dir = Path(session_dir)
    facemap_descriptors = []

    if settings.facemap.run:
        facemap_pattern = "**/*facemap*.npy"
        for facemap_path in session_dir.glob(facemap_pattern):
            facemap_descriptors.append(
                {
                    "path": str(facemap_path.resolve()),
                    "roi": settings.facemap.roi,
                }
            )

    logger.info(f"Found {len(facemap_descriptors)} facemap files")

    return facemap_descriptors


# ============================================================================
# Helpers
# ============================================================================


def _manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    """Convert Manifest to JSON-serializable dictionary.

    Args:
        manifest: Manifest object

    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "session_id": manifest.session_id,
        "videos": [
            {
                "camera_id": v.camera_id,
                "path": str(v.path),
                "codec": v.codec,
                "fps": v.fps,
                "duration": v.duration,
                "resolution": v.resolution,
            }
            for v in manifest.videos
        ],
        "sync": manifest.sync,
        "events": manifest.events,
        "pose": manifest.pose,
        "facemap": manifest.facemap,
        "config_snapshot": manifest.config_snapshot,
        "provenance": manifest.provenance,
    }
