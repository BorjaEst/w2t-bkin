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
- PrefectFlowRunFilter: Filter log records by Prefect flow-run context (prevents cross-session contamination)

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
>>> safe_path = sanitize_path("data/raw/metadata.toml")
>>> # Raises ValueError for dangerous paths like "../../../etc/passwd"
>>>
>>> # Validate files exist
>>> from w2t_bkin.utils import validate_file_exists
>>> validate_file_exists(video_path, IngestError, "Video file required")
"""

from datetime import datetime
import glob
import hashlib
import json
import logging
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Set, Type, Union

from pynwb import NWBFile

# Module logger
logger = logging.getLogger(__name__)

# Import version info
from importlib.metadata import version


class PathEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Path objects."""

    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def recursive_dict_update(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update base dictionary with values from update dictionary.

    Performs deep merge where nested dictionaries are recursively merged rather
    than replaced. Lists and other types are replaced.

    Parameters
    ----------
    base : Dict[str, Any]
        Base dictionary to update
    update : Dict[str, Any]
        Dictionary with values to merge into base

    Returns
    -------
    Dict[str, Any]
        Merged dictionary (modifies base in-place and returns it)

    Example
    -------
    >>> base = {"a": 1, "b": {"x": 10, "y": 20}}
    >>> update = {"b": {"y": 25, "z": 30}, "c": 3}
    >>> recursive_dict_update(base, update)
    {"a": 1, "b": {"x": 10, "y": 25, "z": 30}, "c": 3}
    """
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            recursive_dict_update(base[key], value)
        else:
            # Replace value (for non-dict types or new keys)
            base[key] = value
    return base


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO 8601 datetime string with timezone support.

    Supports formats:
    - YYYY-MM-DDTHH:MM:SS (naive datetime)
    - YYYY-MM-DDTHH:MM:SS+HH:MM (timezone offset)
    - YYYY-MM-DDTHH:MM:SSZ (UTC timezone)
    - YYYY-MM-DD HH:MM:SS (space separator, naive)

    Parameters
    ----------
    dt_str : str
        ISO 8601 datetime string

    Returns
    -------
    datetime
        Parsed datetime object (timezone-aware if timezone was specified)

    Example
    -------
    >>> parse_datetime("2025-11-21T14:30:00Z")
    datetime.datetime(2025, 11, 21, 14, 30, tzinfo=datetime.timezone.utc)
    >>> parse_datetime("2025-11-21T14:30:00")
    datetime.datetime(2025, 11, 21, 14, 30)
    """
    # Normalize 'Z' suffix to '+00:00' for Python < 3.11 compatibility
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"

    # Try with 'T' separator first (ISO 8601 standard)
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        pass

    # Try with space separator
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError(f"Invalid datetime format: {dt_str}. " f"Expected ISO 8601: YYYY-MM-DDTHH:MM:SS[Z|+HH:MM] or YYYY-MM-DD HH:MM:SS")


def get_source_script() -> Optional[str]:
    """Get the source script that is running (the __main__ script).

    Returns the absolute path of the script file used to create the NWB file.
    This captures the actual entry point script (e.g., pipeline.py, analysis.py).

    Returns
    -------
    Optional[str]
        Absolute path to the main script file, or None if not available

    Example
    -------
    >>> # When running: python pipeline.py
    >>> get_source_script()
    '/home/user/project/pipeline.py'

    >>> # When running interactively or from module
    >>> get_source_script()
    None
    """
    try:
        # sys.argv[0] contains the script that was invoked
        if sys.argv and sys.argv[0]:
            script_path = Path(sys.argv[0]).resolve()
            # Only return if it's an actual file (not '<stdin>' or similar)
            if script_path.exists() and script_path.is_file():
                return str(script_path)
    except (IndexError, OSError):
        pass

    return None


def get_source_script_file_name() -> Optional[str]:
    """Get the name of the source script file (without path).

    Returns just the filename of the script used to create the NWB file.

    Returns
    -------
    Optional[str]
        Name of the main script file, or None if not available

    Example
    -------
    >>> # When running: python /home/user/project/pipeline.py
    >>> get_source_script_file_name()
    'pipeline.py'
    """
    script_path = get_source_script()
    if script_path:
        return Path(script_path).name
    return None


def get_software_packages() -> List[str]:
    """Get list of software package names and versions used.

    Returns a list of package names with versions in the format:
    "package_name==version"

    This captures key dependencies for reproducibility and provenance tracking.

    Returns
    -------
    List[str]
        List of package names with versions (e.g., ["pynwb==3.1.0", "w2t_bkin==0.0.3"])

    Example
    -------
    >>> packages = get_software_packages()
    >>> print(packages)
    ['w2t_bkin==0.0.3', 'pynwb==3.1.0', 'hdmf==4.1.0', ...]
    """
    packages = []

    # Core packages to track
    package_names = [
        "w2t_bkin",  # This package
        "pynwb",  # NWB file creation
        "hdmf",  # Data format
        "deeplabcut",  # Pose estimation
        "facemap",  # Facial metrics
        "scipy",  # Scientific computing
        "numpy",  # Array operations
        "pandas",  # Data frames
        "torch",  # Deep learning (if used)
    ]

    for package_name in package_names:
        try:
            pkg_version = version(package_name)
            packages.append(f"{package_name}=={pkg_version}")
        except Exception:
            # Package not installed or version not available
            continue

    return packages


def compute_hash(data: Union[str, Dict[str, Any]]) -> str:
    """Compute deterministic SHA256 hash of input data.

    For dictionaries, canonicalizes by sorting keys before hashing.
    Handles Path objects by converting them to strings.

    Args:
        data: String or dictionary to hash

    Returns:
        SHA256 hex digest (64 characters)
    """
    if isinstance(data, dict):
        # Canonicalize: sort keys and convert to compact JSON
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), cls=PathEncoder)
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
        >>> data = read_toml(Path("metadata.toml"))
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


