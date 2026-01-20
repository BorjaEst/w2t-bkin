"""Behavioral data parsing from Bpod .mat files.

Provides low-level Bpod file operations:
- Parsing and merging Bpod .mat files
- Validating Bpod data structure
- File indexing and manipulation

For behavioral data extraction, use the behavior module with ndx-structured-behavior.

Example:
    >>> from pathlib import Path
    >>> from w2t_bkin.bpod import parse_bpod
    >>> from w2t_bkin.behavior import extract_trials_table
    >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
    >>> trials = extract_trials_table(bpod_data)
"""

"""Low-level Bpod .mat file I/O operations.

Provides functions to parse, merge, validate, index, and write Bpod data files.
"""

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np

try:
    from scipy.io import loadmat, savemat
except ImportError:
    loadmat = None
    savemat = None

from w2t_bkin.exceptions import BpodParseError, BpodValidationError
from w2t_bkin.utils import convert_matlab_struct, discover_files, sanitize_string, sort_files, validate_against_whitelist, validate_file_exists, validate_file_size

logger = logging.getLogger(__name__)

# Constants
MAX_BPOD_FILE_SIZE_MB = 100


def validate_bpod_path(path: Path) -> None:
    """Validate Bpod file path and size.

    Args:
        path: Path to .mat file

    Raises:
        BpodValidationError: Invalid path or file too large
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


def parse_bpod(session_dir: Path, pattern: str, order: str, continuous_time: bool = True) -> Dict[str, Any]:
    """Parse Bpod files matching a glob pattern.

    Discovers files using glob pattern, sorts them, then parses and merges.

    Args:
        session_dir: Base directory for resolving glob pattern
        pattern: Glob pattern for Bpod files (e.g. "Bpod/*.mat")
        order: Sort order (e.g. "name_asc", "modified_desc")
        continuous_time: Offset timestamps for continuous timeline

    Returns:
        Merged Bpod data dictionary

    Raises:
        BpodValidationError: No files found
        BpodParseError: Parse/merge failed

    Example:
        >>> from pathlib import Path
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
    """
    file_paths = discover_bpod_files_from_pattern(session_dir=session_dir, pattern=pattern, order=order)
    return parse_bpod_from_files(file_paths=file_paths, continuous_time=continuous_time)


def discover_bpod_files_from_pattern(session_dir: Path, pattern: str, order: str) -> List[Path]:
    """Discover and sort Bpod .mat files using a glob pattern.

    Args:
        session_dir: Base directory for glob pattern
        pattern: Glob pattern (e.g. "Bpod/*.mat")
        order: Sort order (e.g. "name_asc")

    Returns:
        Sorted list of file paths

    Raises:
        BpodValidationError: No files found
    """
    file_paths = discover_files(session_dir, pattern, sort=False)

    if not file_paths:
        raise BpodValidationError(f"No Bpod files found matching pattern: {pattern}")

    file_paths = sort_files(file_paths, order)

    logger.info("Discovered %d Bpod files with order '%s'", len(file_paths), order)
    return file_paths


def parse_bpod_from_files(file_paths: Sequence[Path], continuous_time: bool = True) -> Dict[str, Any]:
    """Parse and merge Bpod files from explicit paths.

    Args:
        file_paths: Ordered paths to .mat files
        continuous_time: Offset timestamps for continuous timeline

    Returns:
        Merged Bpod data dictionary

    Raises:
        BpodParseError: Parse/merge failed
    """
    return merge_bpod_sessions(list(file_paths), continuous_time=continuous_time)


def parse_bpod_mat(path: Path) -> Dict[str, Any]:
    """Parse a single Bpod .mat file.

    Args:
        path: Path to .mat file

    Returns:
        Bpod data dictionary

    Raises:
        BpodValidationError: File validation failed
        BpodParseError: Parse failed

    Example:
        >>> from pathlib import Path
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
    """
    # Validate path and file size
    validate_bpod_path(path)

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
    """Validate Bpod data has required fields.

    Args:
        data: Bpod data dictionary

    Returns:
        True if valid
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


