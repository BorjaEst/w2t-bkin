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
- **TTL Alignment**: Automatic absolute time alignment using external TTL pulses

Main Functions:
---------------
High-level API (recommended for users):
- extract_trials(session): Extract trials with automatic data loading and TTL alignment
- extract_behavioral_events(session): Extract events with automatic alignment
- create_event_summary(session, trials, events): Generate QC summary from Session

Low-level API (for advanced use cases):
- parse_bpod_mat: Load and validate single Bpod .mat file
- parse_bpod_session: Discover and merge multiple Bpod files from Session config
- discover_bpod_files: Find Bpod files matching glob pattern
- merge_bpod_sessions: Combine multiple Bpod files into unified session
- align_bpod_trials_to_ttl: Convert relative timestamps to absolute using TTLs

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
1. Session → Load .mat files → Raw MATLAB structures
2. Validate SessionData structure
3. Extract trials → Trial objects (absolute or relative timestamps)
4. Extract events → TrialEvent objects (aligned to trials)
5. Create summary → TrialSummary (counts, categories, warnings)

Example (Recommended - Session-based):
--------------------------------------
>>> from w2t_bkin.config import load_session
>>> from w2t_bkin.events import extract_trials, extract_behavioral_events, create_event_summary
>>>
>>> # Load session configuration
>>> session = load_session("data/raw/Session-001/session.toml")
>>>
>>> # Extract trials (automatic loading and alignment)
>>> trials, offsets, warnings = extract_trials(session)
>>> print(f"Extracted {len(trials)} trials with absolute timestamps")
>>>
>>> # Extract behavioral events (automatic alignment)
>>> events = extract_behavioral_events(session, trial_offsets=offsets)
>>> print(f"Extracted {len(events)} events")
>>>
>>> # Generate QC summary
>>> summary = create_event_summary(session, trials, events, alignment_warnings=warnings)
>>> print(f"Session: {summary.session_id}, Trials: {summary.total_trials}")

Example (Advanced - Dict-based for unit testing):
--------------------------------------------------
>>> from pathlib import Path
>>> from w2t_bkin.events import parse_bpod_mat, extract_trials, extract_behavioral_events
>>>
>>> # Parse single file
>>> bpod_path = Path("data/raw/Session-001/Bpod/session.mat")
>>> bpod_data = parse_bpod_mat(bpod_path)
>>>
>>> # Extract trial outcomes (relative timestamps)
>>> trials, _, _ = extract_trials(bpod_data)
>>> print(f"Extracted {len(trials)} trials")
>>>
>>> # Extract behavioral events (relative timestamps)
>>> events = extract_behavioral_events(bpod_data)
>>> print(f"Extracted {len(events)} events")
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

from .domain import Trial, TrialEvent, TrialSummary
from .domain.session import BpodSession, Session
from .domain.trials import TrialOutcome
from .utils import (
    convert_matlab_struct,
    discover_files,
    is_nan_or_none,
    sanitize_string,
    sort_files,
    validate_against_whitelist,
    validate_file_exists,
    validate_file_size,
    write_json,
)

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
    # Validate file exists
    validate_file_exists(path, BpodValidationError, "Bpod file not found")

    # Check file extension
    if path.suffix.lower() not in [".mat"]:
        raise BpodValidationError(f"Invalid file extension: {path.suffix}")

    # Check file size (prevent memory exhaustion)
    try:
        file_size_mb = validate_file_size(path, max_size_mb=MAX_BPOD_FILE_SIZE_MB)
        logger.debug(f"Validated Bpod file: {path.name} ({file_size_mb:.2f}MB)")
    except ValueError as e:
        # Re-raise as BpodValidationError for consistent error handling
        raise BpodValidationError(str(e))


def _sanitize_event_type(event_type: str) -> str:
    """Sanitize event type string from external data.

    Removes potentially dangerous characters and limits length.

    Args:
        event_type: Raw event type string from .mat file

    Returns:
        Sanitized event type string
    """
    return sanitize_string(event_type, max_length=100, allowed_pattern="printable", default="unknown_event")


