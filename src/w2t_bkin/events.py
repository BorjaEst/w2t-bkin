"""Events module for W2T-BKIN pipeline (Phase 3 - Behavioral Data)."""Events module for W2T-BKIN pipeline (Phase 3 - Behavioral Data)."""Events module for W2T-BKIN pipeline (Phase 3 - Behavioral Data).



This module is now a facade that re-exports all public APIs from the events subpackage.



For the refactored structure, see:**This module now re-exports all public APIs from the events subpackage.**Parses Bpod behavioral task data from .mat files (MATLAB format) and extracts:

- events.bpod: Bpod file I/O operations

- events.trials: Trial extraction and outcome inference  - Trial data: trial numbers, outcomes (hit/miss/correct reject), start/end times

- events.behavior: Behavioral event extraction

- events.summary: QC summary creationFor the refactored structure, see:- Behavioral events: state entries/exits, port interactions, stimulus presentations

- events.exceptions: Error types

- events.bpod: Bpod file I/O operations- QC summaries: trial counts, outcome distributions, event categories

All public functions remain available at the top level for backward compatibility.

"""- events.trials: Trial extraction and outcome inference  



# Re-export all public APIs from events subpackage for backward compatibility- events.behavior: Behavioral event extractionThe module uses scipy.io.loadmat for MATLAB file parsing and implements robust

from .events import (

    # Exceptions- events.summary: QC summary creationvalidation for Bpod data structure variations across different task protocols.

    BpodParseError,

    BpodValidationError,- events.exceptions: Error types

    EventsError,

    # Bpod operations**Note**: This module handles Bpod data parsing and extraction only. For TTL-based

    discover_bpod_files,

    index_bpod_data,All public functions remain available at the top level for backward compatibility:temporal alignment, use the sync module (sync.get_ttl_pulses, sync.align_bpod_trials_to_ttl).

    merge_bpod_sessions,

    parse_bpod_mat,

    parse_bpod_session,

    validate_bpod_structure,    from w2t_bkin.events import (Key Features:

    write_bpod_mat,

    # Trial extraction        parse_bpod_mat,-------------

    extract_trials,

    # Behavioral events        extract_trials,- **Bpod Compatibility**: Handles SessionData structure from Bpod r2.5+

    extract_behavioral_events,

    # Summary        extract_behavioral_events,- **Trial Extraction**: Parses trial outcomes and timing from States/RawEvents

    create_event_summary,

    write_event_summary,        create_event_summary,- **Event Extraction**: Converts Bpod events to standardized TrialEvent format

)

    )- **Outcome Inference**: Derives trial outcomes from state visit patterns

__all__ = [

    # Exceptions- **QC Summaries**: Generates statistics for quality control

    "EventsError",

    "BpodParseError",Data Flow:- **Flexible Timestamps**: Supports both relative and absolute timestamps via offsets

    "BpodValidationError",

    # Bpod operations----------

    "parse_bpod_mat",

    "discover_bpod_files",1. Session → Load .mat files (bpod) → Raw MATLAB structuresMain Functions:

    "merge_bpod_sessions",

    "parse_bpod_session",2. Validate SessionData structure (bpod)---------------

    "validate_bpod_structure",

    "index_bpod_data",3. Extract trials (trials) → Trial objects (relative or absolute timestamps)High-level API (recommended):

    "write_bpod_mat",

    # Trial extraction4. Extract events (behavior) → TrialEvent objects (relative or absolute timestamps)- extract_trials: Extract trials from Bpod data with optional TTL offsets

    "extract_trials",

    # Behavioral events5. Create summary (summary) → TrialSummary (counts, categories, warnings)- extract_behavioral_events: Extract events from Bpod data with optional TTL offsets

    "extract_behavioral_events",

    # Summary- create_event_summary: Generate QC summary from Session and extracted data

    "create_event_summary",

    "write_event_summary",Example (Without TTL Alignment - Relative Timestamps):

]

-------------------------------------------------------Low-level API (for advanced use cases):

>>> from w2t_bkin.config import load_session- parse_bpod_mat: Load and validate single Bpod .mat file

>>> from w2t_bkin.events import parse_bpod_session, extract_trials, extract_behavioral_events, create_event_summary- parse_bpod_session: Discover and merge multiple Bpod files from Session config

