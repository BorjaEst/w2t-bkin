"""Events module for W2T-BKIN pipeline (Phase 3 - Behavioral Data).

Parses Bpod behavioral task data from .mat files (MATLAB format) and extracts:
- Trial data: trial numbers, outcomes (hit/miss/correct reject), start/end times
- Behavioral events: state entries/exits, port interactions, stimulus presentations
- QC summaries: trial counts, outcome distributions, event categories

The module uses scipy.io.loadmat for MATLAB file parsing and implements robust
validation for Bpod data structure variations across different task protocols.

Key Features:
-------------
- **Bpod Compatibility**: Handles SessionData structure from Bpod r2.5+
- **Trial Extraction**: Parses trial outcomes and timing from States/RawEvents
- **Event Extraction**: Converts Bpod events to standardized TrialEvent format
- **Outcome Inference**: Derives trial outcomes from state visit patterns
- **QC Summaries**: Generates statistics for quality control

Main Functions:
---------------
- parse_bpod_mat: Load and validate single Bpod .mat file
- parse_bpod_session: Discover and merge multiple Bpod files from BpodSession config
- discover_bpod_files: Find Bpod files matching glob pattern
- merge_bpod_sessions: Combine multiple Bpod files into unified session
- extract_trials: Extract Trial objects from SessionData
- extract_behavioral_events: Convert Bpod events to TrialEvent format
- create_event_summary: Generate TrialSummary for QC reporting

Requirements:
-------------
- FR-11: Behavioral event parsing from Bpod
- FR-14: Trial outcome and timing extraction
- NFR-7: Flexible handling of varying Bpod protocols

Acceptance Criteria:
-------------------
- A4: Trial counts and event categories available for QC

Data Flow:
----------
1. Load .mat file → Raw MATLAB structures
2. Validate SessionData structure
3. Extract trials → Trial objects (outcome, times)
4. Extract events → TrialEvent objects (category, timestamp)
5. Create summary → TrialSummary (counts, categories)

Example:
--------
>>> from w2t_bkin.events import parse_bpod_mat, parse_bpod_session, extract_trials
>>> from w2t_bkin.config import load_session
>>> from pathlib import Path
>>>
>>> # Option 1: Parse from full Session object (recommended)
>>> session = load_session("data/raw/Session-001/session.toml")
>>> bpod_data = parse_bpod_session(session)  # session_dir auto-detected
>>>
>>> # Option 2: Parse from BpodSession config with explicit session_dir
>>> from w2t_bkin.domain.session import BpodSession
>>> bpod_cfg = BpodSession(path="Bpod/*.mat", order="name_asc")
>>> bpod_data = parse_bpod_session(bpod_cfg, Path("data/raw/Session-001"))
>>>
>>> # Option 3: Parse single Bpod file directly
>>> bpod_path = Path("data/raw/Session-001/Bpod/session.mat")
>>> bpod_data = parse_bpod_mat(bpod_path)
>>>
>>> # Extract trial outcomes
>>> trials = extract_trials(bpod_data)
>>> print(f"Extracted {len(trials)} trials")
>>> print(f"First trial outcome: {trials[0].outcome}")
>>>
>>> # Extract behavioral events
>>> events = extract_behavioral_events(bpod_data)
>>> categories = set(e.event_type for e in events)
>>> print(f"Event categories: {categories}")
"""

from datetime import datetime
import glob
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Union

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

from .domain import Trial, TrialEvent, TrialSummary
from .domain.session import BpodSession, Session
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


def discover_bpod_files(bpod_session: BpodSession, session_dir: Path) -> List[Path]:
    """Discover Bpod .mat files from session configuration.

    Args:
        bpod_session: BpodSession configuration with path pattern and ordering
        session_dir: Base directory for resolving glob patterns

    Returns:
        Sorted list of Bpod file paths

    Raises:
        BpodValidationError: If no files found or pattern invalid
    """
    pattern = bpod_session.path
    full_pattern = session_dir / pattern

    # Discover files matching pattern
    file_paths = [Path(p) for p in glob.glob(str(full_pattern))]

    if not file_paths:
        raise BpodValidationError(f"No Bpod files found matching pattern: {pattern}")

    # Sort according to ordering strategy
    if bpod_session.order == "name_asc":
        file_paths.sort(key=lambda p: p.name)
    elif bpod_session.order == "name_desc":
        file_paths.sort(key=lambda p: p.name, reverse=True)
    elif bpod_session.order == "time_asc":
        file_paths.sort(key=lambda p: p.stat().st_mtime)
    elif bpod_session.order == "time_desc":
        file_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    logger.info(f"Discovered {len(file_paths)} Bpod files with order '{bpod_session.order}'")
    return file_paths


