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
# Constants
# =============================================================================

# Valid trial outcome types (whitelist for security)
VALID_OUTCOMES = frozenset(["hit", "miss", "correct_rejection", "false_alarm", "unknown"])

# Valid state names that determine trial outcome
OUTCOME_STATES = frozenset(["HIT", "Miss", "CorrectReject", "FalseAlarm"])

# Maximum file size for Bpod .mat files (100 MB safety limit)
MAX_BPOD_FILE_SIZE_MB = 100


# =============================================================================
# Exceptions
# =============================================================================


class EventsError(Exception):
    """Error during events processing.

    Base exception for all events-related errors.
    Does not include sensitive file paths in messages by default.
    """

    pass


class BpodParseError(EventsError):
    """Error parsing Bpod .mat file.

    Raised when .mat file structure is invalid or cannot be parsed.
    """

    pass


class BpodValidationError(EventsError):
    """Error validating Bpod file or data.

    Raised when file size, path, or data content fails validation.
    """

    pass


# =============================================================================
# Security & Validation Helpers
# =============================================================================


def _validate_bpod_path(path: Path) -> None:
    """Validate Bpod file path for security.

    Args:
        path: Path to Bpod .mat file

    Raises:
        BpodValidationError: If path is invalid or file too large
    """
    if not path.exists():
        raise BpodValidationError("Bpod file not found")

    if not path.is_file():
        raise BpodValidationError("Bpod path is not a file")

    # Check file extension
    if path.suffix.lower() not in [".mat"]:
        raise BpodValidationError(f"Invalid file extension: {path.suffix}")

    # Check file size (prevent memory exhaustion)
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_BPOD_FILE_SIZE_MB:
        raise BpodValidationError(f"Bpod file too large: {file_size_mb:.1f}MB exceeds {MAX_BPOD_FILE_SIZE_MB}MB limit")

    logger.debug(f"Validated Bpod file: {path.name} ({file_size_mb:.2f}MB)")


def _sanitize_event_type(event_type: str) -> str:
    """Sanitize event type string from external data.

    Removes potentially dangerous characters and limits length.

    Args:
        event_type: Raw event type string from .mat file

    Returns:
        Sanitized event type string
    """
    if not isinstance(event_type, str):
        return "unknown_event"

    # Remove control characters and limit length
    sanitized = "".join(c for c in event_type if c.isprintable())[:100]

    if not sanitized:
        return "unknown_event"

    return sanitized


def _validate_outcome(outcome: str) -> str:
    """Validate trial outcome against whitelist.

    Args:
        outcome: Inferred outcome string

    Returns:
        Validated outcome (defaults to 'unknown' if invalid)
    """
    if outcome in VALID_OUTCOMES:
        return outcome

    logger.warning(f"Invalid outcome type '{outcome}', defaulting to 'unknown'")
    return "unknown"


def _convert_matlab_struct(obj: Any) -> Dict[str, Any]:
    """Convert MATLAB struct object to dictionary.

    Handles scipy.io mat_struct objects consistently.

    Args:
        obj: MATLAB struct object or dictionary

    Returns:
        Dictionary representation
    """
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    elif isinstance(obj, dict):
        return obj
    else:
        return {}


# =============================================================================
# Bpod .mat Parsing
# =============================================================================


def parse_bpod_mat(path: Path) -> Dict[str, Any]:
    """Parse Bpod MATLAB .mat file with security validation.

    Args:
        path: Path to .mat file

    Returns:
        Dictionary with parsed Bpod data

    Raises:
        BpodValidationError: If file validation fails
        BpodParseError: If file cannot be parsed
    """
    # Validate path and file size
    _validate_bpod_path(path)

    if loadmat is None:
        raise BpodParseError("scipy is required for .mat file parsing. Install with: pip install scipy")

    try:
        data = loadmat(str(path), squeeze_me=True, struct_as_record=False)
        logger.info(f"Successfully parsed Bpod file: {path.name}")
        return data
    except Exception as e:
        # Avoid leaking full path in error message
        raise BpodParseError(f"Failed to parse Bpod file: {type(e).__name__}")


def validate_bpod_structure(data: Dict[str, Any]) -> bool:
    """Validate Bpod data structure has required fields.

    Args:
        data: Parsed Bpod data

    Returns:
        True if structure is valid, False otherwise
    """
    if "SessionData" not in data:
        logger.warning("Missing 'SessionData' in Bpod file")
        return False

    session_data = _convert_matlab_struct(data["SessionData"])

    # Check for required fields
    required_fields = ["nTrials", "TrialStartTimestamp", "TrialEndTimestamp"]
    for field in required_fields:
        if field not in session_data:
            logger.warning(f"Missing required field '{field}' in SessionData")
            return False

    # Check for RawEvents structure
    if "RawEvents" not in session_data:
        logger.warning("Missing 'RawEvents' in SessionData")
        return False

    raw_events = _convert_matlab_struct(session_data["RawEvents"])

    if "Trial" not in raw_events:
        logger.warning("Missing 'Trial' in RawEvents")
        return False

    logger.debug("Bpod structure validation passed")
    return True


