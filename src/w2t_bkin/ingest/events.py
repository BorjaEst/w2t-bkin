"""TTL pulse loading and NWB EventsTable conversion.

Provides TTL timestamp loading from text files and conversion to structured
NWB-compatible event tables using the ndx-events extension. Optimized for
large datasets (camera frames with 10k+ timestamps).

Functions
---------
- load_ttl_file: Load timestamps from a single TTL file
- get_ttl_pulses: Load TTL pulses from multiple files using glob patterns
- extract_ttl_table: Convert TTL pulses to ndx-events EventsTable
- add_ttl_table_to_nwb: Helper to add TTL EventsTable to NWBFile

Performance
-----------
Uses numpy vectorized operations for efficient handling of large TTL datasets.
Tested with 10k+ events in <60s.

Example
-------
>>> from pathlib import Path
>>> from w2t_bkin.ttl import get_ttl_pulses, extract_ttl_table
>>>
>>> # Load TTL pulses
>>> ttl_patterns = {"ttl_camera": "TTLs/cam*.txt"}
>>> ttl_pulses = get_ttl_pulses(Path("data/session"), ttl_patterns)
>>>
>>> # Create EventsTable
>>> ttl_table = extract_ttl_table(
...     ttl_pulses,
...     descriptions={"ttl_camera": "Camera frame sync (30 Hz)"}
... )
>>>
>>> # Add to NWBFile
>>> nwbfile.add_acquisition(ttl_table)
"""

import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ndx_events import SignalsTable as TTLEventsTable
import numpy as np
import pandas as pd
from pynwb import NWBFile

logger = logging.getLogger(__name__)


class TTLError(Exception):
    """Exception raised for TTL processing errors."""

    pass


# =============================================================================
# TTL File Loading (migrated from sync.ttl)
# =============================================================================


def load_ttl_file(path: Path) -> List[float]:
    """Load TTL timestamps from a single file.

    Expects one timestamp per line in seconds (floating-point format).

    Args:
        path: Path to TTL file

    Returns:
        List of timestamps in seconds

    Raises:
        TTLError: File not found or read error

    Example:
        >>> from pathlib import Path
        >>> timestamps = load_ttl_file(Path("TTLs/cam0.txt"))
        >>> print(f"Loaded {len(timestamps)} TTL pulses")
    """
    if not path.exists():
        raise TTLError(f"TTL file not found: {path}")

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
                    logger.warning(f"Skipping invalid TTL timestamp in {path.name} " f"line {line_num}: {line}")
    except Exception as e:
        raise TTLError(f"Failed to read TTL file {path}: {e}")

    return timestamps


def get_ttl_pulses(session_dir: Path, ttl_patterns: Dict[str, str]) -> Dict[str, List[float]]:
    """Load TTL pulses from multiple files using glob patterns.

    Discovers and loads TTL files matching glob patterns, merging timestamps
    from multiple files per channel and sorting chronologically.

    Args:
        session_dir: Base directory for resolving patterns
        ttl_patterns: Dict mapping TTL ID to glob pattern
                     (e.g., {"ttl_camera": "TTLs/cam*.txt"})

    Returns:
        Dict mapping TTL ID to sorted timestamp list

    Raises:
        TTLError: File read failed

    Example:
        >>> from pathlib import Path
        >>> ttl_patterns = {
        ...     "ttl_camera": "TTLs/*cam*.txt",
        ...     "ttl_cue": "TTLs/*cue*.txt"
        ... }
        >>> ttl_pulses = get_ttl_pulses(Path("data/Session-000001"), ttl_patterns)
        >>> print(f"Camera: {len(ttl_pulses['ttl_camera'])} pulses")
    """
    session_dir = Path(session_dir)
    ttl_pulses = {}

    for ttl_id, pattern_str in ttl_patterns.items():
        # Resolve glob pattern relative to session directory
        pattern = str(session_dir / pattern_str)
        ttl_files = sorted(glob.glob(pattern))

        if not ttl_files:
            logger.warning(f"No TTL files found for '{ttl_id}' with pattern: {pattern}")
            ttl_pulses[ttl_id] = []
            continue

        # Load and merge timestamps from all matching files
        timestamps = []
        for ttl_file in ttl_files:
            path = Path(ttl_file)
            file_timestamps = load_ttl_file(path)
            timestamps.extend(file_timestamps)

        # Sort chronologically and store
        ttl_pulses[ttl_id] = sorted(timestamps)
        logger.debug(f"Loaded {len(timestamps)} TTL pulses for '{ttl_id}' " f"from {len(ttl_files)} file(s)")

    return ttl_pulses


# =============================================================================
# NWB EventsTable Conversion (ndx-events integration)
# =============================================================================


