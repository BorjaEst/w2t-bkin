"""TTL hardware signals: loading, processing, and NWB integration.

This module handles TTL (Transistor-Transistor Logic) pulse timestamps from
hardware synchronization signals, providing functions to load from files and
convert to standardized NWB EventsTable format using ndx-events.

Public API
----------
from w2t_bkin.ingest.ttl import (
    # Loading functions (migrated from sync.ttl)
    load_ttl_file,
    get_ttl_pulses,

    # NWB integration (ndx-events)
    extract_ttl_table,
    add_ttl_table_to_nwb,

    # ndx-events types
    EventsTable,

    # Exceptions
    TTLError,
)

Usage Example
-------------
```python
from w2t_bkin.ingest.ttl import get_ttl_pulses, extract_ttl_table

# Load TTL pulses from files
ttl_patterns = {"ttl_camera": "TTLs/cam*.txt", "ttl_cue": "TTLs/cue*.txt"}
ttl_pulses = get_ttl_pulses(session_dir, ttl_patterns)

# Extract TTL descriptions from config
ttl_descriptions = {ttl.id: ttl.description for ttl in session.TTLs}

# Create EventsTable
ttl_table = extract_ttl_table(ttl_pulses, descriptions=ttl_descriptions)

# Add to NWBFile
nwbfile.add_acquisition(ttl_table)
```

Requirements
------------
- FR-17: Hardware sync signal recording
- ndx-events~=0.4.0 (for EventsTable)
"""