>>>- discover_bpod_files: Find Bpod files matching glob pattern

>>> # Load session configuration- merge_bpod_sessions: Combine multiple Bpod files into unified session

>>> session = load_session("data/raw/Session-001/session.toml")

>>>Data manipulation API:

>>> # Parse Bpod data from session- index_bpod_data: Filter Bpod data to keep only specified trials

>>> bpod_data = parse_bpod_session(session)- write_bpod_mat: Write Bpod data dictionary back to .mat file

>>>

>>> # Extract trials with relative timestampsRequirements:

>>> trials = extract_trials(bpod_data)-------------

>>> print(f"Extracted {len(trials)} trials with relative timestamps")- FR-11: Behavioral event parsing from Bpod

>>>- FR-14: Trial outcome and timing extraction

>>> # Extract behavioral events with relative timestamps- NFR-7: Flexible handling of varying Bpod protocols

>>> events = extract_behavioral_events(bpod_data)

>>> print(f"Extracted {len(events)} events")Acceptance Criteria:

>>>-------------------

>>> # Generate QC summary- A4: Trial counts and event categories available for QC

>>> summary = create_event_summary(session, trials, events)

>>> print(f"Session: {summary.session_id}, Trials: {summary.total_trials}")Data Flow:

----------

Example (With TTL Alignment - Absolute Timestamps):1. Session → Load .mat files → Raw MATLAB structures

----------------------------------------------------2. Validate SessionData structure

>>> from w2t_bkin.config import load_session3. Extract trials → Trial objects (relative or absolute timestamps)

>>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl4. Extract events → TrialEvent objects (relative or absolute timestamps)

>>> from w2t_bkin.events import parse_bpod_session, extract_trials, extract_behavioral_events, create_event_summary5. Create summary → TrialSummary (counts, categories, warnings)

>>>

>>> # Load session and Bpod dataExample (Without TTL Alignment - Relative Timestamps):

>>> session = load_session("data/raw/Session-001/session.toml")-------------------------------------------------------

>>> bpod_data = parse_bpod_session(session)>>> from w2t_bkin.config import load_session

>>>>>> from w2t_bkin.events import parse_bpod_session, extract_trials, extract_behavioral_events, create_event_summary

>>> # Compute TTL-based temporal alignment (from sync module)>>>

>>> ttl_pulses = get_ttl_pulses(session)>>> # Load session configuration

>>> trial_offsets, align_warnings = align_bpod_trials_to_ttl(session, bpod_data, ttl_pulses)>>> session = load_session("data/raw/Session-001/session.toml")

>>>>>>

>>> # Extract trials and events with absolute timestamps>>> # Parse Bpod data from session

>>> trials = extract_trials(bpod_data, trial_offsets=trial_offsets)>>> bpod_data = parse_bpod_session(session)

>>> events = extract_behavioral_events(bpod_data, trial_offsets=trial_offsets)>>>

>>>>>> # Extract trials with relative timestamps

>>> # Generate QC summary with alignment info>>> trials = extract_trials(bpod_data)

>>> summary = create_event_summary(session, trials, events,>>> print(f"Extracted {len(trials)} trials with relative timestamps")

...                               n_total_trials=len(bpod_data['SessionData']['TrialStartTimestamp']),>>>

...                               alignment_warnings=align_warnings)>>> # Extract behavioral events with relative timestamps

>>> events = extract_behavioral_events(bpod_data)

Example (Dict-based for unit testing):>>> print(f"Extracted {len(events)} events")

--------------------------------------->>>

>>> from pathlib import Path>>> # Generate QC summary

>>> from w2t_bkin.events import parse_bpod_mat, extract_trials, extract_behavioral_events>>> summary = create_event_summary(session, trials, events)

>>>>>> print(f"Session: {summary.session_id}, Trials: {summary.total_trials}")

>>> # Parse single file

>>> bpod_path = Path("data/raw/Session-001/Bpod/session.mat")Example (With TTL Alignment - Absolute Timestamps):

>>> bpod_data = parse_bpod_mat(bpod_path)----------------------------------------------------

>>>>>> from w2t_bkin.config import load_session

>>> # Extract trial outcomes (relative timestamps)>>> from w2t_bkin.sync import get_ttl_pulses, align_bpod_trials_to_ttl

