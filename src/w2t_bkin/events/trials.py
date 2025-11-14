"""Trial extraction and outcome inference.

Extracts Trial domain objects from Bpod data with outcome inference from state visits.
Supports both relative and absolute timestamps via trial offsets.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..domain import Trial
from ..domain.trials import TrialOutcome
from ..utils import convert_matlab_struct, is_nan_or_none
from .bpod import validate_bpod_structure
from .exceptions import BpodParseError
from .helpers import to_scalar, validate_outcome

logger = logging.getLogger(__name__)


# =============================================================================
# Trial Extraction
# =============================================================================


def extract_trials(bpod_data: Dict[str, Any], trial_offsets: Optional[Dict[int, float]] = None) -> List[Trial]:
    """Extract trial data from parsed Bpod data dictionary.

    Extracts trials with relative timestamps by default. If trial_offsets are provided
    (from sync.align_bpod_trials_to_ttl), converts to absolute timestamps.

    Warnings about failed trial extraction are logged automatically.

    Args:
        bpod_data: Parsed Bpod data dictionary (from parse_bpod_mat or parse_bpod_session)
        trial_offsets: Optional dict mapping trial_number → absolute time offset.
                      If provided, converts relative timestamps to absolute.
                      Use sync.align_bpod_trials_to_ttl() to compute offsets.

    Returns:
        List[Trial]: Trial objects with absolute (if offsets) or relative timestamps

    Raises:
        BpodParseError: If structure is invalid or extraction fails

    Examples:
        >>> # Parse and extract (relative timestamps)
        >>> from pathlib import Path
        >>> from w2t_bkin.events import parse_bpod_mat, extract_trials
        >>> bpod_data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>> trials = extract_trials(bpod_data)
        >>>
        >>> # With Session configuration
        >>> from w2t_bkin.config import load_session
        >>> from w2t_bkin.events import parse_bpod_session, extract_trials
        >>> session = load_session("data/Session-001/session.toml")
        >>> bpod_data = parse_bpod_session(session)
        >>> trials = extract_trials(bpod_data)
        >>>
        >>> # With TTL alignment (absolute timestamps)
        >>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl
        >>> ttl_pulses = get_ttl_pulses(session)
        >>> trial_offsets, _ = align_bpod_trials_to_ttl(session, bpod_data, ttl_pulses)
        >>> trials = extract_trials(bpod_data, trial_offsets=trial_offsets)
    """
    # Validate Bpod data structure
    if not validate_bpod_structure(bpod_data):
        raise BpodParseError("Invalid Bpod structure")

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials found in Bpod file")
        return []

    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    # Extract TrialTypes if available
    trial_types_array = session_data.get("TrialTypes")
    if trial_types_array is None:
        trial_types_array = [1] * n_trials  # Default to trial_type 1

    trials = []

    for i in range(n_trials):
        try:
            trial_num = i + 1
            start_time_rel = float(to_scalar(start_timestamps, i))
            stop_time_rel = float(to_scalar(end_timestamps, i))
            trial_type = int(to_scalar(trial_types_array, i))

            # Apply offset if provided (converts to absolute time)
            if trial_offsets and trial_num in trial_offsets:
                offset = trial_offsets[trial_num]
                start_time = offset + start_time_rel
                stop_time = offset + stop_time_rel
            else:
                # Keep relative timestamps
                start_time = start_time_rel
                stop_time = stop_time_rel

                # Warn if offsets were expected but not found for this trial
                if trial_offsets is not None and trial_num not in trial_offsets:
                    logger.warning(f"Trial {trial_num}: No offset found, using relative timestamps")

            trial_data = trial_data_list[i]

            # Extract states - handle both dict and MATLAB struct
            if hasattr(trial_data, "States"):
                states = trial_data.States
            elif isinstance(trial_data, dict):
                states = trial_data.get("States", {})
            else:
                states = {}

            # Convert MATLAB struct to dict if needed
            states = convert_matlab_struct(states)
            outcome_str = infer_outcome(states)

            # Map string outcome to TrialOutcome enum
            outcome_map = {
                "hit": TrialOutcome.HIT,
                "miss": TrialOutcome.MISS,
                "correct_rejection": TrialOutcome.CORRECT_REJECTION,
                "false_alarm": TrialOutcome.FALSE_ALARM,
                "unknown": TrialOutcome.MISS,  # Default unknown to MISS
            }
            outcome = outcome_map.get(outcome_str, TrialOutcome.MISS)

            trials.append(
                Trial(
                    trial_number=trial_num,
                    trial_type=trial_type,
                    start_time=start_time,
                    stop_time=stop_time,
                    outcome=outcome,
                )
            )
        except Exception as e:
            logger.error(f"Failed to extract trial {i + 1}: {type(e).__name__}: {e}")

    logger.info(f"Extracted {len(trials)} trials from Bpod file")
    return trials


# =============================================================================
# Outcome Inference Helpers
# =============================================================================


def is_state_visited(state_times: Any) -> bool:
    """Check if a state was visited (not NaN).

    A state is considered visited if it has valid (non-NaN) start time.

    Args:
        state_times: State time array/list from Bpod data (can be ndarray, list, or tuple)

    Returns:
        True if state was visited, False otherwise
    """
    # Handle numpy arrays
    if isinstance(state_times, np.ndarray):
        if state_times.size < 2:
            return False
        start_time = state_times.flat[0]  # Use flat indexer for safety
        return not is_nan_or_none(start_time)

    # Handle lists and tuples
    if not isinstance(state_times, (list, tuple)):
        return False
    if len(state_times) < 2:
        return False
    start_time = state_times[0]
    return not is_nan_or_none(start_time)


def infer_outcome(states: Dict[str, Any]) -> str:
    """Infer trial outcome from visited states.

    Checks outcome-determining states in priority order.

    Args:
        states: Dictionary of state names to timing arrays

    Returns:
        Validated outcome string from VALID_OUTCOMES
    """
    # Check states in priority order
    if "HIT" in states and is_state_visited(states["HIT"]):
        return validate_outcome("hit")
    if "Miss" in states and is_state_visited(states["Miss"]):
        return validate_outcome("miss")
    if "CorrectReject" in states and is_state_visited(states["CorrectReject"]):
        return validate_outcome("correct_rejection")
    if "FalseAlarm" in states and is_state_visited(states["FalseAlarm"]):
        return validate_outcome("false_alarm")

    return validate_outcome("unknown")