"""Core functions for TTL pulse loading and NWB EventsTable conversion.

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
from typing import Dict, List, Optional, Protocol, Tuple

from ndx_events import EventsTable
import numpy as np
import pandas as pd
from pynwb import NWBFile

from w2t_bkin.exceptions import SyncError

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
) -> EventsTable:
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
    ttl_table = EventsTable.from_dataframe(
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


# =============================================================================
# Bpod Alignment (migrated from sync.behavior)
# =============================================================================


def get_sync_time_from_bpod_trial(trial_data: Dict, sync_signal: str) -> Optional[float]:
    """Extract sync signal start time from Bpod trial.

    Args:
        trial_data: Trial data with States structure
        sync_signal: State name (e.g. "W2L_Audio")

    Returns:
        Start time relative to trial start, or None if not found
    """
    from w2t_bkin.utils import convert_matlab_struct, is_nan_or_none

    # Convert MATLAB struct to dict if needed
    trial_data = convert_matlab_struct(trial_data)

    states = trial_data.get("States", {})
    if not states:
        return None

    # Convert states to dict if it's a MATLAB struct
    states = convert_matlab_struct(states)

    sync_times = states.get(sync_signal)
    if sync_times is None:
        return None

    if not isinstance(sync_times, (list, tuple, np.ndarray)) or len(sync_times) < 2:
        return None

    start_time = sync_times[0]
    if is_nan_or_none(start_time):
        return None

    return float(start_time)


class BpodTrialTypeProtocol(Protocol):
    """Protocol for Bpod trial type configuration access.

    Defines minimal interface needed by sync.ttl module without
    importing from domain.session.BpodTrialType.

    Attributes:
        trial_type: Trial type identifier
        sync_signal: Bpod state/event name for alignment
        sync_ttl: TTL channel ID for sync pulses
        description: Human-readable description
    """

    trial_type: int
    sync_signal: str
    sync_ttl: str
    description: str


def align_bpod_trials_to_ttl(
    trial_type_configs: List[BpodTrialTypeProtocol],
    bpod_data: Dict,
    ttl_pulses: Dict[str, List[float]],
) -> Tuple[Dict[int, float], List[str]]:
    """Align Bpod trials to absolute time using TTL sync signals (low-level, Session-free).

    Converts Bpod relative timestamps to absolute time by matching per-trial
    sync signals to corresponding TTL pulses. Returns per-trial offsets that
    can be used with events.extract_trials() and events.extract_behavioral_events()
    to convert relative timestamps to absolute timestamps.

    Args:
        trial_type_configs: List of trial type sync configurations
                           (from session.bpod.trial_types)
        bpod_data: Parsed Bpod data (SessionData structure from events.parse_bpod)
        ttl_pulses: Dict mapping TTL channel ID to sorted list of absolute timestamps
                    (typically from w2t_bkin.ttl.get_ttl_pulses)

    Returns:
        Tuple of:
        - trial_offsets: Dict mapping trial_number → absolute time offset
        - warnings: List of warning messages for trials that couldn't be aligned

    Raises:
        SyncError: If trial_type config missing or data structure invalid
    """
    from w2t_bkin.utils import convert_matlab_struct, to_scalar

    # Validate Bpod structure
    if "SessionData" not in bpod_data:
        raise SyncError("Invalid Bpod structure: missing SessionData")

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials to align")
        return {}, []

    # Build trial_type → sync config mapping
    trial_type_map = {}
    for tt_config in trial_type_configs:
        trial_type_map[tt_config.trial_type] = {
            "sync_signal": tt_config.sync_signal,
            "sync_ttl": tt_config.sync_ttl,
        }

    if not trial_type_map:
        raise SyncError("No trial_type sync configuration provided in trial_type_configs")

    # Prepare TTL pulse pointers (track consumption per channel)
    ttl_pointers = {ttl_id: 0 for ttl_id in ttl_pulses.keys()}

    # Extract raw events
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    # Extract TrialTypes if available
    trial_types_array = session_data.get("TrialTypes")
    if trial_types_array is None:
        # Default to trial_type 1 for all trials if not specified
        trial_types_array = [1] * n_trials
        logger.warning("TrialTypes not found in Bpod data, defaulting all trials to type 1")

    trial_offsets = {}
    warnings_list = []

    for i in range(n_trials):
        trial_num = i + 1
        trial_data = convert_matlab_struct(trial_data_list[i])

        # Get trial type (handle numpy arrays)
        trial_type = int(to_scalar(trial_types_array, i))

        if trial_type not in trial_type_map:
            warnings_list.append(f"Trial {trial_num}: trial_type {trial_type} not in session config, skipping")
            logger.warning(warnings_list[-1])
            continue

        sync_config = trial_type_map[trial_type]
        sync_signal = sync_config["sync_signal"]
        sync_ttl_id = sync_config["sync_ttl"]

        # Extract sync time from trial (relative to trial start)
        sync_time_rel = get_sync_time_from_bpod_trial(trial_data, sync_signal)
        if sync_time_rel is None:
            warnings_list.append(f"Trial {trial_num}: sync_signal '{sync_signal}' not found or not visited, skipping")
            logger.warning(warnings_list[-1])
            continue

        # Get next TTL pulse
        if sync_ttl_id not in ttl_pulses:
            warnings_list.append(f"Trial {trial_num}: TTL channel '{sync_ttl_id}' not found in ttl_pulses, skipping")
            logger.error(warnings_list[-1])
            continue

        ttl_channel = ttl_pulses[sync_ttl_id]
        ttl_ptr = ttl_pointers[sync_ttl_id]

        if ttl_ptr >= len(ttl_channel):
            warnings_list.append(f"Trial {trial_num}: No more TTL pulses available for '{sync_ttl_id}', skipping")
            logger.warning(warnings_list[-1])
            continue

        ttl_pulse_time = ttl_channel[ttl_ptr]
        ttl_pointers[sync_ttl_id] += 1

        # Get trial start timestamp from Bpod (may be non-zero after merge)
        trial_start_timestamp = float(to_scalar(session_data["TrialStartTimestamp"], i))

        # Compute offset: absolute_time = offset + TrialStartTimestamp
        # The sync signal occurs at: trial_start_timestamp + sync_time_rel (in Bpod timeline)
        # And should align to: ttl_pulse_time (in absolute timeline)
        # Therefore: offset + (trial_start_timestamp + sync_time_rel) = ttl_pulse_time
        offset_abs = ttl_pulse_time - (trial_start_timestamp + sync_time_rel)
        trial_offsets[trial_num] = offset_abs

        logger.debug(
            f"Trial {trial_num}: type={trial_type}, sync_signal={sync_signal}, "
            f"trial_start={trial_start_timestamp:.4f}s, sync_rel={sync_time_rel:.4f}s, "
            f"ttl_abs={ttl_pulse_time:.4f}s, offset={offset_abs:.4f}s"
        )  # fmt: skip

    # Warn about unused TTL pulses
    for ttl_id, ptr in ttl_pointers.items():
        unused = len(ttl_pulses[ttl_id]) - ptr
        if unused > 0:
            warnings_list.append(f"TTL channel '{ttl_id}' has {unused} unused pulses")
            logger.warning(warnings_list[-1])

    logger.info(f"Computed offsets for {len(trial_offsets)} out of {n_trials} trials using TTL sync")
    return trial_offsets, warnings_list
