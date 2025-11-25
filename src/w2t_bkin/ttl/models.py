"""Re-export ndx-events types for TTL signal integration.

This module provides convenient access to ndx-events types used for
hardware synchronization signal recording.

Types
-----
- EventsTable: Table for timestamped events with metadata

Requirements
------------
- ndx-events~=0.4.0 (already in dependencies)
"""

from ndx_events import EventsTable

__all__ = [
    "EventsTable",
]