def extract_ttl_table(
    ttl_pulses: Dict[str, List[float]],
    name: str = "TTLEvents",
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
) -> TTLEventsTable:
    """Extract EventsTable from TTL pulse timestamps.

    Converts a dictionary of TTL pulse timestamps into an ndx-events EventsTable
    with one row per pulse. Includes channel ID, description, and source metadata
    via custom columns. Optimized for large datasets using numpy vectorization.

    Performance: Handles 10k+ events efficiently (O(n log n) for sorting).

    Args:
        ttl_pulses: Dict mapping TTL ID to list of timestamps (seconds)
        name: Name for the EventsTable container (default: "TTLEvents")
        descriptions: Optional dict mapping TTL ID to description string
                     (typically from metadata.toml [[TTLs]].description)
        sources: Optional dict mapping TTL ID to source device/system

    Returns:
        EventsTable with all TTL pulses as events, sorted by timestamp

    Raises:
        TTLError: If ttl_pulses is empty or all channels are empty

    Example:
        >>> ttl_pulses = {
        ...     "ttl_camera": [0.0, 0.033, 0.066],  # Camera frames
        ...     "ttl_cue": [1.0, 3.0, 5.0]          # Behavioral cues
        ... }
        >>> ttl_table = extract_ttl_table(
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera sync", "ttl_cue": "Cue trigger"},
        ...     sources={"ttl_camera": "FLIR Blackfly", "ttl_cue": "Bpod"}
        ... )
        >>> len(ttl_table.timestamp)  # Total pulses across all channels
        6
    """
    if not ttl_pulses:
        raise TTLError("ttl_pulses dictionary is empty")

    descriptions = descriptions or {}
    sources = sources or {}

    # Pre-compute total size for efficient array allocation
    total_events = sum(len(timestamps) for timestamps in ttl_pulses.values())
    if total_events == 0:
        raise TTLError("No valid TTL pulses found in any channel")

    # Pre-allocate arrays for performance (avoids list appends)
    all_timestamps = np.empty(total_events, dtype=np.float64)
    all_channels = np.empty(total_events, dtype=object)
    all_descriptions = np.empty(total_events, dtype=object)
    all_sources = np.empty(total_events, dtype=object)

    # Fill arrays efficiently
    offset = 0
    for ttl_id in sorted(ttl_pulses.keys()):  # Deterministic order
        timestamps = ttl_pulses[ttl_id]
        if not timestamps:
            logger.warning(f"TTL channel '{ttl_id}' has no pulses, skipping")
            continue

        n = len(timestamps)
        all_timestamps[offset : offset + n] = timestamps
        all_channels[offset : offset + n] = ttl_id
        all_descriptions[offset : offset + n] = descriptions.get(ttl_id, f"TTL pulses from {ttl_id}")
        all_sources[offset : offset + n] = sources.get(ttl_id, "unknown")
        offset += n

    # Trim arrays if some channels were empty
    if offset < total_events:
        all_timestamps = all_timestamps[:offset]
        all_channels = all_channels[:offset]
        all_descriptions = all_descriptions[:offset]
        all_sources = all_sources[:offset]

    # Sort by timestamp (O(n log n), efficient for large datasets)
    sort_indices = np.argsort(all_timestamps)
    sorted_timestamps = all_timestamps[sort_indices]
    sorted_channels = all_channels[sort_indices]
    sorted_descriptions = all_descriptions[sort_indices]
    sorted_sources = all_sources[sort_indices]

    # Create DataFrame for bulk insertion (much faster than add_row loop)
    df = pd.DataFrame(
        {
            "timestamp": sorted_timestamps,
            "channel": sorted_channels,
            "ttl_description": sorted_descriptions,
            "source": sorted_sources,
        }
    )

    # Define column descriptions for EventsTable
    columns = [
        {"name": "channel", "description": "TTL channel identifier"},
        {"name": "ttl_description", "description": "Description of the TTL channel"},
        {"name": "source", "description": "Source device or system generating the TTL signal"},
    ]

    # Create EventsTable from DataFrame (bulk insertion - much faster than add_row)
    ttl_table = TTLEventsTable.from_dataframe(
        df=df,
        name=name,
        table_description=f"Hardware TTL pulse events from {len(ttl_pulses)} channels, {offset} total pulses",
        columns=columns,
    )

    logger.info(f"Created EventsTable '{name}' with {offset} events from {len(ttl_pulses)} TTL channels")

    return ttl_table


def add_ttl_table_to_nwb(
    nwbfile: NWBFile,
    ttl_pulses: Dict[str, List[float]],
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
    container_name: str = "TTLEvents",
) -> NWBFile:
    """Add TTL events to NWBFile as EventsTable.

    Convenience function that creates an EventsTable and adds it to the NWBFile
    acquisition section.

    Args:
        nwbfile: NWBFile to add TTL table to
        ttl_pulses: Dict mapping TTL ID to timestamps
        descriptions: Optional channel descriptions (from metadata.toml)
        sources: Optional source device/system names
        container_name: Name for the TTL table container (default: "TTLEvents")

    Returns:
        Modified NWBFile with TTL table added to acquisition

    Example:
        >>> from pynwb import NWBFile
        >>> from w2t_bkin.ttl import get_ttl_pulses, add_ttl_table_to_nwb
        >>>
        >>> nwbfile = NWBFile(...)
        >>> ttl_pulses = get_ttl_pulses(session_dir, ttl_patterns)
        >>> nwbfile = add_ttl_table_to_nwb(
        ...     nwbfile,
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera sync"},
        ...     sources={"ttl_camera": "FLIR Blackfly"}
        ... )
    """
    ttl_table = extract_ttl_table(
        ttl_pulses,
        name=container_name,
        descriptions=descriptions,
        sources=sources,
    )

    nwbfile.add_acquisition(ttl_table)

    logger.info(f"Added EventsTable '{container_name}' to NWBFile acquisition")

    return nwbfile
