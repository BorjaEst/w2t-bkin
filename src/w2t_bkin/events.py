"""Events module for W2T-BKIN pipeline (Phase 3).

Parse Bpod .mat files into Trials and BehavioralEvents, generate QC summaries.

Requirements: FR-11, FR-14, NFR-7
Acceptance: A4 (trial counts and event categories in QC)
"""

from datetime import datetime
import logging
import math
from pathlib import Path
from typing import Any, Dict, List

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

from .domain import BehavioralEvent, BpodSummary, TrialData
from .utils import write_json

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class EventsError(Exception):
    """Error during events processing."""

    pass


class BpodParseError(EventsError):
    """Error parsing Bpod .mat file."""

    pass


# =============================================================================
# Bpod .mat Parsing
# =============================================================================


def parse_bpod_mat(path: Path) -> Dict[str, Any]:
    """Parse Bpod MATLAB .mat file.

    Args:
        path: Path to .mat file

    Returns:
        Dictionary with parsed Bpod data

    Raises:
        EventsError: If file not found
        BpodParseError: If file cannot be parsed
    """
    if not path.exists():
        raise EventsError(f"Bpod file not found: {path}")

    if loadmat is None:
        raise BpodParseError("scipy is required for .mat file parsing. Install with: pip install scipy")

    try:
        data = loadmat(str(path), squeeze_me=True, struct_as_record=False)
        return data
    except Exception as e:
        raise BpodParseError(f"Failed to parse Bpod file {path}: {e}")


def validate_bpod_structure(data: Dict[str, Any]) -> bool:
    """Validate Bpod data structure.

    Args:
        data: Parsed Bpod data

    Returns:
        True if structure is valid, False otherwise
    """
    if "SessionData" not in data:
        return False

    session_data = data["SessionData"]

    # Handle scipy.io mat_struct objects
    if hasattr(session_data, "__dict__"):
        session_data_dict = {k: v for k, v in session_data.__dict__.items() if not k.startswith("_")}
    elif isinstance(session_data, dict):
        session_data_dict = session_data
    else:
        return False

    # Check for required fields
    required_fields = ["nTrials", "TrialStartTimestamp", "TrialEndTimestamp"]
    for field in required_fields:
        if field not in session_data_dict:
            return False

    # Check for RawEvents structure
    if "RawEvents" not in session_data_dict:
        return False

    raw_events = session_data_dict["RawEvents"]

    # Handle mat_struct for RawEvents
    if hasattr(raw_events, "__dict__"):
        raw_events_dict = {k: v for k, v in raw_events.__dict__.items() if not k.startswith("_")}
    elif isinstance(raw_events, dict):
        raw_events_dict = raw_events
    else:
        return False

    if "Trial" not in raw_events_dict:
        return False

    return True


# =============================================================================
# Trial Extraction
# =============================================================================


def _is_state_visited(state_times: Any) -> bool:
    """Check if a state was visited (not NaN)."""
    if not isinstance(state_times, (list, tuple)):
        return False
    if len(state_times) < 2:
        return False
    start_time = state_times[0]
    return not (isinstance(start_time, float) and math.isnan(start_time))


def _infer_outcome(states: Dict[str, Any]) -> str:
    """Infer trial outcome from visited states."""
    if "HIT" in states and _is_state_visited(states["HIT"]):
        return "hit"
    if "Miss" in states and _is_state_visited(states["Miss"]):
        return "miss"
    if "CorrectReject" in states and _is_state_visited(states["CorrectReject"]):
        return "correct_rejection"
    if "FalseAlarm" in states and _is_state_visited(states["FalseAlarm"]):
        return "false_alarm"
    return "unknown"


