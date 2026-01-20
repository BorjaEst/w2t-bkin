"""Behavior module for Bpod behavioral data with ndx-structured-behavior.

This module provides transformation functions to convert Bpod .mat files
into ndx-structured-behavior NWB classes (StatesTable, EventsTable, ActionsTable,
TrialsTable, TaskRecording).

Following the NWB-first architecture established in Phase 1 (pose module),
this module produces community-standard ndx-structured-behavior objects directly,
eliminating intermediate custom models and conversion layers.

Public API:
    Core transformation functions:
        - extract_state_types: Parse unique state names → StateTypesTable
        - extract_states: Convert trial states → StatesTable
        - extract_event_types: Parse unique event names → EventTypesTable
        - extract_events: Convert hardware events → EventsTable
        - extract_action_types: Identify action states → ActionTypesTable
        - extract_actions: Convert action states → ActionsTable
        - build_trials_table: Combine states/events/actions → TrialsTable
        - extract_trials_table: Complete extraction (convenience) → TrialsTable
        - build_task_recording: Package tables → TaskRecording
        - extract_task_recording: Complete extraction (convenience) → TaskRecording
        - extract_task_arguments: Extract task parameters → TaskArgumentsTable
        - build_task: Assemble Task container with type tables
        - extract_task: Complete extraction (convenience) → Task

    Re-exported ndx-structured-behavior types:
        - StateTypesTable, StatesTable
        - EventTypesTable, EventsTable
        - ActionTypesTable, ActionsTable
        - TrialsTable
        - TaskRecording
        - Task, TaskArgumentsTable

Example:
    >>> from pathlib import Path
    >>> from w2t_bkin.ingest.bpod import parse_bpod
    >>> from w2t_bkin.ingest.behavior import (
    ...     extract_state_types, extract_states,
    ...     extract_event_types, extract_events,
    ...     extract_action_types, extract_actions,
    ...     build_trials_table, build_task_recording
    ... )
    >>>
    >>> # Parse Bpod data
    >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
    >>>
    >>> # Build type tables
    >>> state_types = extract_state_types(bpod_data)
    >>> event_types = extract_event_types(bpod_data)
    >>> action_types = extract_action_types(bpod_data)
    >>>
    >>> # Build data tables (returns tuples with row indices)
    >>> states, state_indices = extract_states(bpod_data, state_types)
    >>> events, event_indices = extract_events(bpod_data, event_types)
    >>> actions, action_indices = extract_actions(bpod_data, action_types)
    >>>
    >>> # Build trials and recording (pass indices for trial references)
    >>> trials = build_trials_table(bpod_data, states, events, actions,
    ...                             state_indices, event_indices, action_indices)
    >>> task_recording = build_task_recording(states, events, actions)
    >>>
    >>> # Build Task container (optional but recommended)
    >>> task_arguments = extract_task_arguments(bpod_data)  # optional
    >>> task = build_task(state_types, event_types, action_types,
    ...                   task_arguments=task_arguments)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from ndx_structured_behavior import ActionsTable, ActionTypesTable, EventsTable, EventTypesTable, StatesTable, StateTypesTable, Task, TaskArgumentsTable, TaskRecording, TrialsTable
import numpy as np

from w2t_bkin.exceptions import BpodParseError
from w2t_bkin.utils import convert_matlab_struct, is_nan_or_none, to_scalar

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
) -> Tuple[StatesTable, Dict[int, List[int]]]:
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
    recording: TaskRecording,
    state_indices: Dict[int, List[int]],
    event_indices: Dict[int, List[int]],
    action_indices: Dict[int, List[int]],
    trial_offsets: Optional[Dict[int, float]] = None,
) -> TrialsTable:
    """Build TrialsTable with references to TaskRecording tables.

    Creates ndx-structured-behavior TrialsTable with start/stop times for
    each trial and index ranges referencing the states/events/actions tables
    from the TaskRecording.

    This simplified API ensures that the TrialsTable references the exact same
    table instances as the TaskRecording, preventing instance mismatch errors.

    Args:
        bpod_data: Parsed Bpod data dictionary
        recording: TaskRecording containing states/events/actions tables
        state_indices: Dict mapping trial_number → list of state row indices
        event_indices: Dict mapping trial_number → list of event row indices
        action_indices: Dict mapping trial_number → list of action row indices
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        TrialsTable with trial structure

    Example:
        >>> # Build TaskRecording first
        >>> recording = build_task_recording(states, events, actions)
        >>> # Build TrialsTable using the same instances
        >>> trials = build_trials_table(bpod_data, recording,
        ...                             state_indices, event_indices, action_indices,
        ...                             trial_offsets)
        >>> print(f"{len(trials)} trials")
    """
    # Extract tables from TaskRecording to ensure instance consistency
    states = recording.states
    events = recording.events
    actions = recording.actions

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


def extract_trials_table(
    bpod_data: Dict[str, Any],
    recording: TaskRecording,
    trial_offsets: Optional[Dict[int, float]] = None,
) -> TrialsTable:
    """Extract complete TrialsTable from Bpod data using TaskRecording.

    High-level function that builds a TrialsTable using the data tables from
    an existing TaskRecording. This ensures instance consistency between the
    TaskRecording and TrialsTable.

    This is the recommended approach for creating TrialsTable:
    1. Build TaskRecording with extract_task_recording() or build_task_recording()
    2. Pass TaskRecording to this function to build TrialsTable

    Args:
        bpod_data: Parsed Bpod data dictionary
        recording: TaskRecording with states/events/actions tables
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        TrialsTable with complete trial structure

    Example:
        >>> from w2t_bkin.bpod.code import parse_bpod
        >>> from w2t_bkin.behavior import extract_task_recording, extract_trials_table
        >>>
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> recording = extract_task_recording(bpod_data, trial_offsets)
        >>> trials = extract_trials_table(bpod_data, recording, trial_offsets)
        >>> print(f"{len(trials)} trials extracted")

    Note:
        The recording parameter ensures that TrialsTable references the exact
        same table instances as the TaskRecording, preventing NWB serialization
        errors due to instance mismatches.
    """
    # Extract type tables from recording to build indices
    states = recording.states
    events = recording.events
    actions = recording.actions

    state_types = states.state_type.table
    event_types = events.event_type.table
    action_types = actions.action_type.table

    # Re-extract indices (they're not stored in TaskRecording)
    # This is necessary to map trial_number → row indices
    _, state_indices = extract_states(bpod_data, state_types, trial_offsets)
    _, event_indices = extract_events(bpod_data, event_types, trial_offsets)
    _, action_indices = extract_actions(bpod_data, action_types, trial_offsets)

    # Build TrialsTable using TaskRecording
    trials = build_trials_table(
        bpod_data=bpod_data,
        recording=recording,
        state_indices=state_indices,
        event_indices=event_indices,
        action_indices=action_indices,
        trial_offsets=trial_offsets,
    )

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


def extract_task_recording(
    bpod_data: Dict[str, Any],
    trial_offsets: Optional[Dict[int, float]] = None,
) -> TaskRecording:
    """Extract complete TaskRecording from Bpod data (convenience function).

    High-level function that performs all extraction steps:
    1. Extract type tables (states, events, actions)
    2. Extract data tables (states, events, actions) with row indices
    3. Build TaskRecording container

    This is a convenience wrapper for simpler API usage when you need the
    complete TaskRecording for NWB acquisition.

    Args:
        bpod_data: Parsed Bpod data dictionary
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        TaskRecording with complete state/event/action tables

    Example:
        >>> from w2t_bkin.bpod.code import parse_bpod
        >>> from w2t_bkin.behavior import extract_task_recording
        >>>
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> task_recording = extract_task_recording(bpod_data)
        >>> nwbfile.add_acquisition(task_recording)

    Note:
        If you need access to the intermediate type tables or data tables,
        use the individual extract_* functions instead.
    """
    # Step 1: Extract type tables
    state_types = extract_state_types(bpod_data)
    event_types = extract_event_types(bpod_data)
    action_types = extract_action_types(bpod_data)

    # Step 2: Extract data tables with indices
    states, _ = extract_states(bpod_data, state_types, trial_offsets)
    events, _ = extract_events(bpod_data, event_types, trial_offsets)
    actions, _ = extract_actions(bpod_data, action_types, trial_offsets)

    # Step 3: Build TaskRecording
    task_recording = build_task_recording(states, events, actions)

    return task_recording


# =============================================================================
# Task Metadata (Top-level Container)
# =============================================================================


def _flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> List[tuple]:
    """Recursively flatten nested dictionary into list of (key, value) tuples.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix for nested keys
        sep: Separator between parent and child keys

    Returns:
        List of (flattened_key, value) tuples

    Example:
        >>> _flatten_dict({'a': 1, 'b': {'c': 2, 'd': 3}})
        [('a', 1), ('b.c', 2), ('b.d', 3)]
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep))
        else:
            items.append((new_key, v))
    return items


