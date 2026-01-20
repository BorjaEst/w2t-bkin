"""Public TTL API.

This module provides the stable public import path for TTL pulse loading and
conversion to ndx-events `EventsTable`.

Implementation lives in `w2t_bkin.ingest.events`.
"""

from __future__ import annotations

from w2t_bkin.ingest.events import EventsTable, TTLError, add_ttl_table_to_nwb, extract_ttl_table, get_ttl_pulses, load_ttl_file  # noqa: F401

__all__ = [
    "EventsTable",
    "TTLError",
    "add_ttl_table_to_nwb",
    "extract_ttl_table",
    "get_ttl_pulses",
    "load_ttl_file",
]