def _validate_outcome(outcome: str) -> str:
    """Validate trial outcome against whitelist.

    Args:
        outcome: Inferred outcome string

    Returns:
        Validated outcome (defaults to 'unknown' if invalid)
    """
    return validate_against_whitelist(outcome, VALID_OUTCOMES, default="unknown", warn=True)


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
    # Discover files matching pattern
    file_paths = discover_files(session_dir, bpod_session.path, sort=False)

    if not file_paths:
        raise BpodValidationError(f"No Bpod files found matching pattern: {bpod_session.path}")

    # Sort according to ordering strategy
    file_paths = sort_files(file_paths, bpod_session.order)

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
    merged_session = convert_matlab_struct(merged_data["SessionData"])

    # Extract base data
    all_trials = []
    all_start_times = []
    all_end_times = []
    all_raw_events = []
    all_trial_settings = []
    all_trial_types = []

    # Add first file's data
    first_raw_events = convert_matlab_struct(merged_session["RawEvents"])
    all_trials.extend(first_raw_events["Trial"])
    all_start_times.extend(merged_session["TrialStartTimestamp"])
    all_end_times.extend(merged_session["TrialEndTimestamp"])
    all_trial_settings.extend(merged_session.get("TrialSettings", []))
    all_trial_types.extend(merged_session.get("TrialTypes", []))

    # Merge subsequent files
    for path, data in parsed_files[1:]:
        session_data = convert_matlab_struct(data["SessionData"])
        raw_events = convert_matlab_struct(session_data["RawEvents"])

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


def parse_bpod_session(session: Session) -> Dict[str, Any]:
    """Parse Bpod session from configuration with file discovery and merging.

    High-level function that:
    1. Discovers files from glob pattern
    2. Orders files according to strategy
    3. Merges multiple files if needed

    Args:
        session: Full Session object containing Bpod configuration and session_dir

    Returns:
        Unified Bpod data dictionary (single or merged)

    Raises:
        BpodValidationError: If no files found
        BpodParseError: If parsing/merging fails

    Examples:
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/Session-001/session.toml")
        >>> data = parse_bpod_session(session)
        >>> trials = extract_trials(data)
    """
    session_dir = Path(session.session_dir)

    # Discover files
    file_paths = discover_bpod_files(session.bpod, session_dir)

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

    session_data = convert_matlab_struct(data["SessionData"])

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

    raw_events = convert_matlab_struct(session_data["RawEvents"])

    if "Trial" not in raw_events:
        logger.warning("Missing 'Trial' in RawEvents")
        return False

    logger.debug("Bpod structure validation passed")
    return True


# =============================================================================
# TTL-to-Trial Alignment
# =============================================================================