# =============================================================================
# Trial Extraction
# =============================================================================


def _is_state_visited(state_times: Any) -> bool:
    """Check if a state was visited (not NaN).

    A state is considered visited if it has valid (non-NaN) start time.

    Args:
        state_times: State time array/list from Bpod data

    Returns:
        True if state was visited, False otherwise
    """
    if not isinstance(state_times, (list, tuple)):
        return False
    if len(state_times) < 2:
        return False
    start_time = state_times[0]
    return not (isinstance(start_time, float) and math.isnan(start_time))


def _infer_outcome(states: Dict[str, Any]) -> str:
    """Infer trial outcome from visited states.

    Checks outcome-determining states in priority order.

    Args:
        states: Dictionary of state names to timing arrays

    Returns:
        Validated outcome string from VALID_OUTCOMES
    """
    # Check states in priority order
    if "HIT" in states and _is_state_visited(states["HIT"]):
        return _validate_outcome("hit")
    if "Miss" in states and _is_state_visited(states["Miss"]):
        return _validate_outcome("miss")
    if "CorrectReject" in states and _is_state_visited(states["CorrectReject"]):
        return _validate_outcome("correct_rejection")
    if "FalseAlarm" in states and _is_state_visited(states["FalseAlarm"]):
        return _validate_outcome("false_alarm")

    return _validate_outcome("unknown")


def extract_trials(data: Dict[str, Any]) -> List[TrialData]:
    """Extract trial data from parsed Bpod data with validation.

    Args:
        data: Parsed Bpod data dictionary

    Returns:
        List of TrialData objects

    Raises:
        BpodParseError: If structure is invalid or extraction fails
    """
    if not validate_bpod_structure(data):
        raise BpodParseError("Invalid Bpod structure")

    session_data = _convert_matlab_struct(data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials found in Bpod file")
        return []

    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]
    raw_events = _convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    trials = []

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
            states = _convert_matlab_struct(states)
            outcome = _infer_outcome(states)

            trials.append(TrialData(trial_number=trial_num, start_time=start_time, stop_time=stop_time, outcome=outcome))
        except Exception as e:
            raise BpodParseError(f"Failed to extract trial {i + 1}: {type(e).__name__}")

    logger.info(f"Extracted {len(trials)} trials from Bpod file")
    return trials


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(data: Dict[str, Any]) -> List[BehavioralEvent]:
    """Extract behavioral events from parsed Bpod data with sanitization.

    Args:
        data: Parsed Bpod data dictionary

    Returns:
        List of BehavioralEvent objects with sanitized event types
    """
    if not validate_bpod_structure(data):
        logger.warning("Invalid Bpod structure, returning empty event list")
        return []

    session_data = _convert_matlab_struct(data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        return []

    raw_events = _convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

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
        trial_events = _convert_matlab_struct(trial_events)

        if not trial_events:
            continue

        for event_type, timestamps in trial_events.items():
            # Sanitize event type from external data
            safe_event_type = _sanitize_event_type(event_type)

            if not isinstance(timestamps, (list, tuple)):
                timestamps = [timestamps]

            for timestamp in timestamps:
                if isinstance(timestamp, (int, float)) and not math.isnan(timestamp):
                    events.append(BehavioralEvent(event_type=safe_event_type, timestamp=float(timestamp), trial_number=trial_num))

    logger.info(f"Extracted {len(events)} behavioral events from Bpod file")
    return events


# =============================================================================
# Event Summary Creation
# =============================================================================


def create_event_summary(session_id: str, trials: List[TrialData], events: List[BehavioralEvent], bpod_files: List[str]) -> BpodSummary:
    """Create event summary for QC report with validated data.

    Args:
        session_id: Session identifier
        trials: List of extracted trials
        events: List of extracted behavioral events
        bpod_files: List of source Bpod file paths

    Returns:
        BpodSummary object for QC reporting
    """
    outcome_counts = {}
    for trial in trials:
        outcome_counts[trial.outcome] = outcome_counts.get(trial.outcome, 0) + 1

    event_categories = sorted(set(e.event_type for e in events))

    summary = BpodSummary(
        session_id=session_id,
        total_trials=len(trials),
        outcome_counts=outcome_counts,
        event_categories=event_categories,
        bpod_files=bpod_files,
        generated_at=datetime.utcnow().isoformat(),
    )

    logger.info(f"Created event summary: {len(trials)} trials, {len(events)} events")
    return summary


def write_event_summary(summary: BpodSummary, output_path: Path) -> None:
    """Write event summary to JSON file.

    Args:
        summary: BpodSummary object to write
        output_path: Destination path for JSON file
    """
    data = summary.model_dump()
    write_json(data, output_path)
    logger.info(f"Wrote event summary to {output_path.name}")
