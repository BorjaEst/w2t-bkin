"""TTL synchronization utilities.

Provides functions for aligning Bpod trials to TTL sync signals.

Note: TTL loading functions (load_ttl_file, get_ttl_pulses) have been moved
to w2t_bkin.ttl.

Example:
    >>> from w2t_bkin.sync.ttl import align_bpod_trials_to_ttl
    >>> from w2t_bkin.ttl import get_ttl_pulses
"""

import logging
from typing import Dict, List, Optional, Protocol, Sequence, Tuple, TypedDict, Union

import numpy as np

from w2t_bkin.exceptions import SyncError

logger = logging.getLogger(__name__)


def get_sync_time_from_bpod_trial(trial_data: Dict, sync_signal: str) -> Optional[float]:
    """Extract sync signal start time from Bpod trial.

    Args:
        trial_data: Trial data with States structure
        sync_signal: State name (e.g. "W2L_Audio")

    Returns:
        Start time relative to trial start, or None if not found

    Example:
        >>> sync_time = get_sync_time_from_bpod_trial(trial, "W2L_Audio")
    """
    from w2t_bkin.utils import convert_matlab_struct, is_nan_or_none

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


class BpodTrialTypeProtocol(Protocol):
    """Protocol for Bpod trial type configuration access.

    Defines minimal interface needed by sync.ttl module without
    importing from domain.session.BpodTrialType.

    This module accepts both:
    - typed configs (e.g. Pydantic models) exposing attributes
    - dict-based configs (legacy/tests)

    Attributes:
        trial_type: Trial type identifier
        sync_signal: Bpod state/event name for alignment
        sync_ttl: TTL channel ID for sync pulses
    """

    trial_type: int
    sync_signal: str
    sync_ttl: str


class BpodTrialTypeDict(TypedDict):
    """Dict-based trial type sync configuration (legacy/tests)."""

    trial_type: int
    sync_signal: str
    sync_ttl: str


BpodTrialTypeConfig = Union[BpodTrialTypeProtocol, BpodTrialTypeDict]


def _trial_type_config_value(cfg: object, key: str):
    """Read a value from a trial-type config.

    The pipeline historically passed dict-like configs, but the strict metadata
    path now prefers typed Pydantic models.
    """

    if hasattr(cfg, key):
        return getattr(cfg, key)
    if isinstance(cfg, dict):
        return cfg[key]
    if hasattr(cfg, "get"):
        return cfg.get(key)
    raise TypeError(f"Trial type config must support attribute or dict-style access; missing key '{key}'.")


def align_bpod_trials_to_ttl(
    trial_type_configs: Sequence[BpodTrialTypeConfig],
    bpod_data: Dict,
    ttl_pulses: Dict[str, List[float]],
) -> Tuple[Dict[int, float], List[str]]:
    """Align Bpod trials to absolute time using TTL sync signals (low-level, Session-free).

    Converts Bpod relative timestamps to absolute time by matching per-trial
    sync signals to corresponding TTL pulses. Returns per-trial offsets that
    can be used with events.extract_trials() and events.extract_behavioral_events()
    to convert relative timestamps to absolute timestamps.

    Algorithm:
    ----------
    1. For each trial, determine trial_type from Bpod TrialTypes array
    2. Lookup sync configuration from trial_type_configs list
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
        trial_type_configs: List of trial type sync configurations
                           (from session.bpod.trial_types)
        bpod_data: Parsed Bpod data (SessionData structure from events.parse_bpod)
        ttl_pulses: Dict mapping TTL channel ID to sorted list of absolute timestamps
                    (typically from w2t_bkin.ttl.get_ttl_pulses)

    Returns:
        Tuple of:
        - trial_offsets: Dict mapping trial_number → absolute time offset
        - warnings: List of warning messages for trials that couldn't be aligned

    Raises:
        SyncError: If trial_type config missing or data structure invalid
        TypeError: If trial_type_configs is not a list or tuple

    Example:
        >>> from w2t_bkin.ttl import get_ttl_pulses
        >>> from w2t_bkin.sync.ttl import align_bpod_trials_to_ttl
        >>> from w2t_bkin.bpod.code import parse_bpod
        >>> from pathlib import Path
        >>>
        >>> # Low-level approach with primitives
        >>> session_dir = Path("data/Session-001")
        >>> bpod_data = parse_bpod(session_dir, "Bpod/*.mat", "name_asc")
        >>> ttl_patterns = {"ttl_bpod": "TTLs/bod*.txt"}
        >>> ttl_pulses = get_ttl_pulses(session_dir, ttl_patterns)
        >>>
        >>> # Define trial type configs
        >>> from w2t_bkin.domain.session import BpodTrialType
        >>> trial_configs = [
        ...     BpodTrialType(trial_type=1, sync_signal="W2L_Audio",
        ...                  sync_ttl="ttl_bpod", description="W2L")
        ... ]
        >>>
        >>> # Compute alignment offsets
        >>> trial_offsets, warnings = align_bpod_trials_to_ttl(
        ...     trial_configs, bpod_data, ttl_pulses
        ... )
    """
    from w2t_bkin.utils import convert_matlab_struct, to_scalar

    # Validate input types
    if not isinstance(trial_type_configs, (list, tuple)):
        raise TypeError(f"trial_type_configs must be a list or tuple, got {type(trial_type_configs).__name__}. " "Expected sequence of trial-type configs (dicts or typed models).")

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
    for tt_config in trial_type_configs:
        trial_type = int(_trial_type_config_value(tt_config, "trial_type"))
        trial_type_map[trial_type] = {
            "sync_signal": _trial_type_config_value(tt_config, "sync_signal"),
            "sync_ttl": _trial_type_config_value(tt_config, "sync_ttl"),
        }

    if not trial_type_map:
        raise SyncError("No trial_type sync configuration provided in trial_type_configs")

    # Prepare TTL pulse pointers (track consumption per channel)
    ttl_pointers = {ttl_id: 0 for ttl_id in ttl_pulses.keys()}

    # Extract raw events
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    # Extract TrialTypes if available
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
            # Don't log each trial individually - will summarize at the end
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

    # Log summary of alignment issues if any
    skipped_trials = [w for w in warnings_list if "No more TTL pulses available" in w]
    if skipped_trials:
        logger.warning(f"{len(skipped_trials)} trial(s) skipped due to missing TTL pulses (check session log for details)")

    logger.info(f"Computed offsets for {len(trial_offsets)} out of {n_trials} trials using TTL sync")
    return trial_offsets, warnings_list