>>> trials = extract_trials(bpod_data)>>> from w2t_bkin.events import parse_bpod_session, extract_trials, extract_behavioral_events, create_event_summary

>>> print(f"Extracted {len(trials)} trials")>>>

>>>>>> # Load session and Bpod data

>>> # Extract behavioral events (relative timestamps)>>> session = load_session("data/raw/Session-001/session.toml")

>>> events = extract_behavioral_events(bpod_data)>>> bpod_data = parse_bpod_session(session)

>>> print(f"Extracted {len(events)} events")>>>

>>> # Compute TTL-based temporal alignment (from sync module)

Example (Filter and save Bpod data):>>> ttl_pulses = get_ttl_pulses(session)

------------------------------------->>> trial_offsets, align_warnings = align_bpod_trials_to_ttl(session, bpod_data, ttl_pulses)

>>> from pathlib import Path>>>

>>> from w2t_bkin.events import parse_bpod_mat, index_bpod_data, write_bpod_mat>>> # Extract trials and events with absolute timestamps

>>>>>> trials = extract_trials(bpod_data, trial_offsets=trial_offsets)

>>> # Load Bpod data>>> events = extract_behavioral_events(bpod_data, trial_offsets=trial_offsets)

>>> bpod_data = parse_bpod_mat(Path("data/raw/Session-001/Bpod/session.mat"))>>>

>>>>>> # Generate QC summary with alignment info

>>> # Keep only first 3 trials>>> summary = create_event_summary(session, trials, events,

>>> filtered_data = index_bpod_data(bpod_data, [0, 1, 2])...                               n_total_trials=len(bpod_data['SessionData']['TrialStartTimestamp']),

>>>...                               alignment_warnings=align_warnings)

>>> # Save filtered data back to .mat file

>>> write_bpod_mat(filtered_data, Path("data/processed/session_first3.mat"))Example (Dict-based for unit testing):

>>>---------------------------------------

>>> # Verify: reload and check>>> from pathlib import Path

>>> reloaded = parse_bpod_mat(Path("data/processed/session_first3.mat"))>>> from w2t_bkin.events import parse_bpod_mat, extract_trials, extract_behavioral_events

>>> print(f"Filtered file has {reloaded['SessionData']['nTrials']} trials")>>>

""">>> # Parse single file

>>> bpod_path = Path("data/raw/Session-001/Bpod/session.mat")

# Re-export all public APIs from events subpackage for backward compatibility>>> bpod_data = parse_bpod_mat(bpod_path)

from .events import (>>>

    # Exceptions>>> # Extract trial outcomes (relative timestamps)

    BpodParseError,>>> trials = extract_trials(bpod_data)

    BpodValidationError,>>> print(f"Extracted {len(trials)} trials")

    EventsError,>>>

    # Bpod operations>>> # Extract behavioral events (relative timestamps)

    discover_bpod_files,>>> events = extract_behavioral_events(bpod_data)

    index_bpod_data,>>> print(f"Extracted {len(events)} events")

    merge_bpod_sessions,

    parse_bpod_mat,Example (Filter and save Bpod data):

    parse_bpod_session,-------------------------------------

    validate_bpod_structure,>>> from pathlib import Path

    write_bpod_mat,>>> from w2t_bkin.events import parse_bpod_mat, index_bpod_data, write_bpod_mat

    # Trial extraction>>>

    extract_trials,>>> # Load Bpod data

    # Behavioral events>>> bpod_data = parse_bpod_mat(Path("data/raw/Session-001/Bpod/session.mat"))

    extract_behavioral_events,>>>

    # Summary>>> # Keep only first 3 trials

    create_event_summary,>>> filtered_data = index_bpod_data(bpod_data, [0, 1, 2])

    write_event_summary,>>>

)>>> # Save filtered data back to .mat file

>>> write_bpod_mat(filtered_data, Path("data/processed/session_first3.mat"))

__all__ = [>>>

    # Exceptions>>> # Verify: reload and check

    "EventsError",>>> reloaded = parse_bpod_mat(Path("data/processed/session_first3.mat"))

    "BpodParseError",>>> print(f"Filtered file has {reloaded['SessionData']['nTrials']} trials")

    "BpodValidationError","""

    # Bpod operations

    "parse_bpod_mat",from datetime import datetime

    "discover_bpod_files",import logging

    "merge_bpod_sessions",from pathlib import Path

    "parse_bpod_session",from typing import Any, Dict, List, Optional, Tuple, Union

    "validate_bpod_structure",

    "index_bpod_data",import numpy as np

    "write_bpod_mat",

    # Trial extractiontry:

    "extract_trials",    from scipy.io import loadmat, savemat

    # Behavioral eventsexcept ImportError:

    "extract_behavioral_events",    loadmat = None

    # Summary    savemat = None

    "create_event_summary",

    "write_event_summary",from .domain import Trial, TrialEvent, TrialSummary

]from .domain.exceptions import BpodParseError, BpodValidationError, EventsError

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
# Helper Functions for Numpy Array Handling
# =============================================================================