def _get_sync_time_from_trial(trial_data: Dict[str, Any], sync_signal: str) -> Optional[float]:
    """Extract synchronization signal timing from trial data.

    Args:
        trial_data: Raw trial data from Bpod containing States
        sync_signal: State name to use for sync (e.g., "W2L_Audio", "A2L_Audio")

    Returns:
        Start time of sync signal (relative to trial start), or None if not found/visited
    """
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
    bpod_data: Dict[str, Any],
    ttl_pulses: Dict[str, List[float]],
) -> Tuple[List[Trial], Dict[int, float], List[str]]:
    """Align Bpod trials to absolute time using TTL sync signals.

    Converts Bpod relative timestamps to absolute time by matching per-trial
    sync signals to corresponding TTL pulses. Returns aligned Trial objects
    with absolute start_time/stop_time, per-trial offsets, and warnings.

    Algorithm:
    1. For each trial, determine trial_type and lookup sync configuration
    2. Extract sync_signal start time (relative to trial start)
    3. Match to next available TTL pulse from corresponding channel
    4. Compute offset_abs = ttl_pulse_time - bpod_sync_time_rel
    5. Convert all trial times to absolute: t_abs = offset_abs + t_rel

    Edge Cases:
    - Missing sync_signal: Skip trial, record warning
    - Extra TTL pulses: Ignore surplus, log warning
    - Fewer TTL pulses: Align what's possible, mark remaining as unaligned
    - Jitter: Allow small timing differences, log debug info

    Args:
        session: Session config with trial_type sync mappings
        bpod_data: Parsed Bpod data (SessionData structure)
        ttl_pulses: Dict mapping TTL channel ID to sorted list of absolute timestamps

    Returns:
        Tuple of:
        - List[Trial]: Aligned trials with absolute timestamps
        - Dict[int, float]: Map trial_number → absolute offset for events alignment
        - List[str]: Alignment warnings

    Raises:
        BpodParseError: If trial_type config missing or data structure invalid
    """
    if not validate_bpod_structure(bpod_data):
        raise BpodParseError("Invalid Bpod structure")

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials to align")
        return [], {}, []

    # Build trial_type → sync config mapping
    trial_type_map = {}
    for tt_config in session.bpod.trial_types:
        trial_type_map[tt_config.trial_type] = {
            "sync_signal": tt_config.sync_signal,
            "sync_ttl": tt_config.sync_ttl,
            "description": tt_config.description,
        }

    if not trial_type_map:
        raise BpodParseError("No trial_type sync configuration found in session.bpod.trial_types")

    # Prepare TTL pulse pointers (track consumption per channel)
    ttl_pointers = {ttl_id: 0 for ttl_id in ttl_pulses.keys()}

    # Extract raw trial data
    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]

    # Extract TrialTypes if available
    trial_types_array = session_data.get("TrialTypes")
    if trial_types_array is None:
        # Default to trial_type 1 for all trials if not specified
        trial_types_array = [1] * n_trials
        logger.warning("TrialTypes not found in Bpod data, defaulting all trials to type 1")

    aligned_trials = []
    trial_offsets = {}
    warnings_list = []

    for i in range(n_trials):
        trial_num = i + 1
        trial_data = convert_matlab_struct(trial_data_list[i])

        # Get trial type
        trial_type = int(trial_types_array[i])
        if trial_type not in trial_type_map:
            warnings_list.append(f"Trial {trial_num}: trial_type {trial_type} not in session config, skipping")
            logger.warning(warnings_list[-1])
            continue

        sync_config = trial_type_map[trial_type]
        sync_signal = sync_config["sync_signal"]
        sync_ttl_id = sync_config["sync_ttl"]

        # Extract sync time from trial (relative to trial start)
        sync_time_rel = _get_sync_time_from_trial(trial_data, sync_signal)
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

        # Compute offset: absolute_time = offset + relative_time
        offset_abs = ttl_pulse_time - sync_time_rel
        trial_offsets[trial_num] = offset_abs

        # Convert relative times to absolute
        start_time_rel = float(start_timestamps[i])
        stop_time_rel = float(end_timestamps[i])

        start_time_abs = offset_abs + start_time_rel
        stop_time_abs = offset_abs + stop_time_rel

        # Validate monotonicity
        if start_time_abs >= stop_time_abs:
            warnings_list.append(f"Trial {trial_num}: start_time >= stop_time after alignment, skipping")
            logger.error(warnings_list[-1])
            continue

        # Extract states for outcome inference
        states = trial_data.get("States", {})
        states = convert_matlab_struct(states)
        outcome_str = _infer_outcome(states)

        # Map outcome string to TrialOutcome enum
        outcome_map = {
            "hit": TrialOutcome.HIT,
            "miss": TrialOutcome.MISS,
            "correct_rejection": TrialOutcome.CORRECT_REJECTION,
            "false_alarm": TrialOutcome.FALSE_ALARM,
            "unknown": TrialOutcome.MISS,
        }
        outcome = outcome_map.get(outcome_str, TrialOutcome.MISS)

        # Create Trial with absolute timestamps
        aligned_trials.append(
            Trial(
                trial_number=trial_num,
                trial_type=trial_type,
                start_time=start_time_abs,
                stop_time=stop_time_abs,
                outcome=outcome,
            )
        )

        logger.debug(
            f"Trial {trial_num}: type={trial_type}, sync_signal={sync_signal}, "
            f"sync_rel={sync_time_rel:.4f}s, ttl_abs={ttl_pulse_time:.4f}s, "
            f"offset={offset_abs:.4f}s, start_abs={start_time_abs:.4f}s"
        )

    # Warn about unused TTL pulses
    for ttl_id, ptr in ttl_pointers.items():
        unused = len(ttl_pulses[ttl_id]) - ptr
        if unused > 0:
            warnings_list.append(f"TTL channel '{ttl_id}' has {unused} unused pulses")
            logger.warning(warnings_list[-1])

    logger.info(f"Aligned {len(aligned_trials)} out of {n_trials} trials using TTL sync")
    return aligned_trials, trial_offsets, warnings_list


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
    return not is_nan_or_none(start_time)


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


