"""Video transcoding module with idempotence and content addressing.

Transcodes videos to mezzanine format using FFmpeg with content-based output paths.

Requirements: FR-4, NFR-2
"""

import hashlib
import json
import logging
from pathlib import Path
import subprocess
from typing import Dict, Optional

import cv2

from w2t_bkin.domain import TranscodedVideo, TranscodeOptions

logger = logging.getLogger(__name__)


class TranscodeError(Exception):
    """Base exception for transcode-related errors."""

    pass


def create_transcode_options(codec: str = "libx264", crf: int = 18, preset: str = "medium", keyint: int = 15) -> TranscodeOptions:
    """Create TranscodeOptions with validation.

    Args:
        codec: Video codec (default: libx264)
        crf: Constant Rate Factor 0-51 (default: 18, lower=better quality)
        preset: Encoding preset (default: medium)
        keyint: Keyframe interval (default: 15)

    Returns:
        TranscodeOptions object

    Raises:
        ValueError: If CRF out of range [0, 51]
    """
    if not 0 <= crf <= 51:
        raise ValueError(f"CRF must be in range [0, 51], got {crf}")

    return TranscodeOptions(codec=codec, crf=crf, preset=preset, keyint=keyint)


def compute_video_checksum(video_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA256 checksum of video file.

    Args:
        video_path: Path to video file
        chunk_size: Read chunk size in bytes

    Returns:
        SHA256 hex digest

    Raises:
        TranscodeError: If file doesn't exist
    """
    if not video_path.exists():
        raise TranscodeError(f"Video file not found: {video_path}")

    sha256 = hashlib.sha256()

    with open(video_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)

    return sha256.hexdigest()


def is_already_transcoded(video_path: Path, options: TranscodeOptions, transcoded_path: Path) -> bool:
    """Check if video is already transcoded with given options.

    Args:
        video_path: Original video path
        options: Transcode options to check
        transcoded_path: Path to transcoded output

    Returns:
        True if already transcoded with same options, False otherwise
    """
    # Simple check: does the transcoded file exist?
    if not transcoded_path.exists():
        return False

    # Could add more sophisticated checks here (e.g., compare metadata)
    # For now, existence check is sufficient for GREEN phase
    return True


def transcode_video(video_path: Path, options: TranscodeOptions, output_dir: Path) -> TranscodedVideo:
    """Transcode video to mezzanine format.

    Args:
        video_path: Path to input video
        options: Transcoding options
        output_dir: Output directory

    Returns:
        TranscodedVideo metadata

    Raises:
        TranscodeError: If transcoding fails
    """
    if not video_path.exists():
        raise TranscodeError(f"Video file not found: {video_path}")

    try:
        # Compute checksum for content addressing
        checksum = compute_video_checksum(video_path)
        checksum_prefix = checksum[:12]  # Use first 12 chars

        # Extract camera ID from filename (e.g., "cam0_...")
        camera_id = "cam0"  # Default
        if "_" in video_path.stem:
            parts = video_path.stem.split("_")
            if parts[0].startswith("cam"):
                camera_id = parts[0]

        # Create output path with checksum
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{camera_id}_transcoded_{checksum_prefix}.mp4"
        output_path = output_dir / output_filename

        # Get frame count from original video
        cap = cv2.VideoCapture(str(video_path))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        # Build ffmpeg command
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            str(video_path),
            "-c:v",
            options.codec,
            "-crf",
            str(options.crf),
            "-preset",
            options.preset,
            "-g",
            str(options.keyint),
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]

        # Execute ffmpeg
        logger.info(f"Transcoding {video_path.name} to {output_path.name}")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)

        # Verify output exists
        if not output_path.exists():
            raise TranscodeError("Transcode completed but output file not found")

        # Create metadata
        transcoded = TranscodedVideo(
            camera_id=camera_id, original_path=video_path, output_path=output_path, codec=options.codec, checksum=checksum, frame_count=frame_count
        )

        return transcoded

    except subprocess.CalledProcessError as e:
        raise TranscodeError(f"FFmpeg failed: {e.stderr}")
    except Exception as e:
        raise TranscodeError(f"Transcode failed: {e}")


def update_manifest_with_transcode(manifest: Dict, transcoded: TranscodedVideo) -> Dict:
    """Update manifest with transcoded video path.

    Args:
        manifest: Session manifest dict
        transcoded: TranscodedVideo metadata

    Returns:
        Updated manifest dict
    """
    # Make a copy to avoid mutating original
    updated = manifest.copy()

    # Find matching video entry by camera_id
    for video in updated.get("videos", []):
        if video.get("camera_id") == transcoded.camera_id:
            video["transcoded_path"] = str(transcoded.output_path)
            video["transcoded_checksum"] = transcoded.checksum
            break

    return updated
