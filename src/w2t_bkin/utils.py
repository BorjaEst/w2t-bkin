"""Utility functions for W2T-BKIN pipeline (Phase 0 - Foundation).

This module provides core utilities used throughout the pipeline:
- Deterministic SHA256 hashing for files and data structures
- Path sanitization to prevent directory traversal attacks
- File discovery and sorting with glob patterns
- Path and file validation with customizable error handling
- String sanitization for safe identifiers
- File size validation
- Directory creation with write permission checking
- File checksum computation
- TOML file reading
- JSON I/O with consistent formatting
- Video analysis using FFmpeg/FFprobe
- Logger configuration

The utilities ensure reproducible outputs (NFR-1), secure file handling (NFR-2),
and efficient video metadata extraction (FR-2).

Key Functions:
--------------
Core Hashing:
- compute_hash: Deterministic hashing with key canonicalization for dicts
- compute_file_checksum: Compute SHA256/SHA1/MD5 checksum of files

File Discovery & Sorting:
- discover_files: Find files matching glob patterns, return absolute paths
- sort_files: Sort files by name or modification time

Path & File Validation:
- sanitize_path: Security validation for file paths (directory traversal prevention)
- validate_file_exists: Check file exists and is a file
- validate_dir_exists: Check directory exists and is a directory
- validate_file_size: Check file size within limits

String & Directory Operations:
- sanitize_string: Remove control characters, limit length
- is_nan_or_none: Check if value is None or NaN
- convert_matlab_struct: Convert MATLAB struct objects to dictionaries
- validate_against_whitelist: Validate value against allowed set
- ensure_directory: Create directory with optional write permission check

File I/O:
- read_toml: Load TOML files
- read_json: Load JSON files
- write_json: Save JSON with Path object support

Video Analysis:
- run_ffprobe: Count frames using ffprobe

Logging:
- configure_logger: Set up structured or standard logging

Requirements:
-------------
- NFR-1: Reproducible outputs (deterministic hashing)
- NFR-2: Security (path sanitization, validation)
- NFR-3: Performance (efficient I/O)
- FR-2: Video frame counting

Acceptance Criteria:
-------------------
- A18: Deterministic hashing produces identical results for identical inputs

Example:
--------
>>> from w2t_bkin.utils import compute_hash, sanitize_path, discover_files
>>>
>>> # Compute deterministic hash
>>> data = {"session": "Session-001", "timestamp": "2025-11-12"}
>>> hash_value = compute_hash(data)
>>> print(hash_value)  # Consistent across runs
>>>
>>> # Discover files with glob
>>> video_files = discover_files(Path("data/raw/session"), "*.avi")
>>>
>>> # Sanitize file paths
>>> safe_path = sanitize_path("data/raw/session.toml")
>>> # Raises ValueError for dangerous paths like "../../../etc/passwd"
>>>
>>> # Validate files exist
>>> from w2t_bkin.utils import validate_file_exists
>>> validate_file_exists(video_path, IngestError, "Video file required")
"""

import glob
import hashlib
import json
import logging
import math
from pathlib import Path
import subprocess
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Set, Type, Union


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


def discover_files(base_dir: Path, pattern: str, sort: bool = True) -> List[Path]:
    """Discover files matching glob pattern and return absolute paths.

    Args:
        base_dir: Base directory to resolve pattern from
        pattern: Glob pattern (relative to base_dir)
        sort: If True, sort files by name (default: True)

    Returns:
        List of absolute Path objects

    Example:
        >>> files = discover_files(Path("data/raw"), "*.avi")
        >>> files = discover_files(session_dir, "Bpod/*.mat", sort=True)
    """
    full_pattern = str(base_dir / pattern)
    file_paths = [Path(p).resolve() for p in glob.glob(full_pattern)]

    if sort:
        file_paths.sort(key=lambda p: p.name)

    return file_paths