def extract_task_arguments(bpod_data: Dict[str, Any]) -> Optional[TaskArgumentsTable]:
    """Extract task arguments/parameters from Bpod data.

    Attempts to extract task configuration parameters from:
    1. SessionData.Settings (protocol parameters) - most common
    2. SessionData.TrialSettings (per-trial parameters) - if uniform across trials
    3. Top-level SessionData fields (metadata)

    Args:
        bpod_data: Parsed Bpod data dictionary from parse_bpod()

    Returns:
        TaskArgumentsTable if arguments found, None otherwise

    Example:
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> task_args = extract_task_arguments(bpod_data)
        >>> if task_args:
        ...     print(f"{len(task_args)} parameters")
    """
    session_data = convert_matlab_struct(bpod_data.get("SessionData", {}))

    # Try Settings first (most common location)
    params = {}
    if "Settings" in session_data:
        settings = convert_matlab_struct(session_data["Settings"])
        if isinstance(settings, dict) and len(settings) > 0:
            params.update(dict(_flatten_dict(settings)))
            logger.info(f"Found {len(params)} parameters in Settings")

    # Try TrialSettings (check if uniform across trials)
    if "TrialSettings" in session_data and len(params) == 0:
        trial_settings = session_data["TrialSettings"]
        if hasattr(trial_settings, "__len__") and len(trial_settings) > 0:
            first_trial = convert_matlab_struct(trial_settings[0])
            if isinstance(first_trial, dict):
                # Check if all trials have same settings
                uniform = True
                for trial in trial_settings[1:]:
                    trial_dict = convert_matlab_struct(trial)
                    if trial_dict != first_trial:
                        uniform = False
                        break

                if uniform:
                    params.update(dict(_flatten_dict(first_trial)))
                    logger.info(f"Found {len(params)} uniform parameters in TrialSettings")
                else:
                    logger.debug("TrialSettings vary across trials, not extracting as task arguments")

    # Add useful metadata fields
    metadata_fields = ["nTrials", "TrialTypes"]
    for field in metadata_fields:
        if field in session_data and field not in params:
            value = session_data[field]
            # Convert arrays to scalar if single value
            if hasattr(value, "__len__") and not isinstance(value, str):
                if len(set(value)) == 1:  # All same value
                    value = value[0]
                else:
                    continue  # Skip non-uniform arrays
            params[field] = value

    if len(params) == 0:
        logger.info("No task arguments found in Bpod data")
        return None

    # Create TaskArgumentsTable
    task_args = TaskArgumentsTable(description="Task parameters from Bpod")

    # Add each parameter as a row
    for arg_name, arg_value in sorted(params.items()):
        # Convert value to string for storage
        if isinstance(arg_value, (np.ndarray, list)):
            value_str = str(list(arg_value))
            value_type = "array"
        elif isinstance(arg_value, (int, np.integer)):
            value_str = str(arg_value)
            value_type = "integer"
        elif isinstance(arg_value, (float, np.floating)):
            value_str = str(arg_value)
            value_type = "float"
        elif isinstance(arg_value, bool):
            value_str = str(arg_value)
            value_type = "boolean"
        else:
            value_str = str(arg_value)
            value_type = "string"

        task_args.add_row(
            argument_name=arg_name,
            argument_description=f"Parameter from Bpod data",
            expression=value_str,
            expression_type=value_type,
            output_type=value_type,
        )

    logger.info(f"Extracted {len(task_args)} task arguments")
    return task_args