def extract_trials(
    session: Union[Session, Dict[str, Any]],
) -> Tuple[List[Trial], Optional[Dict[int, float]], Optional[List[str]]]:
    """Extract trial data from Session or parsed Bpod data with automatic TTL alignment.

    Simplified API that accepts either:
    - Session: Automatically loads Bpod data and performs TTL alignment if configured
    - Dict: Parsed Bpod data (backwards compatible, relative timestamps only)

    Args:
        session: Session configuration OR parsed Bpod data dictionary

    Returns:
        Tuple of:
        - List[Trial]: Trial objects with absolute (if Session with trial_types) or relative timestamps
        - Optional[Dict[int, float]]: Per-trial offsets (only if aligned)
        - Optional[List[str]]: Alignment warnings (only if aligned)

    Raises:
        BpodParseError: If structure is invalid or extraction fails
        TypeError: If session parameter is neither Session nor Dict

    Examples:
        >>> # Recommended: Session-based (automatic loading and alignment)
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/Session-001/session.toml")
        >>> trials, offsets, warnings = extract_trials(session)
        >>>
        >>> # Backwards compatible: Dict-based (relative timestamps)
        >>> data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>> trials, _, _ = extract_trials(data)
    """
    # Check if Session object or raw data dict
    if isinstance(session, Session):
        # Validate Session object has required attributes
        if not hasattr(session, "bpod"):
            raise TypeError("Session object is missing 'bpod' attribute. " "Ensure session was loaded correctly using load_session().")
        if not hasattr(session, "session_dir"):
            raise TypeError("Session object is missing 'session_dir' attribute. " "Ensure session was loaded correctly using load_session().")

        # Load Bpod data from session
        data = parse_bpod_session(session)

        # If session has trial_types, load TTL pulses and use alignment
        if session.bpod.trial_types:
            from .sync import get_ttl_pulses

            ttl_pulses = get_ttl_pulses(session)
            return align_bpod_trials_to_ttl(session, data, ttl_pulses)
    elif isinstance(session, dict):
        # Backwards compatible: treat as parsed Bpod data dict
        data = session
    else:
        raise TypeError(f"extract_trials() expects Session or Dict, got {type(session).__name__}. " f"Use load_session() to load a Session object, or pass parsed Bpod data dict.")

    # Extract trials with relative timestamps
    if not validate_bpod_structure(data):
        raise BpodParseError("Invalid Bpod structure")

    session_data = convert_matlab_struct(data["SessionData"])
    n_trials = int(session_data["nTrials"])

    if n_trials == 0:
        logger.info("No trials found in Bpod file")
        return [], None, None

    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]
    raw_events = convert_matlab_struct(session_data["RawEvents"])
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
            states = convert_matlab_struct(states)
            outcome_str = _infer_outcome(states)

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
                    trial_type=1,  # Default trial type if not aligned
                    start_time=start_time,
                    stop_time=stop_time,
                    outcome=outcome,
                )
            )
        except Exception as e:
            raise BpodParseError(f"Failed to extract trial {i + 1}: {type(e).__name__}")

    logger.info(f"Extracted {len(trials)} trials from Bpod file")
    return trials, None, None


# =============================================================================
# Behavioral Event Extraction
# =============================================================================


def extract_behavioral_events(
    session: Union[Session, Dict[str, Any]],
    trials: Optional[List[Trial]] = None,
    trial_offsets: Optional[Dict[int, float]] = None,
) -> List[TrialEvent]:
    """Extract behavioral events from Session or parsed Bpod data with automatic alignment.

    Simplified API that accepts either:
    - Session: Automatically loads Bpod data and computes alignment if configured
    - Dict: Parsed Bpod data (backwards compatible, uses provided trial_offsets if any)

    Args:
        session: Session configuration OR parsed Bpod data dictionary
        trials: Optional pre-extracted trials (for reusing extract_trials results)
        trial_offsets: Optional pre-computed trial offsets (for reusing extract_trials results)

    Returns:
        List of TrialEvent objects with absolute or relative timestamps

    Examples:
        >>> # Recommended: Session-based (automatic loading and alignment)
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/Session-001/session.toml")
        >>> events = extract_behavioral_events(session)
        >>>
        >>> # Or reuse trials/offsets from extract_trials
        >>> trials, offsets, _ = extract_trials(session)
        >>> events = extract_behavioral_events(session, trials=trials, trial_offsets=offsets)
        >>>
        >>> # Backwards compatible: Dict-based
        >>> data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>> events = extract_behavioral_events(data)
    """
    # Check if Session object or raw data dict
    if isinstance(session, Session):
        # Load Bpod data from session
        data = parse_bpod_session(session)

        # If trial_offsets not provided but session has trial_types, compute them
        if trial_offsets is None and session.bpod.trial_types:
            _, trial_offsets, _ = extract_trials(session)
    else:
        # Backwards compatible: treat as parsed Bpod data dict
        data = session

    if not validate_bpod_structure(data):
        logger.warning("Invalid Bpod structure, returning empty event list")
        return []

    session_data = convert_matlab_struct(data["SessionData"])
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
            safe_event_type = _sanitize_event_type(event_type)

            if not isinstance(timestamps, (list, tuple)):
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


