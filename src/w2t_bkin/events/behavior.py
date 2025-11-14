"""Behavioral event extraction.

Extracts TrialEvent domain objects from Bpod data representing behavioral events
like port pokes, state entries/exits, and stimulus presentations.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..domain import TrialEvent
from ..utils import convert_matlab_struct, is_nan_or_none
from .bpod import validate_bpod_structure
from .helpers import sanitize_event_type, to_list

logger = logging.getLogger(__name__)


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(bpod_data: Dict[str, Any], trial_offsets: Optional[Dict[int, float]] = None) -> List[TrialEvent]:
    """Extract behavioral events from parsed Bpod data dictionary.

    Extracts events with relative timestamps by default. If trial_offsets are provided
    (from sync.align_bpod_trials_to_ttl), converts to absolute timestamps.

    Args:
        bpod_data: Parsed Bpod data dictionary (from parse_bpod_mat or parse_bpod_session)
        trial_offsets: Optional dict mapping trial_number → absolute time offset.
                      If provided, converts relative timestamps to absolute.
                      Use sync.align_bpod_trials_to_ttl() to compute offsets.

    Returns:
        List of TrialEvent objects with absolute or relative timestamps

    Examples:
        >>> # Parse and extract (relative timestamps)
        >>> from pathlib import Path
        >>> from w2t_bkin.events import parse_bpod_mat, extract_behavioral_events
        >>> bpod_data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>> events = extract_behavioral_events(bpod_data)
        >>>
        >>> # With Session configuration
        >>> from w2t_bkin.config import load_session
        >>> from w2t_bkin.events import parse_bpod_session, extract_behavioral_events
        >>> session = load_session("data/Session-001/session.toml")
        >>> bpod_data = parse_bpod_session(session)
        >>> events = extract_behavioral_events(bpod_data)
        >>>
        >>> # With TTL alignment (absolute timestamps)
        >>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl
        >>> ttl_pulses = get_ttl_pulses(session)
        >>> trial_offsets, _ = align_bpod_trials_to_ttl(session, bpod_data, ttl_pulses)
        >>> events = extract_behavioral_events(bpod_data, trial_offsets=trial_offsets)
    """
    # Validate Bpod data structure
    if not validate_bpod_structure(bpod_data):
        logger.warning("Invalid Bpod structure, returning empty event list")
        return []

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        return []

    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    events = []

    for i in range(n_trials):
        trial_num = i + 1

        # Skip trials without alignment offset if using absolute time
        if trial_offsets is not None and trial_num not in trial_offsets:
            continue

        trial_data = trial_data_list[i]

        # Extract events - handle both dict and MATLAB struct
        if hasattr(trial_data, "Events"):
            trial_events = trial_data.Events
        elif isinstance(trial_data, dict):
            trial_events = trial_data.get("Events", {})
        else:
            trial_events = {}

        # Convert MATLAB struct to dict if needed
        trial_events = convert_matlab_struct(trial_events)

        if not trial_events:
            continue

        for event_type, timestamps in trial_events.items():
            # Sanitize event type from external data
            safe_event_type = sanitize_event_type(event_type)

            # Convert to list if numpy array or scalar
            if isinstance(timestamps, np.ndarray):
                timestamps = to_list(timestamps)
            elif not isinstance(timestamps, (list, tuple)):
                timestamps = [timestamps]

            for timestamp in timestamps:
                if not is_nan_or_none(timestamp):
                    timestamp_rel = float(timestamp)

                    # Convert to absolute time if offsets provided
                    if trial_offsets is not None:
                        offset = trial_offsets[trial_num]
                        timestamp_abs = offset + timestamp_rel
                    else:
                        timestamp_abs = timestamp_rel

                    events.append(
                        TrialEvent(
                            event_type=safe_event_type,
                            timestamp=timestamp_abs,
                            metadata={"trial_number": float(trial_num)},
                        )
                    )

    logger.info(f"Extracted {len(events)} behavioral events from Bpod file")
    return events
