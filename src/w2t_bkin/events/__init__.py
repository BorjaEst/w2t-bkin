"""TTL hardware events integration using ndx-events.

This module converts TTL pulse timestamps into NWB-compatible EventsTable
objects using the ndx-events extension.

IMPORTANT: This is a NEW events module (Phase 4.5) for TTL signal integration.
NOT to be confused with the old deprecated events module (renamed to bpod in Phase 2).

Public API
----------
from w2t_bkin.events import (
    # ndx-events types (re-exported)
    EventsTable,
    CategoricalVectorData,
    MeaningsTable,
    
    # Core functions
    create_events_table_from_ttls,
    add_events_to_nwb,
)

Usage Example
-------------
```python
from w2t_bkin.events import create_events_table_from_ttls
from w2t_bkin.sync import get_ttl_pulses

# Load TTL pulses
ttl_patterns = {"ttl_camera": "TTLs/cam*.txt", "ttl_cue": "TTLs/cue*.txt"}
ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

# Create EventsTable
events_table = create_events_table_from_ttls(
    ttl_pulses,
    descriptions={
        "ttl_camera": "Camera frame sync pulses (30 Hz)",
        "ttl_cue": "Behavioral cue trigger pulses"
    }
)

# Add to NWBFile
nwbfile.add_events_table(events_table)
```

Requirements
------------
- FR-17: Hardware sync signal recording
- Phase 4.5: TTL events standardization
"""

from .core import (
    EventsError,
    add_events_to_nwb,
    create_events_table_from_ttls,
)
from .models import CategoricalVectorData, EventsTable, MeaningsTable

__all__ = [
    # ndx-events types
    "EventsTable",
    "CategoricalVectorData",
    "MeaningsTable",
    # Core functions
    "create_events_table_from_ttls",
    "add_events_to_nwb",
    # Exceptions
    "EventsError",
]
