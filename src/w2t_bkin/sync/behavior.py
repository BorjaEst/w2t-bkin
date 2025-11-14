"""Behavioral data synchronization (Bpod-TTL alignment).

Provides Bpod-specific temporal alignment using hardware TTL sync signals.
Converts Bpod relative timestamps to absolute time by matching per-trial
sync events to corresponding TTL pulses.

Example:
    >>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl
    >>> from w2t_bkin.config import load_session
    >>> from w2t_bkin.events import parse_bpod_session, extract_trials
    >>>
    >>> # Load session and Bpod data
    >>> session = load_session("data/Session-001/session.toml")
    >>> bpod_data = parse_bpod_session(session)
    >>>
    >>> # Get TTL pulses and compute alignment
    >>> ttl_pulses = get_ttl_pulses(session)
    >>> trial_offsets, warnings = align_bpod_trials_to_ttl(session, bpod_data, ttl_pulses)
    >>>
    >>> # Use offsets to extract trials with absolute timestamps
    >>> trials = extract_trials(bpod_data, trial_offsets=trial_offsets)
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..domain import Session
from .exceptions import SyncError

__all__ = [
    "get_sync_time_from_bpod_trial",
    "align_bpod_trials_to_ttl",
]

logger = logging.getLogger(__name__)


def get_sync_time_from_bpod_trial(trial_data: Dict, sync_signal: str) -> Optional[float]:
    """Extract synchronization signal timing from Bpod trial data.

    Looks for a specific state visit (e.g., "W2L_Audio", "A2L_Audio") in the
    trial's States structure and returns its start time relative to trial start.

    Args:
        trial_data: Raw trial data from Bpod containing States
        sync_signal: State name to use for sync (e.g., "W2L_Audio", "A2L_Audio")

    Returns:
        Start time of sync signal (relative to trial start), or None if not found/visited

    Example:
        >>> trial = bpod_data["SessionData"]["RawEvents"]["Trial"][0]
        >>> sync_time = get_sync_time_from_bpod_trial(trial, "W2L_Audio")
        >>> if sync_time is not None:
        ...     print(f"Sync signal occurred at {sync_time:.3f}s into trial")
    """
    from ..utils import convert_matlab_struct, is_nan_or_none

    # Convert MATLAB struct to dict if needed
    trial_data = convert_matlab_struct(trial_data)

    states = trial_data.get("States", {})
    if not states:
        return None

    # Convert states to dict if it's a MATLAB struct
    states = convert_matlab_struct(states)

    sync_times = states.get(sync_signal)
    if sync_times is None:
        return None

    if not isinstance(sync_times, (list, tuple, np.ndarray)) or len(sync_times) < 2:
        return None

    start_time = sync_times[0]
    if is_nan_or_none(start_time):
        return None

    return float(start_time)


def align_bpod_trials_to_ttl(
    session: Session,
    bpod_data: Dict,
    ttl_pulses: Dict[str, List[float]],
) -> Tuple[Dict[int, float], List[str]]:
    """Align Bpod trials to absolute time using TTL sync signals.

    Converts Bpod relative timestamps to absolute time by matching per-trial
    sync signals to corresponding TTL pulses. Returns per-trial offsets that
    can be used with events.extract_trials() and events.extract_behavioral_events()
    to convert relative timestamps to absolute timestamps.

    Algorithm:
    ----------
    1. For each trial, determine trial_type from Bpod TrialTypes array
    2. Lookup sync configuration from session.bpod.trial_types
    3. Extract sync_signal start time (relative to trial start) from States
    4. Match to next available TTL pulse from corresponding channel
    5. Compute offset accounting for TrialStartTimestamp:
       offset = ttl_pulse_time - (TrialStartTimestamp + sync_time_rel)
    6. Return offsets for use: t_abs = offset + TrialStartTimestamp

    Edge Cases:
    -----------
    - Missing sync_signal: Skip trial, record warning
    - Extra TTL pulses: Ignore surplus, log warning
    - Fewer TTL pulses: Align what's possible, mark remaining as unaligned
    - Jitter: Allow small timing differences, log debug info

    Args:
        session: Session config with trial_type sync mappings in session.bpod.trial_types
        bpod_data: Parsed Bpod data (SessionData structure from events.parse_bpod_session)
        ttl_pulses: Dict mapping TTL channel ID to sorted list of absolute timestamps
                    (typically from sync.get_ttl_pulses)

    Returns:
        Tuple of:
        - trial_offsets: Dict mapping trial_number → absolute time offset
        - warnings: List of warning messages for trials that couldn't be aligned

    Raises:
        SyncError: If trial_type config missing or data structure invalid

    Example:
        >>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl
        >>> from w2t_bkin.config import load_session
        >>> from w2t_bkin.events import parse_bpod_session, extract_trials
        >>>
        >>> # Load and parse
        >>> session = load_session("data/Session-001/session.toml")
        >>> bpod_data = parse_bpod_session(session)
        >>> ttl_pulses = get_ttl_pulses(session)
        >>>
        >>> # Compute alignment offsets
        >>> trial_offsets, warnings = align_bpod_trials_to_ttl(
        ...     session, bpod_data, ttl_pulses
        ... )
        >>>
        >>> if warnings:
        ...     print(f"Alignment warnings: {warnings}")
        >>>
        >>> # Extract trials with absolute timestamps
        >>> trials = extract_trials(bpod_data, trial_offsets=trial_offsets)
        >>> print(f"Trial 1 start: {trials[0].start_time:.3f}s (absolute)")
    """
    from ..utils import convert_matlab_struct

    # Validate Bpod structure
    if "SessionData" not in bpod_data:
        raise SyncError("Invalid Bpod structure: missing SessionData")

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials to align")
        return {}, []

    # Build trial_type → sync config mapping
    trial_type_map = {}
    for tt_config in session.bpod.trial_types:
        trial_type_map[tt_config.trial_type] = {
            "sync_signal": tt_config.sync_signal,
            "sync_ttl": tt_config.sync_ttl,
            "description": tt_config.description,
        }

    if not trial_type_map:
        raise SyncError("No trial_type sync configuration found in session.bpod.trial_types")

    # Prepare TTL pulse pointers (track consumption per channel)
    ttl_pointers = {ttl_id: 0 for ttl_id in ttl_pulses.keys()}

    # Extract raw trial data
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    # Extract TrialTypes if available (use helper from events.helpers)
    from ..events.helpers import to_scalar

    trial_types_array = session_data.get("TrialTypes")
    if trial_types_array is None:
        # Default to trial_type 1 for all trials if not specified
        trial_types_array = [1] * n_trials
        logger.warning("TrialTypes not found in Bpod data, defaulting all trials to type 1")

    trial_offsets = {}
    warnings_list = []

    for i in range(n_trials):
        trial_num = i + 1
        trial_data = convert_matlab_struct(trial_data_list[i])

        # Get trial type (handle numpy arrays)
        trial_type = int(to_scalar(trial_types_array, i))

        if trial_type not in trial_type_map:
            warnings_list.append(f"Trial {trial_num}: trial_type {trial_type} not in session config, skipping")
            logger.warning(warnings_list[-1])
            continue

        sync_config = trial_type_map[trial_type]
        sync_signal = sync_config["sync_signal"]
        sync_ttl_id = sync_config["sync_ttl"]

        # Extract sync time from trial (relative to trial start)
        sync_time_rel = get_sync_time_from_bpod_trial(trial_data, sync_signal)
        if sync_time_rel is None:
            warnings_list.append(f"Trial {trial_num}: sync_signal '{sync_signal}' not found or not visited, skipping")
            logger.warning(warnings_list[-1])
            continue

        # Get next TTL pulse
        if sync_ttl_id not in ttl_pulses:
            warnings_list.append(f"Trial {trial_num}: TTL channel '{sync_ttl_id}' not found in ttl_pulses, skipping")
            logger.error(warnings_list[-1])
            continue

        ttl_channel = ttl_pulses[sync_ttl_id]
        ttl_ptr = ttl_pointers[sync_ttl_id]

        if ttl_ptr >= len(ttl_channel):
            warnings_list.append(f"Trial {trial_num}: No more TTL pulses available for '{sync_ttl_id}', skipping")
            logger.warning(warnings_list[-1])
            continue

        ttl_pulse_time = ttl_channel[ttl_ptr]
        ttl_pointers[sync_ttl_id] += 1

        # Get trial start timestamp from Bpod (may be non-zero after merge)
        trial_start_timestamp = float(to_scalar(session_data["TrialStartTimestamp"], i))

        # Compute offset: absolute_time = offset + TrialStartTimestamp
        # The sync signal occurs at: trial_start_timestamp + sync_time_rel (in Bpod timeline)
        # And should align to: ttl_pulse_time (in absolute timeline)
        # Therefore: offset + (trial_start_timestamp + sync_time_rel) = ttl_pulse_time
        offset_abs = ttl_pulse_time - (trial_start_timestamp + sync_time_rel)
        trial_offsets[trial_num] = offset_abs

        logger.debug(
            f"Trial {trial_num}: type={trial_type}, sync_signal={sync_signal}, "
            f"trial_start={trial_start_timestamp:.4f}s, sync_rel={sync_time_rel:.4f}s, "
            f"ttl_abs={ttl_pulse_time:.4f}s, offset={offset_abs:.4f}s"
        )  # fmt: skip

    # Warn about unused TTL pulses
    for ttl_id, ptr in ttl_pointers.items():
        unused = len(ttl_pulses[ttl_id]) - ptr
        if unused > 0:
            warnings_list.append(f"TTL channel '{ttl_id}' has {unused} unused pulses")
            logger.warning(warnings_list[-1])

    logger.info(f"Computed offsets for {len(trial_offsets)} out of {n_trials} trials using TTL sync")
    return trial_offsets, warnings_list