def _to_scalar(value: Union[Any, np.ndarray], index: int) -> Any:
    """Safely extract scalar value from numpy array or list.

    Handles both numpy arrays and regular Python lists/tuples.

    Args:
        value: Value to extract from (ndarray, list, tuple, or scalar)
        index: Index to extract

    Returns:
        Scalar value at index

    Raises:
        IndexError: If index is out of bounds
    """
    if isinstance(value, np.ndarray):
        # Handle numpy arrays (including 0-d arrays)
        if value.ndim == 0:
            return value.item()
        return value[index].item() if hasattr(value[index], "item") else value[index]
    elif isinstance(value, (list, tuple)):
        return value[index]
    else:
        # Assume it's already a scalar
        return value


def _to_list(value: Union[Any, np.ndarray]) -> List[Any]:
    """Convert numpy array or scalar to Python list.

    Args:
        value: Value to convert (ndarray, list, tuple, or scalar)

    Returns:
        Python list
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, (list, tuple)):
        return list(value)
    else:
        # Scalar value
        return [value]


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
    # Ensure RawEvents is a dict in merged_session
    merged_session["RawEvents"] = first_raw_events

    # Convert Trial to list if it's a mat_struct or numpy array
    trials = first_raw_events["Trial"]
    if hasattr(trials, "__dict__"):
        # mat_struct object - could be a single trial or not iterable
        # Try to iterate, if not possible, wrap in list
        try:
            trials = [convert_matlab_struct(trial) for trial in trials]
        except TypeError:
            # Single mat_struct object - wrap in list
            trials = [convert_matlab_struct(trials)]
    elif isinstance(trials, np.ndarray):
        # numpy array - convert to list
        trials = trials.tolist()
    elif not isinstance(trials, list):
        # Other types - wrap in list
        trials = list(trials) if hasattr(trials, "__iter__") else [trials]

    all_trials.extend(trials)

    # Convert timestamps to lists if they're numpy arrays
    start_times = merged_session["TrialStartTimestamp"]
    end_times = merged_session["TrialEndTimestamp"]
    if isinstance(start_times, np.ndarray):
        start_times = start_times.tolist()
    if isinstance(end_times, np.ndarray):
        end_times = end_times.tolist()

    all_start_times.extend(start_times if isinstance(start_times, list) else [start_times])
    all_end_times.extend(end_times if isinstance(end_times, list) else [end_times])

    # Convert settings and types to lists if they're numpy arrays
    trial_settings = merged_session.get("TrialSettings", [])
    trial_types = merged_session.get("TrialTypes", [])
    if isinstance(trial_settings, np.ndarray):
        trial_settings = trial_settings.tolist()
    if isinstance(trial_types, np.ndarray):
        trial_types = trial_types.tolist()

    all_trial_settings.extend(trial_settings if isinstance(trial_settings, list) else [trial_settings])
    all_trial_types.extend(trial_types if isinstance(trial_types, list) else [trial_types])

    # Merge subsequent files
    for path, data in parsed_files[1:]:
        session_data = convert_matlab_struct(data["SessionData"])
        raw_events = convert_matlab_struct(session_data["RawEvents"])

        # Get trial offset (time of last trial end)
        time_offset = all_end_times[-1] if all_end_times else 0.0

        # Convert Trial to list if it's a mat_struct or numpy array
        trials = raw_events["Trial"]
        if hasattr(trials, "__dict__"):
            # mat_struct object - could be a single trial or not iterable
            # Try to iterate, if not possible, wrap in list
            try:
                trials = [convert_matlab_struct(trial) for trial in trials]
            except TypeError:
                # Single mat_struct object - wrap in list
                trials = [convert_matlab_struct(trials)]
        elif isinstance(trials, np.ndarray):
            # numpy array - convert to list
            trials = trials.tolist()
        elif not isinstance(trials, list):
            # Other types - wrap in list
            trials = list(trials) if hasattr(trials, "__iter__") else [trials]

        # Append trials
        all_trials.extend(trials)

        # Offset timestamps
        start_times = session_data["TrialStartTimestamp"]
        end_times = session_data["TrialEndTimestamp"]

        # Convert numpy arrays to lists
        if isinstance(start_times, np.ndarray):
            start_times = start_times.tolist()
        if isinstance(end_times, np.ndarray):
            end_times = end_times.tolist()

        if isinstance(start_times, (list, tuple)):
            all_start_times.extend([t + time_offset for t in start_times])
            all_end_times.extend([t + time_offset for t in end_times])
        else:
            all_start_times.append(start_times + time_offset)
            all_end_times.append(end_times + time_offset)

        # Append settings and types
        trial_settings = session_data.get("TrialSettings", [])
        trial_types = session_data.get("TrialTypes", [])

        # Convert numpy arrays to lists
        if isinstance(trial_settings, np.ndarray):
            trial_settings = trial_settings.tolist()
        if isinstance(trial_types, np.ndarray):
            trial_types = trial_types.tolist()

        all_trial_settings.extend(trial_settings if isinstance(trial_settings, list) else [trial_settings])
        all_trial_types.extend(trial_types if isinstance(trial_types, list) else [trial_types])

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
# Bpod Data Manipulation
# =============================================================================


def index_bpod_data(bpod_data: Dict[str, Any], trial_indices: List[int]) -> Dict[str, Any]:
    """Index Bpod data to keep only specified trials.

    Creates a new Bpod data dictionary containing only the trials specified by
    their indices (0-based). All trial-related arrays (timestamps, events, settings,
    types) are filtered consistently.

    Args:
        bpod_data: Parsed Bpod data dictionary (from parse_bpod_mat or parse_bpod_session)
        trial_indices: List of 0-based trial indices to keep (e.g., [0, 1, 2] for first 3 trials)

    Returns:
        New Bpod data dictionary with filtered trials

    Raises:
        BpodParseError: If structure is invalid
        IndexError: If trial indices are out of bounds

    Examples:
        >>> from pathlib import Path
        >>> from w2t_bkin.events import parse_bpod_mat, index_bpod_data, write_bpod_mat
        >>>
        >>> # Load Bpod data
        >>> bpod_data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>>
        >>> # Keep only first 3 trials
        >>> filtered_data = index_bpod_data(bpod_data, [0, 1, 2])
        >>>
        >>> # Save filtered data
        >>> write_bpod_mat(filtered_data, Path("data/Bpod/session_first3.mat"))
        >>>
        >>> # Keep specific trials (e.g., trials 5, 10, 15)
        >>> selected_data = index_bpod_data(bpod_data, [4, 9, 14])
        >>> write_bpod_mat(selected_data, Path("data/Bpod/session_selected.mat"))
    """
    # Validate structure
    if not validate_bpod_structure(bpod_data):
        raise BpodParseError("Invalid Bpod structure")

    # Deep copy to avoid modifying original
    import copy

    filtered_data = copy.deepcopy(bpod_data)

    # Convert MATLAB struct to dict if needed
    session_data = convert_matlab_struct(filtered_data["SessionData"])
    filtered_data["SessionData"] = session_data

    n_trials = int(session_data["nTrials"])

    # Validate indices
    if not trial_indices:
        raise ValueError("trial_indices cannot be empty")

    for idx in trial_indices:
        if idx < 0 or idx >= n_trials:
            raise IndexError(f"Trial index {idx} out of bounds (0-{n_trials-1})")

    # Filter trial-related arrays
    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]

    # Convert RawEvents to dict if needed
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    session_data["RawEvents"] = raw_events

    # Handle both numpy arrays and lists
    def _index_array(arr: Any, indices: List[int]) -> Any:
        """Helper to index arrays or lists."""
        if isinstance(arr, np.ndarray):
            return arr[indices]
        elif isinstance(arr, (list, tuple)):
            return [arr[i] for i in indices]
        else:
            # Scalar - shouldn't happen for these fields
            return arr

    # Filter timestamps
    session_data["TrialStartTimestamp"] = _index_array(start_timestamps, trial_indices)
    session_data["TrialEndTimestamp"] = _index_array(end_timestamps, trial_indices)

    # Filter RawEvents.Trial (now always a dict)
    trial_list = raw_events["Trial"]
    filtered_trials = _index_array(trial_list, trial_indices)
    raw_events["Trial"] = filtered_trials

    # Filter optional fields if present
    if "TrialSettings" in session_data:
        trial_settings = session_data["TrialSettings"]
        session_data["TrialSettings"] = _index_array(trial_settings, trial_indices)

    if "TrialTypes" in session_data:
        trial_types = session_data["TrialTypes"]
        session_data["TrialTypes"] = _index_array(trial_types, trial_indices)

    # Update nTrials count
    session_data["nTrials"] = len(trial_indices)

    logger.info(f"Indexed Bpod data: kept {len(trial_indices)} trials out of {n_trials}")
    return filtered_data


def write_bpod_mat(bpod_data: Dict[str, Any], output_path: Path) -> None:
    """Write Bpod data dictionary back to MATLAB .mat file.

    Saves Bpod data structure to a .mat file compatible with Bpod software.
    Can be used after filtering with index_bpod_data() or manual modifications.

    Args:
        bpod_data: Bpod data dictionary (from parse_bpod_mat or index_bpod_data)
        output_path: Path where to save the .mat file

    Raises:
        BpodParseError: If scipy is not available or write fails
        BpodValidationError: If data structure is invalid

    Examples:
        >>> from pathlib import Path
        >>> from w2t_bkin.events import parse_bpod_mat, index_bpod_data, write_bpod_mat
        >>>
        >>> # Load, filter, and save
        >>> bpod_data = parse_bpod_mat(Path("data/Bpod/session.mat"))
        >>> filtered_data = index_bpod_data(bpod_data, [0, 1, 2])
        >>> write_bpod_mat(filtered_data, Path("data/Bpod/session_filtered.mat"))
        >>>
        >>> # Verify filtered data
        >>> reloaded = parse_bpod_mat(Path("data/Bpod/session_filtered.mat"))
        >>> print(f"Filtered session has {reloaded['SessionData']['nTrials']} trials")
    """
    # Validate structure before writing
    if not validate_bpod_structure(bpod_data):
        raise BpodValidationError("Invalid Bpod structure - cannot write to file")

    if savemat is None:
        raise BpodParseError("scipy is required for .mat file writing. Install with: pip install scipy")

    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to .mat file (MATLAB v5 format for compatibility)
        savemat(str(output_path), bpod_data, format="5", oned_as="column")

        logger.info(f"Successfully wrote Bpod data to: {output_path.name}")
    except Exception as e:
        raise BpodParseError(f"Failed to write Bpod file: {type(e).__name__}: {e}")


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
            start_time_rel = float(_to_scalar(start_timestamps, i))
            stop_time_rel = float(_to_scalar(end_timestamps, i))
            trial_type = int(_to_scalar(trial_types_array, i))

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


def _is_state_visited(state_times: Any) -> bool:
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
            safe_event_type = _sanitize_event_type(event_type)

            # Convert to list if numpy array or scalar
            if isinstance(timestamps, np.ndarray):
                timestamps = _to_list(timestamps)
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
        >>> from w2t_bkin.events import parse_bpod_session, extract_trials, extract_behavioral_events
        >>> session = load_session("data/Session-001/session.toml")
        >>> bpod_data = parse_bpod_session(session)
        >>> trials = extract_trials(bpod_data)
        >>> events = extract_behavioral_events(bpod_data)
        >>> summary = create_event_summary(session, trials, events)
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
        raise BpodValidationError(f"Invalid file extension: {path.suffix}", file_path=str(path))

    # Check file size (prevent memory exhaustion)
    try:
        file_size_mb = validate_file_size(path, max_size_mb=MAX_BPOD_FILE_SIZE_MB)
        logger.debug(f"Validated Bpod file: {path.name} ({file_size_mb:.2f}MB)")
    except ValueError as e:
        # Re-raise as BpodValidationError for consistent error handling
        raise BpodValidationError(str(e), file_path=str(path))


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
