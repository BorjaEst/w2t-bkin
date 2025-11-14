"""Bpod file I/O operations.

Handles parsing, discovery, merging, validation, and manipulation of Bpod .mat files.
This module provides all low-level Bpod data operations.
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

from ..domain.session import BpodSession, Session
from ..utils import convert_matlab_struct, discover_files, sort_files
from .exceptions import BpodParseError, BpodValidationError
from .helpers import validate_bpod_path

logger = logging.getLogger(__name__)


# =============================================================================
# Bpod .mat File Parsing
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
# Bpod Session Merging
# =============================================================================


def merge_bpod_sessions(file_paths: List[Path], continuous_time: bool = True) -> Dict[str, Any]:
    """Merge multiple Bpod .mat files into unified session data.

    Combines trials from multiple Bpod files in order, updating trial numbers
    and optionally offsetting timestamps to create a continuous session timeline.

    Args:
        file_paths: Ordered list of Bpod .mat file paths
        continuous_time: If True (default), offset timestamps to create continuous timeline.
                        If False, preserve original per-file timestamps (concatenate mode).

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


def parse_bpod_session(session: Session) -> Dict[str, Any]:
    """Parse Bpod session from configuration with file discovery and merging.

    High-level function that:
    1. Discovers files from glob pattern
    2. Orders files according to strategy
    3. Merges multiple files if needed, respecting continuous_time setting

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
    """
    session_dir = Path(session.session_dir)

    # Discover files
    file_paths = discover_bpod_files(session.bpod, session_dir)

    # Merge if multiple files, using continuous_time setting from session config
    merged_data = merge_bpod_sessions(file_paths, continuous_time=session.bpod.continuous_time)

    return merged_data


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
    """Split Bpod data into multiple Bpod data dictionaries.

    This is the inverse of ``merge_bpod_sessions`` for the use case where a
    single Bpod session is exported into several .mat files that are later
    merged back into a continuous timeline.

    **Key properties**

    - Each returned chunk is a valid Bpod data dict (passes
      :func:`validate_bpod_structure`) and can be written using
      :func:`write_bpod_mat`.
    - Trial start/end timestamps and trial structure are preserved exactly as
      they appear in ``bpod_data`` for the selected indices (no additional
      offsets are introduced at split time).
    - When the resulting files are later merged with
      :func:`merge_bpod_sessions`, the timestamps are concatenated into a
      continuous timeline using the merge logic (second file offset by the
      last end time of the previous file, etc.).

    Args:
        bpod_data: Parsed Bpod data dictionary (from :func:`parse_bpod_mat` or
            :func:`parse_bpod_session`).
        splits: Sequence of trial index sequences, each containing **0-based**
            trial indices that should go into one output chunk, in the order
            they should appear in that chunk.

    Returns:
        List of Bpod data dictionaries, one per entry in ``splits``.

    Raises:
        BpodParseError: If the input structure is invalid.
        IndexError: If any index is out of bounds.
        ValueError: If a split is empty.
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
