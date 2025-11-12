"""Utility functions for W2T-BKIN pipeline (Phase 0 - Foundation).

This module provides core utilities used throughout the pipeline:
- Deterministic SHA256 hashing for files and data structures
- Path sanitization to prevent directory traversal attacks
- JSON I/O with consistent formatting
- Video analysis using FFmpeg/FFprobe

The utilities ensure reproducible outputs (NFR-1), secure file handling (NFR-2),
and efficient video metadata extraction (FR-2).

Key Functions:
--------------
- compute_hash: Deterministic hashing with key canonicalization
- sanitize_path: Security validation for file paths
- read_json, write_json: JSON persistence with formatting
- run_ffprobe: Video frame counting and metadata extraction

Requirements:
-------------
- NFR-1: Reproducible outputs (deterministic hashing)
- NFR-2: Security (path sanitization)
- NFR-3: Performance (efficient I/O)
- FR-2: Video frame counting

Acceptance Criteria:
-------------------
- A18: Deterministic hashing produces identical results for identical inputs

Example:
--------
>>> from w2t_bkin.utils import compute_hash, sanitize_path
>>>
>>> # Compute deterministic hash
>>> data = {"session": "Session-001", "timestamp": "2025-11-12"}
>>> hash_value = compute_hash(data)
>>> print(hash_value)  # Consistent across runs
>>>
>>> # Sanitize file paths
>>> safe_path = sanitize_path("data/raw/session.toml")
>>> # Raises ValueError for dangerous paths like "../../../etc/passwd"
"""

import hashlib
import json
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional, Union


def compute_hash(data: Union[str, Dict[str, Any]]) -> str:
    """Compute deterministic SHA256 hash of input data.

    For dictionaries, canonicalizes by sorting keys before hashing.

    Args:
        data: String or dictionary to hash

    Returns:
        SHA256 hex digest (64 characters)
    """
    if isinstance(data, dict):
        # Canonicalize: sort keys and convert to compact JSON
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        data_bytes = canonical.encode("utf-8")
    else:
        data_bytes = data.encode("utf-8")

    return hashlib.sha256(data_bytes).hexdigest()


def sanitize_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
    """Sanitize path to prevent directory traversal attacks.

    Args:
        path: Path to sanitize
        base: Optional base directory to restrict path to

    Returns:
        Sanitized Path object

    Raises:
        ValueError: If path attempts directory traversal
    """
    path_obj = Path(path)

    # Check for directory traversal patterns
    if ".." in path_obj.parts:
        raise ValueError(f"Directory traversal not allowed: {path}")

    # If base provided, ensure resolved path is within base
    if base is not None:
        base = Path(base).resolve()
        resolved = (base / path_obj).resolve()
        if not str(resolved).startswith(str(base)):
            raise ValueError(f"Path {path} outside allowed base {base}")
        return resolved

    return path_obj


def write_json(data: Dict[str, Any], path: Union[str, Path], indent: int = 2) -> None:
    """Write data to JSON file with custom encoder for Path objects.

    Args:
        data: Dictionary to write
        path: Output file path
        indent: JSON indentation (default: 2 spaces)
    """

    class PathEncoder(json.JSONEncoder):
        """Custom JSON encoder that handles Path objects."""

        def default(self, obj):
            if isinstance(obj, Path):
                return str(obj)
            return super().default(obj)

    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path_obj, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, cls=PathEncoder)


