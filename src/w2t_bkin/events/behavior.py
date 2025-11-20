"""Extract behavioral events from Bpod data.

Extracts TrialEvent objects representing port pokes, state entries/exits,
and stimulus presentations.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils import convert_matlab_struct, is_nan_or_none
from .bpod import validate_bpod_structure
from .helpers import sanitize_event_type, to_list, to_scalar
from .models import TrialEvent

logger = logging.getLogger(__name__)


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(
    bpod_data: Dict[str, Any],
    trial_offsets: Optional[Dict[int, float]] = None,
    *,
    bpod_absolute: bool = True,
) -> List[TrialEvent]:
    """Extract behavioral events from Bpod data.

    Returns events with timestamps computed as:
    - With trial_offsets: offset + (TrialStartTimestamp + event_rel)
    - Without offsets, bpod_absolute=True: TrialStartTimestamp + event_rel
    - Without offsets, bpod_absolute=False: event_rel (trial-relative)

    Args:
        bpod_data: Bpod data dictionary
        trial_offsets: Dict mapping trial_number → absolute time offset
        bpod_absolute: Use session-absolute timestamps when no offsets given

    Returns:
        List of TrialEvent objects

    Example:
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
        >>> events = extract_behavioral_events(bpod_data)
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
    start_timestamps = session_data["TrialStartTimestamp"]
    trial_data_list = raw_events["Trial"]

    events = []

    # bpod_absolute directly controls behavior when no offsets are provided

    for i in range(n_trials):
        trial_num = i + 1

        # Per-trial base times
        trial_start_ts = float(to_scalar(start_timestamps, i))
        offset = None
        if trial_offsets is not None:
            offset = trial_offsets.get(trial_num)
            if offset is None and not bpod_absolute:
                logger.warning(f"Trial {trial_num}: No alignment offset found; keeping trial-relative timestamps")

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

                    # Match extract_trials semantics:
                    # - If offsets available: absolute TTL time = offset + (TrialStartTimestamp + event_rel)
                    # - Else: keep trial-relative time = event_rel
                    if offset is not None:
                        timestamp_abs = offset + (trial_start_ts + timestamp_rel)
                    elif bpod_absolute:
                        timestamp_abs = trial_start_ts + timestamp_rel
                    else:
                        timestamp_abs = timestamp_rel

                    events.append(
                        TrialEvent(
                            event_type=safe_event_type,
                            timestamp=timestamp_abs,
                            metadata={"trial_number": float(trial_num)},
                        )
                    )

    # Ensure deterministic, monotonically increasing ordering
    events.sort(key=lambda e: e.timestamp)

    logger.info(f"Extracted {len(events)} behavioral events from Bpod file")
    return events
