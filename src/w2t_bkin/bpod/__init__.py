"""Behavioral data parsing from Bpod .mat files.

Provides low-level Bpod file operations:
- Parsing and merging Bpod .mat files
- Validating Bpod data structure
- File indexing and manipulation

For behavioral data extraction, use the behavior module with ndx-structured-behavior.

Example:
    >>> from pathlib import Path
    >>> from w2t_bkin.bpod import parse_bpod
    >>> from w2t_bkin.behavior import extract_trials_table
    >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
    >>> trials = extract_trials_table(bpod_data)
"""

# Exceptions
from ..exceptions import BpodParseError, BpodValidationError, EventsError

# Bpod file operations
from .core import index_bpod_data, merge_bpod_sessions, parse_bpod, parse_bpod_from_files, parse_bpod_mat, split_bpod_data, validate_bpod_structure, write_bpod_mat

__all__ = [
    # Exceptions
    "EventsError",
    "BpodParseError",
    "BpodValidationError",
    # Bpod file operations
    "parse_bpod",
    "parse_bpod_mat",
    "merge_bpod_sessions",
    "parse_bpod_from_files",
    "validate_bpod_structure",
    "index_bpod_data",
    "split_bpod_data",
    "write_bpod_mat",
]
