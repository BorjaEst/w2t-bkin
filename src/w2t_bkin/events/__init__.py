"""Events module for W2T-BKIN pipeline (Phase 3 - Behavioral Data).

This package provides behavioral data parsing and extraction utilities organized by functional area:

- **exceptions**: Error types (EventsError, BpodParseError, BpodValidationError)
- **bpod**: Bpod file I/O (parse, discover, merge, validate, index, write)
- **trials**: Trial extraction and outcome inference
- **behavior**: Behavioral event extraction
- **summary**: QC summary creation and persistence

Public API:
-----------
All public functions are re-exported at the package level for convenience:

    from w2t_bkin.events import (
        parse_bpod_mat,
        extract_trials,
        extract_behavioral_events,
        create_event_summary,
    )

See individual modules for detailed documentation.
"""

# Behavioral events
from .behavior import extract_behavioral_events

# Bpod file operations
from .bpod import discover_bpod_files, index_bpod_data, merge_bpod_sessions, parse_bpod_mat, parse_bpod_session, split_bpod_data, validate_bpod_structure, write_bpod_mat

# Exceptions
from .exceptions import BpodParseError, BpodValidationError, EventsError

# QC summary
from .summary import create_event_summary, write_event_summary

# Trial extraction
from .trials import extract_trials

__all__ = [
    # Exceptions
    "EventsError",
    "BpodParseError",
    "BpodValidationError",
    # Bpod operations
    "parse_bpod_mat",
    "discover_bpod_files",
    "merge_bpod_sessions",
    "parse_bpod_session",
    "validate_bpod_structure",
    "index_bpod_data",
    "split_bpod_data",
    "write_bpod_mat",
    # Trial extraction
    "extract_trials",
    # Behavioral events
    "extract_behavioral_events",
    # Summary
    "create_event_summary",
    "write_event_summary",
]