def merge_bpod_sessions(file_paths: List[Path]) -> Dict[str, Any]:
    """Merge multiple Bpod .mat files into unified session data.

    Combines trials from multiple Bpod files in order, updating trial numbers
    and timestamps to create a continuous session.

    Args:
        file_paths: Ordered list of Bpod .mat file paths

    Returns:
        Merged Bpod data dictionary with combined trials

    Raises:
        BpodParseError: If files cannot be parsed or merged
    """
    if not file_paths:
        raise BpodParseError("No Bpod files to merge")

    if len(file_paths) == 1:
        # Single file - just parse and return
        return parse_bpod_mat(file_paths[0])

    # Parse all files
    parsed_files = []
    for path in file_paths:
        try:
            data = parse_bpod_mat(path)
            parsed_files.append((path, data))
        except Exception as e:
            logger.error(f"Failed to parse {path.name}: {e}")
            raise

    # Start with first file as base
    _, merged_data = parsed_files[0]
    merged_session = _convert_matlab_struct(merged_data["SessionData"])

    # Extract base data
    all_trials = []
    all_start_times = []
    all_end_times = []
    all_raw_events = []
    all_trial_settings = []
    all_trial_types = []

    # Add first file's data
    first_raw_events = _convert_matlab_struct(merged_session["RawEvents"])
    all_trials.extend(first_raw_events["Trial"])
    all_start_times.extend(merged_session["TrialStartTimestamp"])
    all_end_times.extend(merged_session["TrialEndTimestamp"])
    all_trial_settings.extend(merged_session.get("TrialSettings", []))
    all_trial_types.extend(merged_session.get("TrialTypes", []))

    # Merge subsequent files
    for path, data in parsed_files[1:]:
        session_data = _convert_matlab_struct(data["SessionData"])
        raw_events = _convert_matlab_struct(session_data["RawEvents"])

        # Get trial offset (time of last trial end)
        time_offset = all_end_times[-1] if all_end_times else 0.0

        # Append trials with time offset
        all_trials.extend(raw_events["Trial"])

        # Offset timestamps
        start_times = session_data["TrialStartTimestamp"]
        end_times = session_data["TrialEndTimestamp"]

        if isinstance(start_times, (list, tuple)):
            all_start_times.extend([t + time_offset for t in start_times])
            all_end_times.extend([t + time_offset for t in end_times])
        else:
            all_start_times.append(start_times + time_offset)
            all_end_times.append(end_times + time_offset)

        # Append settings and types
        all_trial_settings.extend(session_data.get("TrialSettings", []))
        all_trial_types.extend(session_data.get("TrialTypes", []))

        logger.debug(f"Merged {path.name}: added {session_data['nTrials']} trials")

    # Update merged data
    merged_session["nTrials"] = len(all_trials)
    merged_session["TrialStartTimestamp"] = all_start_times
    merged_session["TrialEndTimestamp"] = all_end_times
    merged_session["RawEvents"]["Trial"] = all_trials
    merged_session["TrialSettings"] = all_trial_settings
    merged_session["TrialTypes"] = all_trial_types

    merged_data["SessionData"] = merged_session

    logger.info(f"Merged {len(file_paths)} Bpod files into {len(all_trials)} total trials")
    return merged_data


def parse_bpod_session(bpod_session_or_session: Union[BpodSession, Session], session_dir: Union[Path, str, None] = None) -> Dict[str, Any]:
    """Parse Bpod session from configuration with file discovery and merging.

    High-level function that:
    1. Discovers files from glob pattern
    2. Orders files according to strategy
    3. Merges multiple files if needed

    Args:
        bpod_session_or_session: BpodSession configuration or full Session object
        session_dir: Base directory for session (required if bpod_session_or_session
                     is BpodSession, optional if Session)

    Returns:
        Unified Bpod data dictionary (single or merged)

    Raises:
        BpodValidationError: If no files found
        BpodParseError: If parsing/merging fails
        ValueError: If session_dir cannot be determined

    Examples:
        >>> # Option 1: Use full Session object (recommended)
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/Session-001/session.toml")
        >>> data = parse_bpod_session(session)
        >>> trials = extract_trials(data)
        >>>
        >>> # Option 2: Use BpodSession with explicit session_dir
        >>> from w2t_bkin.domain.session import BpodSession
        >>> bpod_cfg = BpodSession(path="Bpod/*.mat", order="name_asc")
        >>> data = parse_bpod_session(bpod_cfg, Path("data/Session-001"))
    """
    # Extract BpodSession and session_dir
    if isinstance(bpod_session_or_session, Session):
        bpod_session = bpod_session_or_session.bpod
        if session_dir is None:
            session_dir = Path(bpod_session_or_session.session_dir)
    else:
        bpod_session = bpod_session_or_session
        if session_dir is None:
            raise ValueError(
                "session_dir must be provided when using BpodSession directly. "
                "Use parse_bpod_session(session) with full Session object, "
                "or parse_bpod_session(bpod_session, session_dir)."
            )

    session_dir = Path(session_dir) if isinstance(session_dir, str) else session_dir

    # Discover files
    file_paths = discover_bpod_files(bpod_session, session_dir)

    # Merge if multiple files
    merged_data = merge_bpod_sessions(file_paths)

    return merged_data


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


