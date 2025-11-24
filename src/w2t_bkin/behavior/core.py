"""Core transformation functions: Bpod data → ndx-structured-behavior.

This module implements the transformation layer that converts parsed Bpod .mat
files into ndx-structured-behavior NWB classes. All functions produce NWB-native
objects directly, following the NWB-first architecture from Phase 1.

Architecture:
    - Low-level: Parse Bpod .mat files (events.bpod module)
    - Mid-level: Transform to ndx-structured-behavior (this module)
    - High-level: Integrate with pipeline and NWB assembly (pipeline.py, nwb.py)

Data Flow:
    Bpod .mat → parse_bpod() → extract_*_types() → extract_*() → build_trials_table() → TaskRecording → NWBFile
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from ..exceptions import BpodParseError
from ..utils import convert_matlab_struct, is_nan_or_none, to_scalar
from .models import ActionsTable, ActionTypesTable, EventsTable, EventTypesTable, StatesTable, StateTypesTable, TaskRecording, TrialsTable

logger = logging.getLogger(__name__)

# Mapping of Bpod state names to action names
# States that represent actions (rewards, stimuli, etc.)
ACTION_STATES = {
    "LeftReward": "left_valve_open",
    "RightReward": "right_valve_open",
    "W2T_Audio": "audio_stimulus",
    "A2L_Audio": "audio_stimulus",
    "Airpuff": "airpuff_stimulus",
    "Microstim": "microstimulation",
}


# =============================================================================
# Type Tables (Metadata)
# =============================================================================


def extract_state_types(bpod_data: Dict[str, Any]) -> StateTypesTable:
    """Extract unique state types from Bpod data.

    Discovers all state names present in RawEvents.Trial[].States and
    creates a StateTypesTable for ndx-structured-behavior.

    Args:
        bpod_data: Parsed Bpod data dictionary from parse_bpod()

    Returns:
        StateTypesTable with all unique state names

    Raises:
        BpodParseError: Invalid Bpod structure

    Example:
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> state_types = extract_state_types(bpod_data)
        >>> print(state_types["state_name"].data)
        ['ITI', 'Response_window', 'HIT', 'Miss', ...]
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))

    if "RawEvents" not in session_data:
        raise BpodParseError("Missing RawEvents in Bpod data")

    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])

    # Discover unique state names across all trials
    state_names: Set[str] = set()

    for trial_data in trial_data_list:
        # Handle both dict and MATLAB struct
        if hasattr(trial_data, "States"):
            states = trial_data.States
        elif isinstance(trial_data, dict):
            states = trial_data.get("States", {})
        else:
            continue

        states = convert_matlab_struct(states)
        state_names.update(states.keys())

    # Create StateTypesTable
    state_types = StateTypesTable(description="State types from Bpod protocol")

    # Add states in sorted order for consistency
    for state_name in sorted(state_names):
        state_types.add_row(state_name=state_name)

    logger.info(f"Extracted {len(state_names)} unique state types")
    return state_types


def extract_event_types(bpod_data: Dict[str, Any]) -> EventTypesTable:
    """Extract unique event types from Bpod data.

    Discovers all event names present in RawEvents.Trial[].Events and
    creates an EventTypesTable for ndx-structured-behavior.

    Args:
        bpod_data: Parsed Bpod data dictionary from parse_bpod()

    Returns:
        EventTypesTable with all unique event names

    Raises:
        BpodParseError: Invalid Bpod structure

    Example:
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> event_types = extract_event_types(bpod_data)
        >>> print(event_types["event_name"].data)
        ['Port1In', 'Port1Out', 'BNC1High', 'Flex1Trig1', ...]
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))

    if "RawEvents" not in session_data:
        raise BpodParseError("Missing RawEvents in Bpod data")

    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])

    # Discover unique event names across all trials
    event_names: Set[str] = set()

    for trial_data in trial_data_list:
        # Handle both dict and MATLAB struct
        if hasattr(trial_data, "Events"):
            events = trial_data.Events
        elif isinstance(trial_data, dict):
            events = trial_data.get("Events", {})
        else:
            continue

        events = convert_matlab_struct(events)
        event_names.update(events.keys())

    # Create EventTypesTable
    event_types = EventTypesTable(description="Event types from Bpod hardware")

    # Add events in sorted order for consistency
    for event_name in sorted(event_names):
        event_types.add_row(event_name=event_name)

    logger.info(f"Extracted {len(event_names)} unique event types")
    return event_types


def extract_action_types(bpod_data: Dict[str, Any]) -> ActionTypesTable:
    """Extract action types from Bpod state names.

    Identifies states that represent actions (rewards, stimuli) using
    the ACTION_STATES mapping and creates an ActionTypesTable.

    Args:
        bpod_data: Parsed Bpod data dictionary from parse_bpod()

    Returns:
        ActionTypesTable with action names

    Example:
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> action_types = extract_action_types(bpod_data)
        >>> print(action_types["action_name"].data)
        ['left_valve_open', 'right_valve_open', 'audio_stimulus', ...]
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))

    if "RawEvents" not in session_data:
        raise BpodParseError("Missing RawEvents in Bpod data")

    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])

    # Discover action states present in data
    observed_actions: Set[str] = set()

    for trial_data in trial_data_list:
        # Handle both dict and MATLAB struct
        if hasattr(trial_data, "States"):
            states = trial_data.States
        elif isinstance(trial_data, dict):
            states = trial_data.get("States", {})
        else:
            continue

        states = convert_matlab_struct(states)

        # Check which action states are present
        for state_name in states.keys():
            if state_name in ACTION_STATES:
                observed_actions.add(ACTION_STATES[state_name])

    # Create ActionTypesTable
    action_types = ActionTypesTable(description="Action types from Bpod protocol")

    # Add actions in sorted order for consistency
    for action_name in sorted(observed_actions):
        action_types.add_row(action_name=action_name)

    logger.info(f"Extracted {len(observed_actions)} unique action types")
    return action_types