def sort_files(files: List[Path], strategy: Literal["name_asc", "name_desc", "time_asc", "time_desc"]) -> List[Path]:
    """Sort file list by specified strategy.

    Args:
        files: List of file paths to sort
        strategy: Sorting strategy:
            - "name_asc": Sort by filename ascending
            - "name_desc": Sort by filename descending
            - "time_asc": Sort by modification time ascending (oldest first)
            - "time_desc": Sort by modification time descending (newest first)

    Returns:
        Sorted list of Path objects (new list, does not modify input)

    Example:
        >>> files = sort_files(discovered_files, "time_desc")
    """
    sorted_files = files.copy()

    if strategy == "name_asc":
        sorted_files.sort(key=lambda p: p.name)
    elif strategy == "name_desc":
        sorted_files.sort(key=lambda p: p.name, reverse=True)
    elif strategy == "time_asc":
        sorted_files.sort(key=lambda p: p.stat().st_mtime)
    elif strategy == "time_desc":
        sorted_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        raise ValueError(f"Invalid sort strategy: {strategy}")

    return sorted_files


def validate_file_exists(path: Path, error_class: Type[Exception] = FileNotFoundError, message: Optional[str] = None) -> None:
    """Validate file exists and is a file, not a directory.

    Args:
        path: Path to validate
        error_class: Exception class to raise on validation failure
        message: Optional custom error message

    Raises:
        error_class: If file doesn't exist or is not a file

    Example:
        >>> validate_file_exists(video_path, IngestError, "Video file required")
    """
    if not path.exists():
        msg = message or f"File not found: {path}"
        raise error_class(msg)

    if not path.is_file():
        msg = message or f"Path is not a file: {path}"
        raise error_class(msg)


def validate_dir_exists(path: Path, error_class: Type[Exception] = FileNotFoundError, message: Optional[str] = None) -> None:
    """Validate directory exists and is a directory, not a file.

    Args:
        path: Path to validate
        error_class: Exception class to raise on validation failure
        message: Optional custom error message

    Raises:
        error_class: If directory doesn't exist or is not a directory

    Example:
        >>> validate_dir_exists(output_dir, NWBError, "Output directory required")
    """
    if not path.exists():
        msg = message or f"Directory not found: {path}"
        raise error_class(msg)

    if not path.is_dir():
        msg = message or f"Path is not a directory: {path}"
        raise error_class(msg)


def validate_file_size(path: Path, max_size_mb: float) -> float:
    """Validate file size within limits, return size in MB.

    Args:
        path: Path to file
        max_size_mb: Maximum allowed size in megabytes

    Returns:
        File size in MB

    Raises:
        ValueError: If file exceeds size limit

    Example:
        >>> size_mb = validate_file_size(bpod_path, max_size_mb=100)
    """
    file_size_mb = path.stat().st_size / (1024 * 1024)

    if file_size_mb > max_size_mb:
        raise ValueError(f"File too large: {file_size_mb:.1f}MB exceeds {max_size_mb}MB limit")

    return file_size_mb


def sanitize_string(
    text: str, max_length: int = 100, allowed_pattern: Literal["alphanumeric", "alphanumeric_-", "alphanumeric_-_", "printable"] = "alphanumeric_-_", default: str = "unknown"
) -> str:
    """Sanitize string by removing control characters and limiting length.

    Args:
        text: String to sanitize
        max_length: Maximum length of output string
        allowed_pattern: Character allowance pattern:
            - "alphanumeric": Only letters and numbers
            - "alphanumeric_-": Letters, numbers, hyphens
            - "alphanumeric_-_": Letters, numbers, hyphens, underscores
            - "printable": All printable characters
        default: Default value if sanitized string is empty

    Returns:
        Sanitized string

    Example:
        >>> safe_id = sanitize_string("Session-001", allowed_pattern="alphanumeric_-")
        >>> safe_event = sanitize_string(raw_event_name, max_length=50)
    """
    if not isinstance(text, str):
        return default

    # Remove control characters based on pattern
    if allowed_pattern == "alphanumeric":
        sanitized = "".join(c for c in text if c.isalnum())
    elif allowed_pattern == "alphanumeric_-":
        sanitized = "".join(c for c in text if c.isalnum() or c == "-")
    elif allowed_pattern == "alphanumeric_-_":
        sanitized = "".join(c for c in text if c.isalnum() or c in "-_")
    elif allowed_pattern == "printable":
        sanitized = "".join(c for c in text if c.isprintable())
    else:
        raise ValueError(f"Invalid allowed_pattern: {allowed_pattern}")

    # Limit length
    sanitized = sanitized[:max_length]

    # Return default if empty
    if not sanitized:
        return default

    return sanitized


