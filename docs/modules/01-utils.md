# Utils Module

**Phase:** 0 (Foundation)  
**Status:** ✅ Complete  
**Requirements:** NFR-1 (Reproducibility), NFR-2 (Idempotence), NFR-3 (Observability)

## Purpose

Provides shared utility functions for hashing, path sanitization, subprocess execution, JSON I/O, and logging. All other modules depend on utils for these primitives.

## Key Functions

### Hashing

```python
def compute_hash(data: Union[str, Dict[str, Any]]) -> str:
    """Compute deterministic SHA256 hash of input data.

    For dictionaries, canonicalizes by sorting keys before hashing.

    Args:
        data: String or dictionary to hash

    Returns:
        SHA256 hex digest (64 characters)

    Example:
        >>> from w2t_bkin.utils import compute_hash
        >>> hash_val = compute_hash('{"key": "value"}')
        >>> len(hash_val)
        64
        >>> # Can also hash dictionaries directly
        >>> hash_val = compute_hash({"key": "value"})
    """
```

### Path Safety

```python
def sanitize_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
    """Sanitize path to prevent directory traversal attacks.

    Args:
        path: Path to sanitize
        base: Optional base directory to restrict path to

    Returns:
        Sanitized Path object

    Raises:
        ValueError: If path attempts directory traversal

    Example:
        >>> from w2t_bkin.utils import sanitize_path
        >>> safe_path = sanitize_path("data/raw/video.avi")
        >>> # Restrict to base directory
        >>> safe_path = sanitize_path("video.avi", base=Path("/data/raw"))
    """
```

### Subprocess Execution

```python
def run_ffprobe(video_path: Path, timeout: int = 30) -> int:
    """Count frames in a video file using ffprobe.

    Uses ffprobe to accurately count video frames by reading stream metadata.
    More reliable than OpenCV for corrupted or unusual video formats.

    Args:
        video_path: Path to video file
        timeout: Maximum time in seconds to wait for ffprobe (default: 30)

    Returns:
        Number of frames in video

    Raises:
        VideoAnalysisError: If video file is invalid or ffprobe fails
        FileNotFoundError: If video file doesn't exist
        ValueError: If video_path is not a valid path

    Security:
        - Input path validation to prevent command injection
        - Subprocess timeout to prevent hanging
        - stderr capture for diagnostic information

    Example:
        >>> from w2t_bkin.utils import run_ffprobe
        >>> frame_count = run_ffprobe(Path("video.avi"))
        >>> print(frame_count)
    """
```

### JSON I/O

```python
def write_json(data: Dict[str, Any], path: Union[str, Path], indent: int = 2) -> None:
    """Write data to JSON file with custom encoder for Path objects.

    Args:
        data: Dictionary to write
        path: Output file path
        indent: JSON indentation (default: 2 spaces)

    Note:
        - Automatically creates parent directories if they don't exist
        - Custom PathEncoder handles Path objects by converting to strings
        - Uses UTF-8 encoding
    """

def read_json(path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file into dictionary.

    Args:
        path: Input file path

    Returns:
        Dictionary with parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
    """
```

### Logging

```python
def configure_logger(name: str, level: str = "INFO", structured: bool = False) -> logging.Logger:
    """Configure logger with specified settings.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: If True, use structured (JSON) logging

    Returns:
        Configured logger instance

    Example:
        >>> from w2t_bkin.utils import configure_logger
        >>> logger = configure_logger("w2t_bkin.ingest", level="DEBUG")
        >>> logger.info("Processing started")
        >>> # Structured logging
        >>> json_logger = configure_logger("w2t_bkin", structured=True)
    """
```

## Error Handling

Utils functions raise standard Python exceptions:

- `ValueError`: For invalid inputs (path traversal, invalid paths)
- `FileNotFoundError`: For missing files
- `subprocess.TimeoutExpired`: For ffprobe timeout
- `json.JSONDecodeError`: For invalid JSON
- `VideoAnalysisError`: Custom exception for video analysis failures (ffprobe errors)

### VideoAnalysisError

```python
class VideoAnalysisError(Exception):
    """Error during video analysis operations."""
    pass
```

This custom exception is raised by `run_ffprobe()` for:

- Empty ffprobe output
- Non-integer frame count
- Negative frame count
- ffprobe command failures
- Unexpected errors during execution

## Testing

**Test file:** `tests/unit/test_utils.py`

**Coverage:**