class PrefectFlowRunFilter(logging.Filter):
    """Logging filter that accepts only records from a specific Prefect flow run.

    Prevents cross-session log contamination when multiple sessions run concurrently
    in the same worker process. Each session's pipeline.log file handler is bound to
    its flow-run context via this filter.

    Logs emitted outside any Prefect flow-run context are rejected (they remain in
    Prefect's run logs but don't pollute session-specific files).

    Args:
        flow_run_id: The Prefect flow run ID to accept records from.
                     If None, accepts all records (no filtering).

    Example:
        >>> from prefect.context import get_run_context
        >>> ctx = get_run_context()
        >>> flow_run_filter = PrefectFlowRunFilter(ctx.flow_run.id)
        >>> handler.addFilter(flow_run_filter)
    """

    def __init__(self, flow_run_id: Optional[str] = None):
        super().__init__()
        self.flow_run_id = flow_run_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Accept record only if it originates from our flow-run context.

        Args:
            record: Log record to evaluate

        Returns:
            True if record should be logged, False otherwise
        """
        # If no flow_run_id set, accept all records (fallback for non-Prefect usage)
        if self.flow_run_id is None:
            return True

        try:
            # Import here to avoid hard dependency on prefect for utils module
            from prefect.runtime import flow_run

            # Get current flow run ID from runtime (works in tasks/threads)
            current_id = flow_run.id
            if current_id is None:
                # No flow run context available
                return False

            # Accept record only if it's from our flow run
            # Convert both to string to handle UUID vs str comparison
            return str(current_id) == str(self.flow_run_id)
        except Exception:
            # No Prefect runtime available (import-time logs, background threads, etc.)
            # Reject these records; they'll still appear in Prefect run logs
            return False


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


# =============================================================================
# Events Helper Functions (Numpy Array Handling)
# =============================================================================


def to_scalar(value: Union[Any, "np.ndarray"], index: int) -> Any:
    """Extract scalar from array or list.

    Args:
        value: Array, list, tuple, or scalar
        index: Index to extract

    Returns:
        Scalar value at index

    Raises:
        IndexError: Index out of bounds
    """
    import numpy as np

    if isinstance(value, np.ndarray):
        # Handle numpy arrays (including 0-d arrays)
        if value.ndim == 0:
            return value.item()
        return value[index].item() if hasattr(value[index], "item") else value[index]
    elif isinstance(value, (list, tuple)):
        return value[index]
    else:
        # Assume it's already a scalar
        return value


def to_list(value: Union[Any, "np.ndarray"]) -> List[Any]:
    """Convert array or scalar to Python list.

    Args:
        value: Array, list, tuple, or scalar

    Returns:
        Python list
    """
    import numpy as np

    if isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, (list, tuple)):
        return list(value)
    else:
        # Scalar value
        return [value]


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


# =============================================================================
# Video and TTL Counting Utilities
# =============================================================================


def count_video_frames(video_path: Path, timeout: int = 30) -> int:
    """Count frames in a video file using ffprobe or synthetic stub.

    This function counts video frames using ffprobe. It includes special
    handling for synthetic stub videos (used in testing) and provides
    robust error handling for unreadable or missing files.

    Args:
        video_path: Path to video file
        timeout: Maximum time in seconds to wait for ffprobe (default: 30)

    Returns:
        Number of frames in video (0 if file not found or empty)

    Raises:
        RuntimeError: If video file cannot be analyzed

    Example:
        >>> from pathlib import Path
        >>> frame_count = count_video_frames(Path("video.avi"))
        >>> print(f"Frames: {frame_count}")
    """
    # Validate input
    if not video_path.exists():
        logger.warning(f"Video file not found: {video_path}")
        return 0

    # Handle empty files
    if video_path.stat().st_size == 0:
        logger.warning(f"Video file is empty: {video_path}")
        return 0

    # Check if this is a synthetic stub video
    try:
        # Try importing synthetic module (only available if in test/synthetic context)
        from synthetic.video_synth import count_stub_frames, is_synthetic_stub

        if is_synthetic_stub(video_path):
            frame_count = count_stub_frames(video_path)
            logger.debug(f"Counted {frame_count} frames in synthetic stub {video_path.name}")
            return frame_count
    except ImportError:
        # Synthetic module not available - continue with normal ffprobe
        pass

    # Use ffprobe to count frames
    try:
        frame_count = run_ffprobe(video_path, timeout=timeout)
        logger.debug(f"Counted {frame_count} frames in {video_path.name}")
        return frame_count
    except Exception as e:
        # Log error and raise - frame counting failure is critical
        logger.error(f"Failed to count frames in {video_path}: {e}")
        raise RuntimeError(f"Could not count frames in video {video_path}: {e}")


def normalize_keypoints_to_dict(keypoints) -> Dict[str, Dict]:
    """Convert keypoints to standard dict format (name -> keypoint data).

    Handles multiple input formats:
    - KeypointsDict (custom dict that iterates over values)
    - Regular dict with keypoint name as key
    - List of keypoint dicts

    Args:
        keypoints: Keypoints in various formats

    Returns:
        Dictionary mapping keypoint name to keypoint data dict

    Example:
        >>> kp_list = [{"name": "nose", "x": 10, "y": 20}]
        >>> result = normalize_keypoints_to_dict(kp_list)
        >>> result["nose"]
        {"name": "nose", "x": 10, "y": 20}
    """
    if isinstance(keypoints, dict):
        # Check if it's a KeypointsDict or dict-like that iterates values
        if hasattr(keypoints, "__iter__") and keypoints:
            first_val = next(iter(keypoints.values()))
            if isinstance(first_val, dict) and "name" in first_val:
                # Already in correct format (name -> dict)
                return keypoints
        # Standard dict format
        return keypoints
    elif isinstance(keypoints, list):
        # Convert list to dict
        return {kp["name"]: kp for kp in keypoints}
    else:
        # Fallback for unknown types
        return {}


def log_missing_keypoints(
    frame_index: int,
    expected_names: Set[str],
    actual_names: Set[str],
    logger_instance: logging.Logger,
) -> None:
    """Log warning for missing keypoints in a frame.

    Args:
        frame_index: Frame number for logging
        expected_names: Set of expected keypoint names
        actual_names: Set of actual keypoint names found
        logger_instance: Logger to use for warning
    """
    missing = expected_names - actual_names
    if missing:
        logger_instance.warning(f"Frame {frame_index}: Missing keypoints {missing}")


def derive_bodyparts_from_data(data: List[Dict]) -> List[str]:
    """Extract canonical bodypart names from harmonized pose data.

    Args:
        data: List of pose frame dictionaries with keypoints

    Returns:
        Sorted list of bodypart names

    Raises:
        ValueError: If data is empty or has no keypoints

    Example:
        >>> frames = [{"keypoints": {"nose": {...}, "ear_left": {...}}}]
        >>> derive_bodyparts_from_data(frames)
        ["ear_left", "nose"]
    """
    if not data:
        raise ValueError("Cannot derive bodyparts from empty data")

    first_frame_keypoints = normalize_keypoints_to_dict(data[0].get("keypoints", {}))

    if not first_frame_keypoints:
        raise ValueError("First frame has no keypoints")

    # Sort for consistency across runs
    return sorted(first_frame_keypoints.keys())


def count_ttl_pulses(ttl_path: Path) -> int:
    """Count TTL pulses from log file.

    Counts non-empty lines in a TTL log file. Each line represents one
    TTL pulse event.

    Args:
        ttl_path: Path to TTL log file

    Returns:
        Number of pulses in file (0 if file not found or unreadable)

    Example:
        >>> from pathlib import Path
        >>> pulse_count = count_ttl_pulses(Path("camera_ttl.log"))
        >>> print(f"Pulses: {pulse_count}")
    """
    if not ttl_path.exists():
        return 0

    # Count lines in TTL file (each line = one pulse)
    try:
        with open(ttl_path, "r") as f:
            lines = f.readlines()
            return len([line for line in lines if line.strip()])
    except Exception:
        return 0


def discover_sessions_in_raw_root(
    raw_root: Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Discover sessions in raw data directory with glob pattern support.

    Scans the raw_root directory and returns valid subject/session combinations.
    A valid session must have either a session.toml or metadata.toml file.

    Parameters
    ----------
    raw_root : Path
        Raw data root directory
    subject_filter : Optional[str], optional
        Glob pattern to filter subjects (e.g., 'subject-*', 'SNA-*')
    session_filter : Optional[str], optional
        Glob pattern to filter sessions (e.g., 'session-001', '2024-*')

    Returns
    -------
    List[Dict[str, Any]]
        List of dictionaries with keys:
        - subject: Subject identifier
        - session: Session identifier
        - has_subject_metadata: Whether subject.toml exists
        - metadata_file: Name of metadata file ("session.toml" or "metadata.toml")

    Raises
    ------
    ValueError
        If raw_root does not exist

    Example
    -------
    >>> from pathlib import Path
    >>> from w2t_bkin.utils import discover_sessions_in_raw_root
    >>>
    >>> # Discover all sessions
    >>> sessions = discover_sessions_in_raw_root(Path("data/raw"))
    >>>
    >>> # Filter by glob pattern
    >>> sessions = discover_sessions_in_raw_root(
    ...     Path("data/raw"),
    ...     subject_filter="subject-*",
    ...     session_filter="2024-*"
    ... )
    """
    from fnmatch import fnmatch

    if not raw_root.exists():
        raise ValueError(f"raw_root does not exist: {raw_root}")

    discoveries = []

    # Iterate through subjects
    for subject_dir in sorted(raw_root.iterdir()):
        if not subject_dir.is_dir():
            continue
        if subject_dir.name.startswith("."):
            continue

        subject_id = subject_dir.name

        # Apply subject filter (glob pattern)
        if subject_filter and not fnmatch(subject_id, subject_filter):
            continue

        # Check for subject.toml
        subject_toml = subject_dir / "subject.toml"
        has_subject_metadata = subject_toml.exists()

        # Iterate through sessions
        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            if session_dir.name.startswith("."):
                continue

            session_id = session_dir.name

            # Apply session filter (glob pattern)
            if session_filter and not fnmatch(session_id, session_filter):
                continue

            # Check for session metadata (session.toml or metadata.toml)
            session_toml = session_dir / "session.toml"
            metadata_toml = session_dir / "metadata.toml"
            has_session_metadata = session_toml.exists() or metadata_toml.exists()

            # Valid session must have metadata
            if has_session_metadata:
                discoveries.append(
                    {
                        "subject": subject_id,
                        "session": session_id,
                        "has_subject_metadata": has_subject_metadata,
                        "metadata_file": "session.toml" if session_toml.exists() else "metadata.toml",
                    }
                )

    return discoveries


def discover_sessions(
    config_path: Union[str, Path],
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Discover sessions from config file (CLI convenience wrapper).

    Loads configuration from TOML file and delegates to discover_sessions_in_raw_root.

    Parameters
    ----------
    config_path : Union[str, Path]
        Path to configuration TOML file
    subject_filter : Optional[str], optional
        Glob pattern to filter subjects (e.g., 'subject-*')
    session_filter : Optional[str], optional
        Glob pattern to filter sessions (e.g., 'session-001')

    Returns
    -------
    List[Dict[str, Any]]
        List of session dictionaries (see discover_sessions_in_raw_root)

    Raises
    ------
    FileNotFoundError
        If config file does not exist
    ValueError
        If raw_root does not exist

    Example
    -------
    >>> from w2t_bkin.utils import discover_sessions
    >>>
    >>> # Discover all sessions
    >>> sessions = discover_sessions("config.toml")
    >>>
    >>> # Filter by glob pattern
    >>> sessions = discover_sessions("config.toml", subject_filter="subject-*")
    """
    from w2t_bkin.config import load_config

    config = load_config(Path(config_path))
    return discover_sessions_in_raw_root(
        raw_root=config.paths.raw_root,
        subject_filter=subject_filter,
        session_filter=session_filter,
    )