def extract_trials(data: Dict[str, Any]) -> List[TrialData]:
    """Extract trial data from parsed Bpod data."""
    if not validate_bpod_structure(data):
        raise BpodParseError("Invalid Bpod structure")

    session_data = data["SessionData"]

    # Convert mat_struct to dict if needed
    if hasattr(session_data, "__dict__"):
        session_data_dict = {k: v for k, v in session_data.__dict__.items() if not k.startswith("_")}
    else:
        session_data_dict = session_data if isinstance(session_data, dict) else {}

    n_trials = int(session_data_dict["nTrials"])

    if n_trials == 0:
        return []

    start_timestamps = session_data_dict["TrialStartTimestamp"]
    end_timestamps = session_data_dict["TrialEndTimestamp"]
    raw_events = session_data_dict["RawEvents"]

    # Convert RawEvents mat_struct to dict if needed
    if hasattr(raw_events, "__dict__"):
        raw_events_dict = {k: v for k, v in raw_events.__dict__.items() if not k.startswith("_")}
    else:
        raw_events_dict = raw_events if isinstance(raw_events, dict) else {}

    # Note: start_timestamps and end_timestamps are already numpy arrays or lists
    # Don't wrap them - they can be indexed directly

    trials = []
    trial_data_list = raw_events_dict["Trial"]

    # Note: trial_data_list is already a numpy array or list - don't wrap it

    for i in range(n_trials):
        try:
            trial_num = i + 1
            start_time = float(start_timestamps[i])
            stop_time = float(end_timestamps[i])

            trial_data = trial_data_list[i]

            # Extract states - handle both dict and MATLAB struct
            if hasattr(trial_data, "States"):
                states = trial_data.States
            elif isinstance(trial_data, dict):
                states = trial_data.get("States", {})
            else:
                states = {}

            # Convert MATLAB struct to dict if needed
            if hasattr(states, "__dict__"):
                states = {k: v for k, v in states.__dict__.items() if not k.startswith("_")}

            outcome = _infer_outcome(states)

            trials.append(TrialData(trial_number=trial_num, start_time=start_time, stop_time=stop_time, outcome=outcome))
        except Exception as e:
            raise BpodParseError(f"Failed to extract trial {i}: {e}")

    return trials


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(data: Dict[str, Any]) -> List[BehavioralEvent]:
    """Extract behavioral events from parsed Bpod data."""
    if not validate_bpod_structure(data):
        return []

    session_data = data["SessionData"]

    # Convert mat_struct to dict if needed
    if hasattr(session_data, "__dict__"):
        session_data_dict = {k: v for k, v in session_data.__dict__.items() if not k.startswith("_")}
    else:
        session_data_dict = session_data if isinstance(session_data, dict) else {}

    n_trials = int(session_data_dict["nTrials"])

    if n_trials == 0:
        return []

    raw_events = session_data_dict["RawEvents"]

    # Convert RawEvents mat_struct to dict if needed
    if hasattr(raw_events, "__dict__"):
        raw_events_dict = {k: v for k, v in raw_events.__dict__.items() if not k.startswith("_")}
    else:
        raw_events_dict = raw_events if isinstance(raw_events, dict) else {}

    trial_data_list = raw_events_dict["Trial"]

    # Note: trial_data_list is already a numpy array or list - don't wrap it

    events = []

    for i in range(n_trials):
        trial_num = i + 1
        trial_data = trial_data_list[i]

        # Extract events - handle both dict and MATLAB struct
        if hasattr(trial_data, "Events"):
            trial_events = trial_data.Events
        elif isinstance(trial_data, dict):
            trial_events = trial_data.get("Events", {})
        else:
            trial_events = {}

        # Convert MATLAB struct to dict if needed
        if hasattr(trial_events, "__dict__"):
            trial_events = {k: v for k, v in trial_events.__dict__.items() if not k.startswith("_")}

        if not trial_events:
            continue

        for event_type, timestamps in trial_events.items():
            if not isinstance(timestamps, (list, tuple)):
                timestamps = [timestamps]

            for timestamp in timestamps:
                if isinstance(timestamp, (int, float)) and not math.isnan(timestamp):
                    events.append(BehavioralEvent(event_type=event_type, timestamp=float(timestamp), trial_number=trial_num))

    return events


# =============================================================================
# Event Summary Creation
# =============================================================================


def create_event_summary(session_id: str, trials: List[TrialData], events: List[BehavioralEvent], bpod_files: List[str]) -> BpodSummary:
    """Create event summary for QC report."""
    outcome_counts = {}
    for trial in trials:
        outcome_counts[trial.outcome] = outcome_counts.get(trial.outcome, 0) + 1

    event_categories = sorted(set(e.event_type for e in events))

    return BpodSummary(
        session_id=session_id,
        total_trials=len(trials),
        outcome_counts=outcome_counts,
        event_categories=event_categories,
        bpod_files=bpod_files,
        generated_at=datetime.utcnow().isoformat(),
    )


def write_event_summary(summary: BpodSummary, output_path: Path) -> None:
    """Write event summary to JSON file."""
    data = summary.model_dump()
    write_json(data, output_path)