def read_json(path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file into dictionary.

    Args:
        path: Input file path

    Returns:
        Dictionary with parsed JSON data
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def configure_logger(name: str, level: str = "INFO", structured: bool = False) -> logging.Logger:
    """Configure logger with specified settings.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: If True, use structured (JSON) logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    handler = logging.StreamHandler()

    if structured:
        # JSON structured logging
        formatter = logging.Formatter('{"timestamp":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}')
    else:
        # Standard logging
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


class VideoAnalysisError(Exception):
    """Error during video analysis operations."""

    pass


def run_ffprobe(video_path: Path, timeout: int = 30) -> int:
    """Count frames in a video file using ffprobe.

    Uses ffprobe to accurately count video frames by reading the stream metadata.
    This is more reliable than using OpenCV for corrupted or unusual video formats.

    Args:
        video_path: Path to video file
        timeout: Maximum time in seconds to wait for ffprobe (default: 30)

    Returns:
        Number of frames in video

    Raises:
        VideoAnalysisError: If video file is invalid or ffprobe fails
        FileNotFoundError: If video file does not exist
        ValueError: If video_path is not a valid path

    Security:
        - Input path validation to prevent command injection
        - Subprocess timeout to prevent hanging
        - stderr capture for diagnostic information
    """
    # Input validation
    if not isinstance(video_path, Path):
        video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not video_path.is_file():
        raise ValueError(f"Path is not a file: {video_path}")

    # Sanitize path - resolve to absolute path to prevent injection
    video_path = video_path.resolve()

    # ffprobe command to count frames accurately
    # -v error: only show errors
    # -select_streams v:0: select first video stream
    # -count_frames: actually count frames (slower but accurate)
    # -show_entries stream=nb_read_frames: output only frame count
    # -of csv=p=0: output as CSV without header
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-count_frames",
        "-show_entries",
        "stream=nb_read_frames",
        "-of",
        "csv=p=0",
        str(video_path),
    ]

    try:
        # Run ffprobe with timeout and capture output
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )

        # Parse output - should be a single integer
        output = result.stdout.strip()

        if not output:
            raise VideoAnalysisError(f"ffprobe returned empty output for: {video_path}")

        try:
            frame_count = int(output)
        except ValueError:
            raise VideoAnalysisError(f"ffprobe returned non-integer output: {output}")

        if frame_count < 0:
            raise VideoAnalysisError(f"ffprobe returned negative frame count: {frame_count}")

        return frame_count

    except subprocess.TimeoutExpired:
        raise VideoAnalysisError(f"ffprobe timed out after {timeout}s for: {video_path}")

    except subprocess.CalledProcessError as e:
        # ffprobe failed - provide diagnostic information
        stderr_msg = e.stderr.strip() if e.stderr else "No error message"
        raise VideoAnalysisError(f"ffprobe failed for {video_path}: {stderr_msg}")

    except Exception as e:
        # Unexpected error
        raise VideoAnalysisError(f"Unexpected error running ffprobe: {e}")


if __name__ == "__main__":
    """Usage examples for utils module."""
    import tempfile

    print("=" * 70)
    print("W2T-BKIN Utils Module - Usage Examples")
    print("=" * 70)
    print()

    # Example 1: Compute hash
    print("Example 1: Compute Hash")
    print("-" * 50)
    test_data = {"session_id": "Session-000001", "timestamp": "2025-11-12"}
    hash_result = compute_hash(test_data)
    print(f"Data: {test_data}")
    print(f"Hash: {hash_result}")
    print()

    # Example 2: Sanitize path
    print("Example 2: Sanitize Path")
    print("-" * 50)
    safe_path = sanitize_path("data/raw/Session-000001")
    print(f"Input: data/raw/Session-000001")
    print(f"Sanitized: {safe_path}")

    try:
        dangerous = sanitize_path("../../etc/passwd")
        print(f"Dangerous path: {dangerous}")
    except ValueError as e:
        print(f"Blocked directory traversal: {e}")
    print()

    # Example 3: JSON I/O
    print("Example 3: JSON I/O")
    print("-" * 50)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    test_obj = {"key": "value", "number": 42}
    write_json(test_obj, temp_path)
    print(f"Wrote to: {temp_path.name}")

    loaded = read_json(temp_path)
    print(f"Read back: {loaded}")
    temp_path.unlink()
    print()

    print("=" * 70)
    print("Examples completed. See module docstring for more details.")
    print("=" * 70)