- ✅ Hash consistency and reproducibility
- ✅ Path sanitization edge cases (directory traversal, base restriction)
- ✅ ffprobe frame counting (mocked and real tests)
- ✅ JSON round-trip serialization with Path encoder
- ✅ Logger configuration (standard and structured)
- ✅ VideoAnalysisError for various failure modes

**Run tests:**

```bash
pytest tests/unit/test_utils.py -v
```

## Design Decisions

1. **Deterministic hashing:** Always sort keys before hashing for reproducibility (NFR-1)
2. **Dict and string hashing:** Support both dictionaries and strings for flexibility
3. **Path safety:** Reject paths with `..`, optional base directory restriction
4. **Custom Path encoder:** Automatic Path→string conversion in JSON serialization
5. **Subprocess wrapping:** Capture stdout/stderr, timeout support (30s default), error context
6. **JSON consistency:** 2-space indent, UTF-8 encoding, automatic parent directory creation
7. **Frame counting accuracy:** Use ffprobe `-count_frames` for accurate results (not metadata estimation)
8. **Custom exception:** VideoAnalysisError provides clear diagnostics for video processing failures

## Dependencies

- Standard library only: `hashlib`, `pathlib`, `subprocess`, `json`, `logging`
- No external packages required

## Usage Examples

### Compute deterministic config hash

```python
from w2t_bkin.utils import compute_hash
import json

# Hash a dictionary directly
config_data = {"project": {"name": "test"}, "paths": {}}
hash_val = compute_hash(config_data)  # Automatically canonicalized

# Or hash a string
config_str = json.dumps(config_data, sort_keys=True)
hash_val2 = compute_hash(config_str)

assert hash_val == hash_val2  # Both produce same hash
```

### Safe path handling

```python
from w2t_bkin.utils import sanitize_path
from pathlib import Path

# OK - relative path
safe = sanitize_path("data/raw/session001/video.avi")

# OK - with base directory restriction
safe = sanitize_path("video.avi", base=Path("/data/raw"))

# Raises ValueError - directory traversal
try:
    unsafe = sanitize_path("../../../etc/passwd")
except ValueError as e:
    print(f"Rejected: {e}")
```

### Extract video frame count

```python
from w2t_bkin.utils import run_ffprobe, VideoAnalysisError
from pathlib import Path

video_path = Path("data/raw/cam0.avi")

try:
    frame_count = run_ffprobe(video_path)
    print(f"Video has {frame_count} frames")
except VideoAnalysisError as e:
    print(f"Failed to analyze video: {e}")
except FileNotFoundError:
    print(f"Video file not found: {video_path}")
```

### JSON I/O with Path objects

```python
from w2t_bkin.utils import write_json, read_json
from pathlib import Path

# Write data with Path objects
data = {
    "session_id": "Session-001",
    "video_path": Path("/data/raw/video.avi"),  # Path automatically converted
    "config": {"threshold": 0.9}
}

write_json(data, "output/manifest.json")  # Creates output/ if needed

# Read back
loaded = read_json("output/manifest.json")
print(loaded["video_path"])  # String: "/data/raw/video.avi"
```

### Configure logging

```python
from w2t_bkin.utils import configure_logger

# Standard logging
logger = configure_logger("w2t_bkin.ingest", level="DEBUG")
logger.info("Processing started")
logger.warning("Frame mismatch detected")

# Structured (JSON) logging
json_logger = configure_logger("w2t_bkin", level="INFO", structured=True)
json_logger.info("Pipeline complete")
# Output: {"timestamp":"2025-11-12 12:00:00","level":"INFO","name":"w2t_bkin","message":"Pipeline complete"}
```

## Performance Notes

- **Hashing:** O(n) in data size, fast for typical config files (<1ms)
- **ffprobe:** Uses `-count_frames` for accuracy (~100-500ms per video, scales with video size)
- **Path operations:** O(1), filesystem operations cached by OS
- **JSON I/O:** O(n) in data size with custom Path encoder overhead

## Thread Safety

All utils functions are thread-safe and reentrant. No shared mutable state.

## Related Modules

- **domain:** Uses utils for model validation helpers
- **config:** Uses utils for hash computation
- **ingest:** Uses utils for ffprobe and path operations
- **All modules:** Use utils for logging

## Further Reading

- [Design document](../../design.md#security--privacy) - Path sanitization rationale
- [NFR-1 Reproducibility](../../requirements.md#non-functional-requirements-nfr) - Hash determinism requirements
