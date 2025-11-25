"""TTL hardware signals: loading, processing, and NWB integration.

This module handles TTL (Transistor-Transistor Logic) pulse timestamps from
hardware synchronization signals, providing functions to load from files and
convert to standardized NWB EventsTable format using ndx-events.

Public API
----------
from w2t_bkin.ttl import (
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
from w2t_bkin.ttl import get_ttl_pulses, extract_ttl_table

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

from .core import TTLError, add_ttl_table_to_nwb, extract_ttl_table, get_ttl_pulses, load_ttl_file
from .models import EventsTable

__all__ = [
    # Loading functions
    "load_ttl_file",
    "get_ttl_pulses",
    # NWB integration
    "extract_ttl_table",
    "add_ttl_table_to_nwb",
    # ndx-events types
    "EventsTable",
    # Exceptions
    "TTLError",
]