# =============================================================================
# Data Tables (Temporal Events)
# =============================================================================


def extract_states(
    bpod_data: Dict[str, Any],
    state_types: StateTypesTable,
    trial_offsets: Optional[Dict[int, float]] = None,
) -> StatesTable:
    """Extract state sequences from Bpod data.

    Converts RawEvents.Trial[].States to ndx-structured-behavior StatesTable
    with start_time/stop_time for each state occurrence.

    Args:
        bpod_data: Parsed Bpod data dictionary
        state_types: StateTypesTable with state name → index mapping
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        Tuple of (StatesTable with state occurrences, Dict mapping trial_number → list of state row indices)

    Example:
        >>> states, state_indices = extract_states(bpod_data, state_types, trial_offsets)
        >>> print(f"{len(states)} state occurrences")
        >>> print(f"Trial 1 has {len(state_indices[1])} states")
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])
    start_timestamps = session_data["TrialStartTimestamp"]

    # Build state name → index mapping
    state_name_to_idx = {name: idx for idx, name in enumerate(state_types["state_name"].data)}

    # Create StatesTable
    states = StatesTable(description="State sequences from Bpod trials", state_types_table=state_types)

    n_states = 0
    # Track which states belong to which trial
    trial_state_indices: Dict[int, List[int]] = {}

    for trial_idx, trial_data in enumerate(trial_data_list):
        trial_num = trial_idx + 1
        trial_start_ts = float(to_scalar(start_timestamps, trial_idx))

        # Initialize list for this trial's state indices
        trial_state_indices[trial_num] = []

        # Get time offset for absolute time conversion
        offset = trial_offsets.get(trial_num) if trial_offsets else 0.0

        # Extract states
        if hasattr(trial_data, "States"):
            trial_states = trial_data.States
        elif isinstance(trial_data, dict):
            trial_states = trial_data.get("States", {})
        else:
            continue

        trial_states = convert_matlab_struct(trial_states)

        # Add each state occurrence
        for state_name, state_times in trial_states.items():
            if state_name not in state_name_to_idx:
                logger.warning(f"Unknown state '{state_name}' not in StateTypesTable")
                continue

            # Check if state was visited (non-NaN start time)
            if isinstance(state_times, np.ndarray) and state_times.size >= 2:
                start_rel = float(state_times.flat[0])
                stop_rel = float(state_times.flat[1])
            elif isinstance(state_times, (list, tuple)) and len(state_times) >= 2:
                start_rel = float(state_times[0])
                stop_rel = float(state_times[1])
            else:
                continue

            # Skip NaN states (not visited)
            if is_nan_or_none(start_rel) or is_nan_or_none(stop_rel):
                continue

            # Convert to absolute time
            start_abs = offset + trial_start_ts + start_rel
            stop_abs = offset + trial_start_ts + stop_rel

            # Add to StatesTable
            state_type_idx = state_name_to_idx[state_name]
            states.add_state(
                state_type=state_type_idx,
                start_time=start_abs,
                stop_time=stop_abs,
            )
            # Track this state index for the trial
            trial_state_indices[trial_num].append(n_states)
            n_states += 1

    logger.info(f"Extracted {n_states} state occurrences from {len(trial_data_list)} trials")
    return states, trial_state_indices


def extract_events(
    bpod_data: Dict[str, Any],
    event_types: EventTypesTable,
    trial_offsets: Optional[Dict[int, float]] = None,
) -> Tuple[EventsTable, Dict[int, List[int]]]:
    """Extract hardware events from Bpod data.

    Converts RawEvents.Trial[].Events to ndx-structured-behavior EventsTable
    with timestamps for each event occurrence.

    Args:
        bpod_data: Parsed Bpod data dictionary
        event_types: EventTypesTable with event name → index mapping
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        Tuple of (EventsTable with event occurrences, Dict mapping trial_number → list of event row indices)

    Example:
        >>> events, event_indices = extract_events(bpod_data, event_types, trial_offsets)
        >>> print(f"{len(events)} event occurrences")
        >>> print(f"Trial 1 has {len(event_indices[1])} events")
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])
    start_timestamps = session_data["TrialStartTimestamp"]

    # Build event name → index mapping
    event_name_to_idx = {name: idx for idx, name in enumerate(event_types["event_name"].data)}

    # Create EventsTable
    events = EventsTable(description="Hardware events from Bpod", event_types_table=event_types)

    n_events = 0
    # Track which events belong to which trial
    trial_event_indices: Dict[int, List[int]] = {}

    for trial_idx, trial_data in enumerate(trial_data_list):
        trial_num = trial_idx + 1
        trial_start_ts = float(to_scalar(start_timestamps, trial_idx))

        # Initialize list for this trial's event indices
        trial_event_indices[trial_num] = []

        # Get time offset for absolute time conversion
        offset = trial_offsets.get(trial_num) if trial_offsets else 0.0

        # Extract events
        if hasattr(trial_data, "Events"):
            trial_events = trial_data.Events
        elif isinstance(trial_data, dict):
            trial_events = trial_data.get("Events", {})
        else:
            continue

        trial_events = convert_matlab_struct(trial_events)

        # Add each event occurrence
        for event_name, timestamps in trial_events.items():
            if event_name not in event_name_to_idx:
                logger.warning(f"Unknown event '{event_name}' not in EventTypesTable")
                continue

            # Convert to list if numpy array or scalar
            if isinstance(timestamps, np.ndarray):
                timestamps = timestamps.flatten().tolist()
            elif not isinstance(timestamps, (list, tuple)):
                timestamps = [timestamps]

            event_type_idx = event_name_to_idx[event_name]

            # Add each timestamp
            for timestamp_rel in timestamps:
                if is_nan_or_none(timestamp_rel):
                    continue

                timestamp_rel = float(timestamp_rel)
                timestamp_abs = offset + trial_start_ts + timestamp_rel

                # Add to EventsTable
                events.add_event(
                    event_type=event_type_idx,
                    timestamp=timestamp_abs,
                    value=event_name,  # Store original event name
                )
                # Track this event index for the trial
                trial_event_indices[trial_num].append(n_events)
                n_events += 1

    logger.info(f"Extracted {n_events} event occurrences from {len(trial_data_list)} trials")
    return events, trial_event_indices