def build_task(
    state_types: StateTypesTable,
    event_types: EventTypesTable,
    action_types: ActionTypesTable,
    task_arguments: Optional[TaskArgumentsTable] = None,
) -> Task:
    """Build Task container with type tables and metadata.

    Assembles the top-level Task container that holds all behavioral
    type tables (states, events, actions) and optional task metadata
    (arguments). This Task object is added to /general/task in the NWBFile.

    Args:
        state_types: StateTypesTable with state definitions
        event_types: EventTypesTable with event definitions
        action_types: ActionTypesTable with action definitions
        task_arguments: Optional task parameters/arguments

    Returns:
        Task container for /general/task in NWBFile

    Example:
        >>> task_args = extract_task_arguments(bpod_data)
        >>> task = build_task(state_types, event_types, action_types,
        ...                   task_arguments=task_args)
        >>> nwbfile.add_lab_meta_data(task)
    """
    # Create Task container with required type tables
    task = Task(
        event_types=event_types,
        state_types=state_types,
        action_types=action_types,
    )

    # Add optional task arguments
    if task_arguments is not None:
        task.task_arguments = task_arguments
        logger.info(f"Built Task with {len(task_arguments)} arguments")
    else:
        logger.info("Built Task without arguments")

    return task


def extract_task(bpod_data: Dict[str, Any]) -> Task:
    """Extract complete Task container from Bpod data (convenience function).

    High-level function that performs all extraction steps:
    1. Extract type tables (states, events, actions)
    2. Extract task arguments (optional)
    3. Build Task container

    This is a convenience wrapper for simpler API usage when you need the
    complete Task container for /general/task in NWBFile.

    Args:
        bpod_data: Parsed Bpod data dictionary

    Returns:
        Task container with type tables and optional arguments

    Example:
        >>> from w2t_bkin.bpod.code import parse_bpod
        >>> from w2t_bkin.behavior import extract_task
        >>>
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> task = extract_task(bpod_data)
        >>> nwbfile.add_lab_meta_data(task)

    Note:
        If you need access to the intermediate type tables or task arguments,
        use the individual extract_* functions instead.
    """
    # Step 1: Extract type tables
    state_types = extract_state_types(bpod_data)
    event_types = extract_event_types(bpod_data)
    action_types = extract_action_types(bpod_data)

    # Step 2: Extract task arguments (optional)
    task_arguments = extract_task_arguments(bpod_data)

    # Step 3: Build Task
    task = build_task(state_types, event_types, action_types, task_arguments)

    return task


