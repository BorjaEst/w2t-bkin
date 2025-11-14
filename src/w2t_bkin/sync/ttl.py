"""Generic TTL pulse loading utilities.

These utilities are hardware-agnostic and can be used for:
- Video camera synchronization TTLs
- Behavioral synchronization TTLs (Bpod, etc.)
- Neural recording synchronization TTLs
- Any other hardware sync signals

Example:
    >>> from w2t_bkin.sync import get_ttl_pulses
    >>> from w2t_bkin.config import load_session
    >>>
    >>> session = load_session("data/session.toml")
    >>> ttl_pulses = get_ttl_pulses(session)
    >>> print(f"Camera TTL: {len(ttl_pulses['ttl_camera'])} pulses")
    >>> print(f"Bpod TTL: {len(ttl_pulses['ttl_bpod'])} pulses")
"""

import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..domain import Session
from .exceptions import SyncError

__all__ = ["get_ttl_pulses", "load_ttl_file"]

logger = logging.getLogger(__name__)


def load_ttl_file(path: Path) -> List[float]:
    """Load TTL pulse timestamps from a single file.

    TTL files should contain one timestamp per line (in seconds).
    Empty lines and parsing errors are logged but don't stop processing.

    Args:
        path: Path to TTL file

    Returns:
        List of timestamps (unsorted)

    Raises:
        SyncError: If file cannot be read

    Example:
        >>> from pathlib import Path
        >>> timestamps = load_ttl_file(Path("data/ttl_camera.txt"))
        >>> print(f"Loaded {len(timestamps)} TTL pulses")
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


def get_ttl_pulses(session: Session, session_dir: Optional[Path] = None) -> Dict[str, List[float]]:
    """Load TTL pulse timestamps from session configuration (generic).

    This function is hardware-agnostic and can load TTL pulses for any
    modality: video cameras, behavioral equipment (Bpod), neural recordings,
    or any other synchronized hardware.

    Discovers TTL files matching glob patterns in session.TTLs and parses
    timestamps from each file. Returns a dictionary mapping TTL channel IDs
    to sorted lists of absolute timestamps.

    Args:
        session: Session configuration with TTL definitions
        session_dir: Base directory for resolving TTL glob patterns.
                    If None, uses session.session_dir.

    Returns:
        Dictionary mapping TTL ID to list of absolute timestamps (sorted).
        Empty list if no files found for a TTL channel.

    Raises:
        SyncError: If TTL files cannot be parsed

    Example:
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/raw/Session-001/session.toml")
        >>>
        >>> # Load all TTL channels
        >>> ttl_pulses = get_ttl_pulses(session)
        >>>
        >>> # Access specific channels
        >>> camera_ttls = ttl_pulses.get("ttl_camera", [])
        >>> bpod_ttls = ttl_pulses.get("ttl_bpod", [])
        >>>
        >>> print(f"Camera: {len(camera_ttls)} pulses")
        >>> print(f"Bpod: {len(bpod_ttls)} pulses")
    """
    if session_dir is None:
        session_dir = Path(session.session_dir)
    else:
        session_dir = Path(session_dir)

    ttl_pulses = {}

    for ttl_config in session.TTLs:
        # Resolve glob pattern
        pattern = str(session_dir / ttl_config.paths)
        ttl_files = sorted(glob.glob(pattern))

        if not ttl_files:
            logger.warning(f"No TTL files found for '{ttl_config.id}' with pattern: {pattern}")
            ttl_pulses[ttl_config.id] = []
            continue

        # Load and merge timestamps from all files
        timestamps = []
        for ttl_file in ttl_files:
            path = Path(ttl_file)
            file_timestamps = load_ttl_file(path)
            timestamps.extend(file_timestamps)

        # Sort timestamps and store
        ttl_pulses[ttl_config.id] = sorted(timestamps)
        logger.debug(f"Loaded {len(timestamps)} TTL pulses for '{ttl_config.id}' from {len(ttl_files)} file(s)")

    return ttl_pulses