def extract_actions(
    bpod_data: Dict[str, Any],
    action_types: ActionTypesTable,
    trial_offsets: Optional[Dict[int, float]] = None,
) -> Tuple[ActionsTable, Dict[int, List[int]]]:
    """Extract actions from Bpod state transitions.

    Identifies action states (rewards, stimuli) and converts to
    ndx-structured-behavior ActionsTable with timestamps and durations.

    Args:
        bpod_data: Parsed Bpod data dictionary
        action_types: ActionTypesTable with action name → index mapping
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        Tuple of (ActionsTable with action occurrences, Dict mapping trial_number → list of action row indices)

    Example:
        >>> actions, action_indices = extract_actions(bpod_data, action_types, trial_offsets)
        >>> print(f"{len(actions)} action occurrences")
        >>> print(f"Trial 1 has {len(action_indices[1])} actions")
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))
    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events.get("Trial", [])
    start_timestamps = session_data["TrialStartTimestamp"]

    # Build action name → index mapping
    action_name_to_idx = {name: idx for idx, name in enumerate(action_types["action_name"].data)}

    # Reverse mapping: state_name → action_name
    state_to_action = {state: action for state, action in ACTION_STATES.items() if action in action_name_to_idx}

    # Create ActionsTable
    actions = ActionsTable(description="Actions from Bpod protocol", action_types_table=action_types)

    n_actions = 0
    # Track which actions belong to which trial
    trial_action_indices: Dict[int, List[int]] = {}

    for trial_idx, trial_data in enumerate(trial_data_list):
        trial_num = trial_idx + 1
        trial_start_ts = float(to_scalar(start_timestamps, trial_idx))

        # Initialize list for this trial's action indices
        trial_action_indices[trial_num] = []

        # Get time offset for absolute time conversion
        offset = trial_offsets.get(trial_num) if trial_offsets else 0.0

        # Extract states
        if hasattr(trial_data, "States"):
            trial_states = trial_data.States
        elif isinstance(trial_data, dict):
            trial_states = trial_data.get("States", {})
        else:
            continue

        trial_states = convert_matlab_struct(trial_states)

        # Check action states
        for state_name, state_times in trial_states.items():
            if state_name not in state_to_action:
                continue

            action_name = state_to_action[state_name]
            action_type_idx = action_name_to_idx[action_name]

            # Check if state was visited
            if isinstance(state_times, np.ndarray) and state_times.size >= 2:
                start_rel = float(state_times.flat[0])
                stop_rel = float(state_times.flat[1])
            elif isinstance(state_times, (list, tuple)) and len(state_times) >= 2:
                start_rel = float(state_times[0])
                stop_rel = float(state_times[1])
            else:
                continue

            # Skip NaN states (not visited)
            if is_nan_or_none(start_rel) or is_nan_or_none(stop_rel):
                continue

            # Convert to absolute time
            timestamp_abs = offset + trial_start_ts + start_rel
            duration = stop_rel - start_rel

            # Add to ActionsTable
            actions.add_action(
                action_type=action_type_idx,
                timestamp=timestamp_abs,
                duration=duration,
                value=state_name,  # Original state name for traceability
            )
            # Track this action index for the trial
            trial_action_indices[trial_num].append(n_actions)
            n_actions += 1

    logger.info(f"Extracted {n_actions} action occurrences from {len(trial_data_list)} trials")
    return actions, trial_action_indices


# =============================================================================
# Trials and Recording
# =============================================================================


def build_trials_table(
    bpod_data: Dict[str, Any],
    states: StatesTable,
    events: EventsTable,
    actions: ActionsTable,
    state_indices: Dict[int, List[int]],
    event_indices: Dict[int, List[int]],
    action_indices: Dict[int, List[int]],
    trial_offsets: Optional[Dict[int, float]] = None,
) -> TrialsTable:
    """Build TrialsTable with references to states/events/actions.

    Creates ndx-structured-behavior TrialsTable with start/stop times for
    each trial and index ranges referencing the states/events/actions tables.

    Args:
        bpod_data: Parsed Bpod data dictionary
        states: StatesTable with state occurrences
        events: EventsTable with event occurrences
        actions: ActionsTable with action occurrences
        state_indices: Dict mapping trial_number → list of state row indices
        event_indices: Dict mapping trial_number → list of event row indices
        action_indices: Dict mapping trial_number → list of action row indices
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        TrialsTable with trial structure

    Example:
        >>> trials = build_trials_table(bpod_data, states, events, actions,
        ...                             state_indices, event_indices, action_indices,
        ...                             trial_offsets)
        >>> print(f"{len(trials)} trials")
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))
    n_trials = int(session_data["nTrials"])
    start_timestamps = session_data["TrialStartTimestamp"]
    end_timestamps = session_data["TrialEndTimestamp"]

    # Create TrialsTable
    trials = TrialsTable(
        description="Trials from Bpod session",
        states_table=states,
        events_table=events,
        actions_table=actions,
    )

    # Build trials with references to states/events/actions
    for trial_idx in range(n_trials):
        trial_num = trial_idx + 1
        trial_start_rel = float(to_scalar(start_timestamps, trial_idx))
        trial_stop_rel = float(to_scalar(end_timestamps, trial_idx))

        # Get time offset
        offset = trial_offsets.get(trial_num) if trial_offsets else 0.0

        # Convert to absolute time
        start_time = offset + trial_start_rel
        stop_time = offset + trial_stop_rel

        # Get indices for this trial (use empty lists if trial not found)
        trial_states = state_indices.get(trial_num, [])
        trial_events = event_indices.get(trial_num, [])
        trial_actions = action_indices.get(trial_num, [])

        trials.add_trial(
            start_time=start_time,
            stop_time=stop_time,
            states=trial_states,
            events=trial_events,
            actions=trial_actions,
        )

    logger.info(f"Built TrialsTable with {n_trials} trials")
    return trials


def build_task_recording(
    states: StatesTable,
    events: EventsTable,
    actions: ActionsTable,
) -> TaskRecording:
    """Build TaskRecording container for states/events/actions.

    Creates ndx-structured-behavior TaskRecording object that packages
    the three data tables for NWB file integration.

    Args:
        states: StatesTable with state occurrences
        events: EventsTable with event occurrences
        actions: ActionsTable with action occurrences

    Returns:
        TaskRecording container

    Example:
        >>> task_recording = build_task_recording(states, events, actions)
        >>> nwbfile.add_acquisition(task_recording)
    """
    task_recording = TaskRecording(
        states=states,
        events=events,
        actions=actions,
    )

    logger.info("Built TaskRecording container")
    return task_recording