# =============================================================================
# Event Summary Creation
# =============================================================================


def create_event_summary(
    session: Union[Session, str],
    trials: List[Trial],
    events: List[TrialEvent],
    bpod_files: Optional[List[str]] = None,
    n_total_trials: Optional[int] = None,
    alignment_warnings: Optional[List[str]] = None,
) -> TrialSummary:
    """Create event summary for QC report from Session and extracted data.

    Simplified API that accepts either:
    - Session: Automatically extracts session_id and bpod_files from Session object
    - str: Session ID (backwards compatible, requires bpod_files parameter)

    Args:
        session: Session configuration OR session ID string
        trials: List of extracted trials
        events: List of extracted behavioral events
        bpod_files: List of Bpod file paths (required if session is str, ignored if Session)
        n_total_trials: Total trials before alignment (for computing n_dropped)
        alignment_warnings: List of alignment warnings (if alignment was performed)

    Returns:
        TrialSummary object for QC reporting

    Examples:
        >>> # Recommended: Session-based
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/Session-001/session.toml")
        >>> trials, offsets, warnings = extract_trials(session)
        >>> events = extract_behavioral_events(session, trial_offsets=offsets)
        >>> summary = create_event_summary(session, trials, events, alignment_warnings=warnings)
        >>>
        >>> # Backwards compatible: session_id string
        >>> summary = create_event_summary("session-001", trials, events, bpod_files=["/path/to/bpod.mat"])
    """
    # Check if Session object or session_id string
    if isinstance(session, Session):
        # Extract session ID from Session
        session_id = session.session.id

        # Extract Bpod file paths from Session
        from pathlib import Path

        session_dir = Path(session.session_dir)
        bpod_files_paths = discover_bpod_files(session.bpod, session_dir)
        bpod_files = [str(p) for p in bpod_files_paths]
    else:
        # Backwards compatible: treat as session_id string
        session_id = session
        if bpod_files is None:
            raise ValueError("bpod_files parameter required when session is a string")

    # Count outcomes
    outcome_counts = {}
    for trial in trials:
        outcome_str = trial.outcome.value  # Get string value from enum
        outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

    # Count trial types
    trial_type_counts = {}
    for trial in trials:
        trial_type_counts[trial.trial_type] = trial_type_counts.get(trial.trial_type, 0) + 1

    # Calculate mean trial duration from start_time/stop_time
    durations = [trial.stop_time - trial.start_time for trial in trials]
    mean_trial_duration = sum(durations) / len(durations) if durations else 0.0

    # Calculate mean response latency (only for trials with response_time field)
    latencies = []
    for trial in trials:
        # Check if trial has response_time field (protocol-specific)
        trial_dict = trial.model_dump()
        if "response_time" in trial_dict and trial_dict["response_time"] is not None:
            latency = trial_dict["response_time"] - trial.start_time
            latencies.append(latency)

    mean_response_latency = sum(latencies) / len(latencies) if latencies else None

    # Extract unique event categories
    event_categories = sorted(set(e.event_type for e in events))

    # Compute alignment stats if applicable
    n_aligned = None
    n_dropped = None
    if n_total_trials is not None:
        n_aligned = len(trials)
        n_dropped = n_total_trials - n_aligned

    summary = TrialSummary(
        session_id=session_id,
        total_trials=n_total_trials if n_total_trials is not None else len(trials),
        n_aligned=n_aligned,
        n_dropped=n_dropped,
        outcome_counts=outcome_counts,
        trial_type_counts=trial_type_counts,
        mean_trial_duration=mean_trial_duration,
        mean_response_latency=mean_response_latency,
        event_categories=event_categories,
        bpod_files=bpod_files,
        alignment_warnings=alignment_warnings if alignment_warnings is not None else [],
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