def extract_behavioral_data(
    bpod_data: Dict[str, Any],
    trial_offsets: Optional[Dict[int, float]] = None,
) -> Tuple[Task, TaskRecording, TrialsTable]:
    """Extract all behavioral data structures in one call (highest-level convenience).

    This is the simplest API for extracting complete behavioral data from Bpod.
    It extracts Task, TaskRecording, and TrialsTable with guaranteed instance
    consistency between all components.

    Recommended for most use cases where you need all three components.

    Args:
        bpod_data: Parsed Bpod data dictionary
        trial_offsets: Optional dict mapping trial_number → absolute time offset

    Returns:
        Tuple of (Task, TaskRecording, TrialsTable)

    Example:
        >>> from w2t_bkin.bpod.code import parse_bpod
        >>> from w2t_bkin.behavior import extract_behavioral_data
        >>>
        >>> bpod_data = parse_bpod(Path("data"), "Bpod/*.mat", "name_asc")
        >>> task, recording, trials = extract_behavioral_data(bpod_data, trial_offsets)
        >>>
        >>> # Add to NWB file
        >>> nwbfile.add_lab_meta_data(task)
        >>> nwbfile.add_acquisition(recording)
        >>> nwbfile.trials = trials

    Note:
        This function ensures that:
        - Task contains the type tables
        - TaskRecording references those type tables
        - TrialsTable references the data tables from TaskRecording
    """
    # Step 1: Extract type tables once (shared between Task and TaskRecording)
    state_types = extract_state_types(bpod_data)
    event_types = extract_event_types(bpod_data)
    action_types = extract_action_types(bpod_data)

    # Step 2: Build Task with type tables
    task_arguments = extract_task_arguments(bpod_data)
    task = build_task(state_types, event_types, action_types, task_arguments)

    # Step 3: Extract data tables using the same type tables
    states, state_indices = extract_states(bpod_data, state_types, trial_offsets)
    events, event_indices = extract_events(bpod_data, event_types, trial_offsets)
    actions, action_indices = extract_actions(bpod_data, action_types, trial_offsets)

    # Step 4: Build TaskRecording with data tables
    recording = build_task_recording(states, events, actions)

    # Step 5: Build TrialsTable using TaskRecording (ensures instance consistency)
    trials = build_trials_table(
        bpod_data=bpod_data,
        recording=recording,
        state_indices=state_indices,
        event_indices=event_indices,
        action_indices=action_indices,
        trial_offsets=trial_offsets,
    )

    logger.info("Extracted complete behavioral data: Task, TaskRecording, and TrialsTable")
    return task, recording, trials
