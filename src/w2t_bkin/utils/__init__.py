"""Foundation utilities module for W2T BKin pipeline.

Provides reusable primitives for file I/O, hashing, provenance capture,
timing, and logging. As a Layer 0 foundation module, this package must
not import any other project packages.

Requirements: NFR-1, NFR-3, NFR-4, NFR-8, NFR-11
Design: design.md §2, §7, §8, §11, §21.1
API: api.md §3.2
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "read_json",
    "write_json",
    "write_csv",
    "file_hash",
    "get_commit",
    "time_block",
    "configure_logging",
]


# ============================================================================
# JSON I/O (NFR-3, Design §8)
# ============================================================================


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
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    path = Path(path)
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


# ============================================================================
# CSV I/O (Design §3.2, §3.5)
# ============================================================================


def write_csv(
    path: Path | str,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
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
    path = Path(path)
    
    # Validate inputs
    if not rows and fieldnames is None:
        raise ValueError("Cannot write CSV: rows is empty and no fieldnames provided")
    
    # Infer fieldnames from first row if not provided
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ============================================================================
# File Hashing (NFR-1, NFR-8, NFR-11)
# ============================================================================


def file_hash(
    path: Path | str,
    algorithm: str = "sha256",
    chunk_size: int = 8192,
) -> str:
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
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Validate algorithm
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from e
    
    # Hash file in chunks for memory efficiency
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


# ============================================================================
# Git Provenance (NFR-11, Design §11)
# ============================================================================


def get_commit() -> str:
    """Retrieve current Git commit hash for provenance capture.
    
    Returns:
        Git commit SHA (short form, 7 chars), or "unknown" if not in git repo
        
    Requirements: NFR-11 (Provenance), Design §11
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        
        return "unknown"
    
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown"


# ============================================================================
# Timing Utilities (NFR-3, NFR-4, Design §7)
# ============================================================================


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
    start_time = time.time()
    
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        message = f"{label} completed in {elapsed:.2f}s"
        
        if logger is not None:
            logger.info(message)
        else:
            print(message)


# ============================================================================
# Logging Configuration (NFR-3, Design §7)
# ============================================================================


def configure_logging(level: str = "INFO", structured: bool = False) -> None:
    """Configure root logger with standardized format.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        structured: Enable JSON structured logging (default: False)
        
    Requirements: NFR-3 (Observability), Design §7
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)
    
    # Set formatter based on structured flag
    if structured:
        # JSON structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"name": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Standard human-readable format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
