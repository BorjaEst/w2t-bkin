"""Load TTL pulse timestamps from text files.

Provides hardware-agnostic TTL pulse loading for cameras, behavioral
equipment, and neural recordings.

Example:
    >>> from pathlib import Path
    >>> ttl_patterns = {"ttl_camera": "TTLs/cam*.txt"}
    >>> ttl_pulses = get_ttl_pulses(ttl_patterns, Path("data/session"))
"""

import glob
import logging
from pathlib import Path
from typing import Dict, List

from ..exceptions import SyncError

__all__ = ["get_ttl_pulses", "load_ttl_file"]

logger = logging.getLogger(__name__)


def load_ttl_file(path: Path) -> List[float]:
    """Load TTL timestamps from a file.

    Expects one timestamp per line in seconds.

    Args:
        path: Path to TTL file

    Returns:
        List of timestamps

    Raises:
        SyncError: File not found or read error
    """
    if not path.exists():
        raise SyncError(f"TTL file not found: {path}")

    timestamps = []

    try:
        with open(path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    timestamps.append(float(line))
                except ValueError:
                    logger.warning(f"Skipping invalid TTL timestamp in {path.name} line {line_num}: {line}")
    except Exception as e:
        raise SyncError(f"Failed to read TTL file {path}: {e}")

    return timestamps


def get_ttl_pulses(ttl_patterns: Dict[str, str], session_dir: Path) -> Dict[str, List[float]]:
    """Load TTL pulses from multiple files using glob patterns.

    Args:
        ttl_patterns: Dict mapping TTL ID to glob pattern
        session_dir: Base directory for patterns

    Returns:
        Dict mapping TTL ID to sorted timestamp list

    Raises:
        SyncError: Parse failed

    Example:
        >>> ttl_patterns = {"ttl_camera": "TTLs/cam*.txt"}
        >>> ttl_pulses = get_ttl_pulses(ttl_patterns, Path("data/session"))
    """
    session_dir = Path(session_dir)
    ttl_pulses = {}

    for ttl_id, pattern_str in ttl_patterns.items():
        # Resolve glob pattern
        pattern = str(session_dir / pattern_str)
        ttl_files = sorted(glob.glob(pattern))

        if not ttl_files:
            logger.warning(f"No TTL files found for '{ttl_id}' with pattern: {pattern}")
            ttl_pulses[ttl_id] = []
            continue

        # Load and merge timestamps from all files
        timestamps = []
        for ttl_file in ttl_files:
            path = Path(ttl_file)
            file_timestamps = load_ttl_file(path)
            timestamps.extend(file_timestamps)

        # Sort timestamps and store
        ttl_pulses[ttl_id] = sorted(timestamps)
        logger.debug(f"Loaded {len(timestamps)} TTL pulses for '{ttl_id}' from {len(ttl_files)} file(s)")

    return ttl_pulses
