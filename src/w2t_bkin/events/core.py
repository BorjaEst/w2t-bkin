"""Core functions for converting TTL pulses to ndx-events EventsTable objects.

Provides conversion from raw TTL timestamp dictionaries to structured NWB-compatible
event tables using the ndx-events extension. Optimized for large datasets (camera frames).

Functions
---------
- create_events_table_from_ttls: EventsTable from TTL pulses with channel metadata
- add_events_to_nwb: Helper to add EventsTable to NWBFile

Performance
-----------
Uses numpy vectorized operations for efficient handling of large TTL datasets
(e.g., camera frames with 10k+ timestamps per session).

Example
-------
>>> from w2t_bkin.events import create_events_table_from_ttls
>>> from w2t_bkin.sync import get_ttl_pulses
>>>
>>> # Load TTL pulses
>>> ttl_patterns = {"ttl_camera": "TTLs/cam*.txt"}
>>> ttl_pulses = get_ttl_pulses(ttl_patterns, Path("data/session"))
>>>
>>> # Create EventsTable (optimized for large datasets)
>>> events_table = create_events_table_from_ttls(
...     ttl_pulses,
...     descriptions={"ttl_camera": "Camera frame sync (30 Hz)"}
... )
>>>
>>> # Add to NWBFile
>>> nwbfile.add_events_table(events_table)
"""

import logging
from typing import Dict, List, Optional

import numpy as np
from ndx_events import EventsTable
from pynwb import NWBFile

logger = logging.getLogger(__name__)


class EventsError(Exception):
    """Exception raised for TTL events processing errors."""

    pass


def create_events_table_from_ttls(
    ttl_pulses: Dict[str, List[float]],
    name: str = "TTLEvents",
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
) -> EventsTable:
    """Create EventsTable from TTL pulse timestamps.

    Converts a dictionary of TTL pulse timestamps into an ndx-events EventsTable
    with one row per pulse. Includes channel ID, description, and source metadata
    via custom columns. Optimized for large datasets using numpy vectorization.

    Performance: Handles 10k+ events efficiently (O(n log n) for sorting).

    Args:
        ttl_pulses: Dict mapping TTL ID to list of timestamps (seconds)
        name: Name for the EventsTable container
        descriptions: Optional dict mapping TTL ID to description string
        sources: Optional dict mapping TTL ID to source device/system

    Returns:
        EventsTable with all TTL pulses as events, sorted by timestamp

    Raises:
        EventsError: If ttl_pulses is empty or all channels are empty

    Example:
        >>> ttl_pulses = {
        ...     "ttl_camera": [0.0, 0.033, 0.066],  # Camera frames
        ...     "ttl_cue": [1.0, 3.0, 5.0]          # Behavioral cues
        ... }
        >>> table = create_events_table_from_ttls(
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera sync", "ttl_cue": "Cue trigger"},
        ...     sources={"ttl_camera": "FLIR Blackfly", "ttl_cue": "Bpod"}
        ... )
        >>> len(table.timestamp)  # Total pulses across all channels
        6
    """
    if not ttl_pulses:
        raise EventsError("ttl_pulses dictionary is empty")

    descriptions = descriptions or {}
    sources = sources or {}

    # Pre-compute total size for efficient array allocation
    total_events = sum(len(timestamps) for timestamps in ttl_pulses.values())
    if total_events == 0:
        raise EventsError("No valid TTL pulses found in any channel")

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
        all_descriptions[offset : offset + n] = descriptions.get(
            ttl_id, f"TTL pulses from {ttl_id}"
        )
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

    # Create EventsTable with custom columns
    events_table = EventsTable(
        name=name,
        description=f"Hardware TTL pulse events from {len(ttl_pulses)} channels, {offset} total pulses",
    )

    # Add custom columns for metadata
    events_table.add_column(
        name="channel",
        description="TTL channel identifier",
    )
    events_table.add_column(
        name="ttl_description",
        description="Description of the TTL channel",
    )
    events_table.add_column(
        name="source",
        description="Source device or system generating the TTL signal",
    )

    # Add all rows efficiently (EventsTable handles timestamp column automatically)
    for timestamp, channel, description, source in zip(
        sorted_timestamps, sorted_channels, sorted_descriptions, sorted_sources
    ):
        events_table.add_row(
            timestamp=float(timestamp),
            channel=str(channel),
            ttl_description=str(description),
            source=str(source),
        )

    logger.info(
        f"Created EventsTable '{name}' with {offset} events from {len(ttl_pulses)} TTL channels"
    )

    return events_table


def add_events_to_nwb(
    nwbfile: NWBFile,
    ttl_pulses: Dict[str, List[float]],
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
    container_name: str = "TTLEvents",
) -> NWBFile:
    """Add TTL events to NWBFile as EventsTable.

    Convenience function that creates an EventsTable and adds it to the NWBFile
    events collection using nwbfile.add_events_table().

    Args:
        nwbfile: NWBFile to add events to
        ttl_pulses: Dict mapping TTL ID to timestamps
        descriptions: Optional channel descriptions
        sources: Optional source device/system names
        container_name: Name for the events container

    Returns:
        Modified NWBFile with events added

    Example:
        >>> from pynwb import NWBFile
        >>> from w2t_bkin.events import add_events_to_nwb
        >>> from w2t_bkin.sync import get_ttl_pulses
        >>>
        >>> nwbfile = NWBFile(...)
        >>> ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)
        >>> nwbfile = add_events_to_nwb(
        ...     nwbfile,
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera sync"},
        ...     sources={"ttl_camera": "FLIR Blackfly"}
        ... )
    """
    events_table = create_events_table_from_ttls(
        ttl_pulses,
        name=container_name,
        descriptions=descriptions,
        sources=sources,
    )

    nwbfile.add_acquisition(events_table)

    logger.info(f"Added EventsTable '{container_name}' to NWBFile acquisition")

    return nwbfile
