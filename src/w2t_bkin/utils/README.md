---
post_title: "Utils Module — Foundation Utilities (W2T BKin)"
author1: "Project Team"
post_slug: "utils-module-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "utils"]
tags: ["utils", "foundation", "helpers"]
ai_note: "Generated from design and API specifications."
summary: "Foundation utilities module providing JSON/CSV I/O, file hashing, git provenance, timing, and logging configuration for the W2T BKin pipeline."
post_date: "2025-11-09"
---

# Utils Module — Foundation Utilities

## 1. Overview

The `w2t_bkin.utils` module provides foundational utility functions used across all pipeline stages. As a Layer 0 foundation module, it **must not import** any other project packages, ensuring zero circular dependencies.

**Design Principle**: Pure, stateless helper functions with no side effects beyond I/O operations.

## 2. Module Purpose

According to the design (`design.md` §2, §21.1):

- Provides reusable primitives for file I/O, hashing, provenance capture, timing, and logging
- Acts as a foundation layer (Layer 0) with no dependencies on other project packages
- Supports reproducibility (NFR-1), observability (NFR-3), and provenance (NFR-11)

## 3. Public API

### 3.1 JSON I/O

```python
def read_json(path: Path | str) -> dict[str, Any]:
    """Read JSON file and return parsed dictionary.
    
    Args:
        path: Absolute or relative path to JSON file
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        FileNotFoundError: If file does not exist
        JSONDecodeError: If file contains invalid JSON
        
    Requirements: NFR-3 (Observability), Design §8
    """

def write_json(path: Path | str, obj: dict[str, Any], indent: int = 2) -> None:
    """Write dictionary to JSON file with pretty formatting.
    
    Args:
        path: Target file path
        obj: Dictionary to serialize
        indent: Indentation level (default: 2)
        
    Raises:
        OSError: If write operation fails
        
    Requirements: NFR-3 (Observability), Design §8
    """
```

### 3.2 CSV I/O

```python
def write_csv(path: Path | str, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    """Write rows to CSV file with explicit field ordering.
    
    Args:
        path: Target CSV file path
        rows: List of dictionaries representing table rows
        fieldnames: Optional explicit column order (default: keys from first row)
        
    Raises:
        ValueError: If rows is empty and fieldnames not provided
        OSError: If write operation fails
        
    Requirements: Design §3.2 (Timestamp CSV), Design §3.5 (Trials CSV)
    """
```

### 3.3 File Hashing

```python
def file_hash(path: Path | str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Compute content hash of file for caching and provenance.
    
    Args:
        path: File to hash
        algorithm: Hash algorithm (default: sha256)
        chunk_size: Read chunk size in bytes
        
    Returns:
        Hexadecimal hash digest
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If algorithm not supported
        
    Requirements: NFR-1 (Reproducibility), NFR-8 (Data integrity), NFR-11 (Provenance)
    """
```

### 3.4 Git Provenance

```python
def get_commit() -> str:
    """Retrieve current Git commit hash for provenance capture.
    
    Returns:
        Git commit SHA (short form, 7 chars), or "unknown" if not in git repo
        
    Requirements: NFR-11 (Provenance), Design §11
    """
```

### 3.5 Timing Utilities

```python
@contextmanager
def time_block(label: str, logger: logging.Logger | None = None) -> Iterator[None]:
    """Context manager for timing code blocks with optional logging.
    
    Args:
        label: Descriptive label for timed block
        logger: Optional logger instance (if None, prints to stdout)
        
    Yields:
        None (used as context manager)
        
    Example:
        with time_block("Video decoding"):
            decode_video(path)
        # Output: "Video decoding completed in 12.34s"
        
    Requirements: NFR-3 (Observability), NFR-4 (Performance), Design §7
    """
```

### 3.6 Logging Configuration

```python
def configure_logging(level: str = "INFO", structured: bool = False) -> None:
    """Configure root logger with standardized format.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        structured: Enable JSON structured logging (default: False)
        
    Requirements: NFR-3 (Observability), Design §7
    """
```

## 4. Design Constraints

### 4.1 No Internal Dependencies

As a Layer 0 foundation module, `utils` **must not import**:
- `w2t_bkin.config`
- `w2t_bkin.domain`
- Any processing stage (`ingest`, `sync`, `pose`, etc.)

Only external libraries and Python standard library are allowed.

### 4.2 Stateless Functions

All functions should be:
- **Pure** where possible (deterministic outputs for given inputs)
- **Stateless** (no module-level mutable state)
- **Thread-safe** (safe for concurrent use)

### 4.3 Error Handling

- Raise standard Python exceptions (`FileNotFoundError`, `ValueError`, `OSError`)
- Do not use custom pipeline exceptions from `domain` (to avoid circular dependency)
- Include descriptive error messages with file paths when applicable

## 5. Testing Strategy

Unit tests for `utils` (see `tests/unit/test_utils.py`):

1. **JSON I/O**: Round-trip serialization, error handling for malformed JSON
2. **CSV I/O**: Field ordering, empty input handling, special characters
3. **File Hashing**: Consistency across runs, algorithm validation, large file handling
4. **Git Provenance**: Repository detection, fallback to "unknown"
5. **Timing**: Accuracy of elapsed time measurement, logger integration
6. **Logging**: Configuration validation, structured format toggle

## 6. Usage Examples

### Manifest Persistence (Ingest Stage)

```python
from w2t_bkin.utils import write_json, file_hash

manifest_data = {...}  # Manifest dict
write_json(output_dir / "manifest.json", manifest_data)

# Optional: compute hash for caching
manifest_hash = file_hash(output_dir / "manifest.json")
```

### Timestamp CSV Export (Sync Stage)

```python
from w2t_bkin.utils import write_csv

timestamps = [
    {"frame_index": 0, "timestamp": 0.0000},
    {"frame_index": 1, "timestamp": 0.0333},
    ...
]
write_csv(output_dir / "timestamps_cam0.csv", timestamps, fieldnames=["frame_index", "timestamp"])
```

### Performance Profiling (Any Stage)

```python
from w2t_bkin.utils import time_block
import logging

logger = logging.getLogger(__name__)

with time_block("TTL parsing", logger=logger):
    parse_ttl_logs(sync_files)
```

### Provenance Capture (NWB Stage)

```python
from w2t_bkin.utils import get_commit

provenance = {
    "git_commit": get_commit(),
    "pipeline_version": "0.1.0",
    "timestamp": datetime.now().isoformat()
}
```

## 7. Dependencies

**Standard Library Only**:
- `json` — JSON serialization
- `csv` — CSV I/O
- `hashlib` — File hashing
- `pathlib` — Path handling
- `subprocess` — Git command execution
- `time`, `contextlib` — Timing utilities
- `logging` — Logging configuration

**No External Dependencies** — `utils` must remain lightweight.

## 8. Maintenance Notes

- Keep functions focused and single-purpose
- Avoid feature creep (complex transformations belong in stage modules)
- Document all public functions with Requirements/Design traceability
- Maintain 100% unit test coverage

## 9. Related Documentation

- **Design**: `/design.md` §8 (Performance), §7 (Logging), §11 (Provenance)
- **API**: `/api.md` §3.2 (Utils Module API)
- **Tests**: `/tests/unit/test_utils.py`

---

**Last Updated**: 2025-11-09  
**Status**: Foundation module (Layer 0)
