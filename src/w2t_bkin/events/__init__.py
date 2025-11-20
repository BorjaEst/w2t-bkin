"""Behavioral data parsing and extraction from Bpod .mat files.

Provides low-level operations for:
- Parsing and merging Bpod .mat files
- Extracting trials with outcome inference
- Extracting behavioral events
- Creating QC summaries

Example:
    >>> from pathlib import Path
    >>> from w2t_bkin.events import parse_bpod_mat, extract_trials
    >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
    >>> trials = extract_trials(bpod_data)
"""

# Exceptions
from ..exceptions import BpodParseError, BpodValidationError, EventsError

# Behavioral events
from .behavior import extract_behavioral_events

# Bpod file operations
from .bpod import index_bpod_data, merge_bpod_sessions, parse_bpod, parse_bpod_from_files, parse_bpod_mat, split_bpod_data, validate_bpod_structure, write_bpod_mat

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
    "parse_bpod",
    "parse_bpod_mat",
    "merge_bpod_sessions",
    "parse_bpod_from_files",
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