def merge_bpod_sessions(file_paths: List[Path], continuous_time: bool = True) -> Dict[str, Any]:
    """Merge multiple Bpod .mat files into one.

    Combines trials from files in order. With continuous_time=True, offsets
    timestamps so each file continues from the previous file's end time.

    Args:
        file_paths: Ordered list of .mat file paths
        continuous_time: Offset timestamps for continuous timeline

    Returns:
        Merged Bpod data dictionary

    Raises:
        BpodParseError: Parse/merge failed
    """
    if not file_paths:
        raise BpodParseError("No Bpod files to merge")

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

        # Get trial offset (time of last trial end) - only if continuous_time is True
        time_offset = all_end_times[-1] if all_end_times and continuous_time else 0.0

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


def index_bpod_data(bpod_data: Dict[str, Any], trial_indices: List[int]) -> Dict[str, Any]:
    """Filter Bpod data to keep only specified trials.

    Args:
        bpod_data: Bpod data dictionary
        trial_indices: 0-based indices of trials to keep

    Returns:
        New Bpod data with filtered trials

    Raises:
        BpodParseError: Invalid structure
        IndexError: Indices out of bounds

    Example:
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
        >>> filtered = index_bpod_data(bpod_data, [0, 1, 2])  # First 3 trials
    """
    # Validate structure
    if not validate_bpod_structure(bpod_data):
        raise BpodParseError("Invalid Bpod structure")

    # Deep copy to avoid modifying original
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


def split_bpod_data(bpod_data: Dict[str, Any], splits: Sequence[Sequence[int]]) -> List[Dict[str, Any]]:
    """Split Bpod data into multiple chunks by trial indices.

    Each output chunk is a valid Bpod data dictionary that can be written
    with write_bpod_mat and later re-merged with merge_bpod_sessions.

    Args:
        bpod_data: Bpod data dictionary
        splits: Sequences of 0-based trial indices for each chunk

    Returns:
        List of Bpod data dictionaries

    Raises:
        BpodParseError: Invalid structure
        IndexError: Indices out of bounds
        ValueError: Empty split

    Example:
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
        >>> chunks = split_bpod_data(bpod_data, [[0, 1], [2, 3], [4, 5]])
    """

    # Validate structure first
    if not validate_bpod_structure(bpod_data):
        raise BpodParseError("Invalid Bpod structure")

    # Convert and inspect the source to validate indices against nTrials
    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data["nTrials"])

    # Helper for a single split; reuses index_bpod_data to ensure deep copy
    # and consistent filtering of all fields.
    def _make_chunk(indices: Sequence[int]) -> Dict[str, Any]:
        if not indices:
            raise ValueError("split indices cannot be empty")

        for idx in indices:
            if idx < 0 or idx >= n_trials:
                raise IndexError(f"Trial index {idx} out of bounds (0-{n_trials-1})")

        # Delegate the heavy lifting to index_bpod_data, which:
        # - deep copies the original structure
        # - converts MATLAB structs to dicts
        # - consistently filters timestamps, RawEvents.Trial, TrialSettings,
        #   TrialTypes, and updates nTrials.
        return index_bpod_data(bpod_data, list(indices))

    return [_make_chunk(indices) for indices in splits]


def write_bpod_mat(bpod_data: Dict[str, Any], output_path: Path) -> None:
    """Write Bpod data to a .mat file.

    Args:
        bpod_data: Bpod data dictionary
        output_path: Output .mat file path

    Raises:
        BpodParseError: Write failed or scipy not available
        BpodValidationError: Invalid structure

    Example:
        >>> bpod_data = parse_bpod_mat(Path("data/session.mat"))
        >>> filtered = index_bpod_data(bpod_data, [0, 1, 2])
        >>> write_bpod_mat(filtered, Path("data/filtered.mat"))
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
