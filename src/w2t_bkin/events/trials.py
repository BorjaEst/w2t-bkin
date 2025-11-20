"""Extract trials and infer outcomes from Bpod data.

Provides trial extraction with outcome inference based on visited states.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..exceptions import BpodParseError
from ..utils import convert_matlab_struct, is_nan_or_none, to_scalar, validate_against_whitelist
from .bpod import validate_bpod_structure
from .models import Trial, TrialOutcome

logger = logging.getLogger(__name__)

# Constants
VALID_OUTCOMES = frozenset(["hit", "miss", "correct_rejection", "false_alarm", "unknown"])


# =============================================================================
# Trial Extraction
# =============================================================================


def extract_trials(bpod_data: Dict[str, Any], trial_offsets: Optional[Dict[int, float]] = None) -> List[Trial]:
    """Extract trials from Bpod data with outcome inference.

    Returns trials with relative timestamps by default. If trial_offsets are
    provided, converts to absolute timestamps.

    Args:
        bpod_data: Bpod data dictionary
        trial_offsets: Dict mapping trial_number → absolute time offset

    Returns:
        List of Trial objects

    Raises:
        BpodParseError: Invalid structure or extraction failed

    Example:
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
        >>> trials = extract_trials(bpod_data)
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
    """Check if a state was visited.

    Args:
        state_times: State time array/list from Bpod data

    Returns:
        True if state has valid (non-NaN) start time
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

    Args:
        states: Dict of state names to timing arrays

    Returns:
        Outcome string (hit, miss, correct_rejection, false_alarm, or unknown)
    """
    # Check states in priority order
    if "HIT" in states and is_state_visited(states["HIT"]):
        return validate_against_whitelist("hit", VALID_OUTCOMES, default="unknown", warn=True)
    if "Miss" in states and is_state_visited(states["Miss"]):
        return validate_against_whitelist("miss", VALID_OUTCOMES, default="unknown", warn=True)
    if "CorrectReject" in states and is_state_visited(states["CorrectReject"]):
        return validate_against_whitelist("correct_rejection", VALID_OUTCOMES, default="unknown", warn=True)
    if "FalseAlarm" in states and is_state_visited(states["FalseAlarm"]):
        return validate_against_whitelist("false_alarm", VALID_OUTCOMES, default="unknown", warn=True)

    return validate_against_whitelist("unknown", VALID_OUTCOMES, default="unknown", warn=True)
