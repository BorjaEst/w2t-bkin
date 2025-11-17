"""Synthetic video generation for testing.

This module generates synthetic video files that match the format expected by
the W2T-BKIN pipeline. Videos are minimal but valid, optimized for fast test
execution.

Video Generation Strategy:
--------------------------
- Use ffmpeg to create small, valid video files
- Minimize resolution and duration for speed
- Support multiple codecs (h264, rawvideo)
- Predictable frame counts for verification testing

Features:
---------
- Deterministic frame count
- Minimal file size
- Fast generation
- Valid format for ffprobe counting

Requirements Coverage:
----------------------
- FR-13: Video file generation for frame counting tests
- NFR-4: Fast generation for unit tests
"""

from pathlib import Path
import subprocess
from typing import Optional

from synthetic.models import SyntheticCamera


def is_synthetic_stub(video_path: Path) -> bool:
    """Check if a video file is a synthetic stub.

    Args:
        video_path: Path to video file

    Returns:
        True if file is a synthetic stub (has SYNTHVID magic marker)
    """
    if not video_path.exists():
        return False

    try:
        with open(video_path, "rb") as f:
            magic = f.read(8)
            return magic == b"SYNTHVID"
    except Exception:
        return False


def count_stub_frames(video_path: Path) -> int:
    """Read frame count from synthetic stub video.

    Args:
        video_path: Path to stub video file

    Returns:
        Frame count encoded in the stub

    Raises:
        ValueError: If not a valid synthetic stub
    """
    if not is_synthetic_stub(video_path):
        raise ValueError(f"Not a synthetic stub video: {video_path}")

    with open(video_path, "rb") as f:
        f.read(8)  # Skip magic
        frame_bytes = f.read(4)
        return int.from_bytes(frame_bytes, byteorder="little")


def create_video_file(
    output_path: Path,
    camera: SyntheticCamera,
    seed: Optional[int] = None,
    pattern: str = "testsrc",
) -> Path:
    """Create a synthetic video file using ffmpeg.

    Args:
        output_path: Path where video file should be written
        camera: Camera generation parameters (frame_count, fps, resolution)
        seed: Random seed (for pattern generation if applicable)
        pattern: ffmpeg video source pattern (testsrc, color, etc.)

    Returns:
        Path to created video file

    Raises:
        RuntimeError: If ffmpeg fails

    Example:
        >>> from pathlib import Path
        >>> from synthetic.models import SyntheticCamera
        >>> cam = SyntheticCamera(
        ...     camera_id="cam0",
        ...     frame_count=100,
        ...     fps=30.0,
        ...     resolution=(320, 240)
        ... )
        >>> path = create_video_file(Path("test.mp4"), cam)
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate duration from frame count and fps
    duration_s = camera.frame_count / camera.fps
    width, height = camera.resolution

    # Build ffmpeg command
    # Use -f lavfi with testsrc to generate synthetic test pattern
    # -frames:v ensures exact frame count
    # -pix_fmt yuv420p ensures compatibility
    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        f"{pattern}=size={width}x{height}:rate={camera.fps}",
        "-frames:v",
        str(camera.frame_count),
        "-pix_fmt",
        "yuv420p",
        "-y",  # Overwrite output file
        str(output_path),
    ]

    # Suppress ffmpeg output unless there's an error
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed to create video: {e.stderr.decode()}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ffmpeg timed out creating video: {e}") from e

    return output_path


def create_stub_video_file(output_path: Path, frame_count: int = 64) -> Path:
    """Create a minimal stub video file without ffmpeg (for unit tests).

    This creates a tiny placeholder file with a special marker that identifies
    it as a synthetic stub. The stub includes the frame count in a simple format
    that can be read by a custom counter.

    Args:
        output_path: Path where stub file should be written
        frame_count: Frame count to encode in the file

    Returns:
        Path to created stub file

    Note:
        This is NOT a valid video file for ffprobe. It's a placeholder for
        tests that don't actually need to process video content. The file
        format is:
            - Magic bytes: b'SYNTHVID'
            - Frame count: 4 bytes (little-endian int32)
            - Padding: random bytes to make it look like a video file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write stub with recognizable marker
    with open(output_path, "wb") as f:
        # Magic marker for synthetic video
        f.write(b"SYNTHVID")
        # Frame count as 4-byte integer
        f.write(frame_count.to_bytes(4, byteorder="little"))
        # Add some padding to make it non-empty (simulate video data)
        f.write(b"\x00" * 100)

    return output_path


def create_empty_video_file(output_path: Path) -> Path:
    """Create an empty video file for testing error handling.

    Args:
        output_path: Path where empty file should be written

    Returns:
        Path to created empty file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.touch()
    return output_path


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system.

    Returns:
        True if ffmpeg is available, False otherwise
    """
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