def is_nan_or_none(value: Any) -> bool:
    """Check if value is None or NaN (for float values).

    Args:
        value: Value to check

    Returns:
        True if value is None or NaN, False otherwise

    Example:
        >>> is_nan_or_none(None)  # True
        >>> is_nan_or_none(float('nan'))  # True
        >>> is_nan_or_none(0.0)  # False
        >>> is_nan_or_none([1.0, 2.0])  # False
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def convert_matlab_struct(obj: Any) -> Dict[str, Any]:
    """Convert MATLAB struct object to dictionary.

    Handles scipy.io mat_struct objects by extracting non-private attributes.
    If already a dict, returns as-is. For other types, returns empty dict.

    Args:
        obj: MATLAB struct object, dictionary, or other type

    Returns:
        Dictionary representation

    Example:
        >>> # With scipy mat_struct
        >>> from scipy.io import loadmat
        >>> data = loadmat("file.mat")
        >>> session_data = convert_matlab_struct(data["SessionData"])
        >>>
        >>> # With plain dict
        >>> convert_matlab_struct({"key": "value"})  # Returns as-is
    """
    if hasattr(obj, "__dict__"):
        # scipy mat_struct or similar object with __dict__
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    elif isinstance(obj, dict):
        # Already a dictionary
        return obj
    else:
        # Unsupported type - return empty dict
        return {}


def validate_against_whitelist(value: str, whitelist: Union[Set[str], FrozenSet[str]], default: str, warn: bool = True) -> str:
    """Validate string value against whitelist, return default if invalid.

    Args:
        value: Value to validate
        whitelist: Set or frozenset of allowed values
        default: Default value to return if validation fails
        warn: If True, log warning when value not in whitelist

    Returns:
        Value if in whitelist, otherwise default

    Example:
        >>> outcomes = frozenset(["hit", "miss", "correct"])
        >>> validate_against_whitelist("hit", outcomes, "unknown")  # "hit"
        >>> validate_against_whitelist("invalid", outcomes, "unknown")  # "unknown"
    """
    if value in whitelist:
        return value

    if warn:
        logger = logging.getLogger(__name__)
        logger.warning(f"Invalid value '{value}', defaulting to '{default}'")

    return default


def ensure_directory(path: Path, check_writable: bool = False) -> Path:
    """Ensure directory exists, optionally check write permissions.

    Args:
        path: Directory path to ensure
        check_writable: If True, verify directory is writable

    Returns:
        The path (for chaining)

    Raises:
        OSError: If directory cannot be created
        PermissionError: If check_writable=True and directory is not writable

    Example:
        >>> output_dir = ensure_directory(Path("data/processed"), check_writable=True)
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    if not path.is_dir():
        raise OSError(f"Path exists but is not a directory: {path}")

    if check_writable:
        # Try to write test file to check permissions
        test_file = path / ".test_write"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise PermissionError(f"Directory is not writable: {path}. Error: {e}")

    return path


def compute_file_checksum(file_path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Compute checksum of file using specified algorithm.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, sha1, md5)
        chunk_size: Read chunk size in bytes

    Returns:
        Hex digest of file checksum

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is unsupported

    Example:
        >>> checksum = compute_file_checksum(video_path)
        >>> checksum = compute_file_checksum(video_path, algorithm="sha1")
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Create hash object
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    # Read file in chunks and update hash
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def read_toml(path: Union[str, Path]) -> Dict[str, Any]:
    """Read TOML file into dictionary.

    Args:
        path: Path to TOML file (str or Path)

    Returns:
        Dictionary with parsed TOML data

    Raises:
        FileNotFoundError: If file doesn't exist

    Example:
        >>> data = read_toml("config.toml")
        >>> data = read_toml(Path("session.toml"))
    """
    path = Path(path) if isinstance(path, str) else path

    if not path.exists():
        raise FileNotFoundError(f"TOML file not found: {path}")

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


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
