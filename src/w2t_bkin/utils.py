"""Utility functions for W2T-BKIN pipeline (Phase 0).

Provides hashing, path sanitization, JSON I/O, and logging utilities.

Requirements: NFR-1, NFR-2, NFR-3
Acceptance: A18 (deterministic hashing)
"""

import hashlib
import json
import logging
from pathlib import Path
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