def extract_trials(data: Dict[str, Any]) -> List[Trial]:
    """Extract trial data from parsed Bpod data with validation.

    Args:
        data: Parsed Bpod data dictionary

    Returns:
        List of Trial objects

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
            outcome_str = _infer_outcome(states)

            # Map string outcome to TrialOutcome enum
            from .domain import TrialOutcome

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
                    trial_type=1,  # Default trial type, can be enhanced later
                    start_time=start_time,
                    end_time=stop_time,
                    outcome=outcome,
                    events=[],  # Events extracted separately
                )
            )
        except Exception as e:
            raise BpodParseError(f"Failed to extract trial {i + 1}: {type(e).__name__}")

    logger.info(f"Extracted {len(trials)} trials from Bpod file")
    return trials


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(data: Dict[str, Any]) -> List[TrialEvent]:
    """Extract behavioral events from parsed Bpod data with sanitization.

    Args:
        data: Parsed Bpod data dictionary

    Returns:
        List of TrialEvent objects with sanitized event types
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
                    events.append(
                        TrialEvent(
                            event_type=safe_event_type,
                            timestamp=float(timestamp),
                            metadata={"trial_number": float(trial_num)},
                        )
                    )

    logger.info(f"Extracted {len(events)} behavioral events from Bpod file")
    return events


# =============================================================================
# Event Summary Creation
# =============================================================================


def create_event_summary(session_id: str, trials: List[Trial], events: List[TrialEvent], bpod_files: List[str]) -> TrialSummary:
    """Create event summary for QC report with validated data.

    Args:
        session_id: Session identifier
        trials: List of extracted trials
        events: List of extracted behavioral events
        bpod_files: List of source Bpod file paths

    Returns:
        TrialSummary object for QC reporting
    """
    # Count outcomes
    outcome_counts = {}
    for trial in trials:
        outcome_str = trial.outcome.value  # Get string value from enum
        outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

    # Count trial types
    trial_type_counts = {}
    for trial in trials:
        trial_type_counts[trial.trial_type] = trial_type_counts.get(trial.trial_type, 0) + 1

    # Calculate mean trial duration
    durations = [trial.duration for trial in trials]
    mean_trial_duration = sum(durations) / len(durations) if durations else 0.0

    # Calculate mean response latency (only for trials with valid latency)
    latencies = [trial.response_latency for trial in trials if trial.response_latency is not None]
    mean_response_latency = sum(latencies) / len(latencies) if latencies else None

    # Extract unique event categories
    event_categories = sorted(set(e.event_type for e in events))

    summary = TrialSummary(
        session_id=session_id,
        total_trials=len(trials),
        outcome_counts=outcome_counts,
        trial_type_counts=trial_type_counts,
        mean_trial_duration=mean_trial_duration,
        mean_response_latency=mean_response_latency,
        event_categories=event_categories,
        bpod_files=bpod_files,
        generated_at=datetime.utcnow().isoformat(),
    )

    logger.info(f"Created event summary: {len(trials)} trials, {len(events)} events")
    return summary


def write_event_summary(summary: TrialSummary, output_path: Path) -> None:
    """Write event summary to JSON file.

    Args:
        summary: TrialSummary object to write
        output_path: Destination path for JSON file
    """
    data = summary.model_dump()
    write_json(data, output_path)
    logger.info(f"Wrote event summary to {output_path.name}")


if __name__ == "__main__":
    """Usage examples for events module."""
    from pathlib import Path

    print("=" * 70)
    print("W2T-BKIN Events Module - Usage Examples")
    print("=" * 70)
    print()

    print("Example: Parse Bpod .mat file and extract behavioral data")
    print("-" * 50)
    print()

    # Example with fixture path
    fixture_path = Path("tests/fixtures/sessions/bpod_example.mat")

    if fixture_path.exists():
        print(f"Loading Bpod file: {fixture_path}")

        # Parse .mat file
        bpod_data = parse_bpod_mat(fixture_path)
        print(f"✓ Parsed Bpod data with {len(bpod_data.get('SessionData', {}).get('nTrials', 0))} trials")

        # Extract trials
        trials = extract_trials(bpod_data)
        print(f"✓ Extracted {len(trials)} trial records")

        if trials:
            print(f"  First trial: {trials[0].trial_number}, outcome: {trials[0].outcome}")

        # Extract behavioral events
        events = extract_behavioral_events(bpod_data)
        print(f"✓ Extracted {len(events)} behavioral events")

        if events:
            categories = set(e.event_type for e in events)
            print(f"  Event categories: {', '.join(sorted(categories))}")

        # Create summary
        summary = create_event_summary(session_id="Session-Example", trials=trials, events=events, bpod_files=[str(fixture_path)])
        print(f"✓ Created summary: {summary.total_trials} trials, {len(summary.event_categories)} event types")

    else:
        print("Note: Example requires Bpod fixture file")
        print("In production, use:")
        print()
        print("  from w2t_bkin.events import parse_bpod_mat, extract_trials")
        print("  bpod_data = parse_bpod_mat('path/to/bpod.mat')")
        print("  trials = extract_trials(bpod_data)")
        print("  events = extract_behavioral_events(bpod_data)")

    print()
    print("=" * 70)
    print("Examples completed. See module docstring for API details.")
    print("=" * 70)
