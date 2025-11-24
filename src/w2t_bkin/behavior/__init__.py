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
    >>> from w2t_bkin.events.bpod import parse_bpod
    >>> from w2t_bkin.behavior import (
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

from .core import (
    build_task,
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
    extract_task,
    extract_task_arguments,
    extract_task_recording,
    extract_trials_table,
)
from .models import ActionsTable, ActionTypesTable, EventsTable, EventTypesTable, StatesTable, StateTypesTable, Task, TaskArgumentsTable, TaskRecording, TrialsTable

__all__ = [
    # Core transformation functions
    "extract_state_types",
    "extract_states",
    "extract_event_types",
    "extract_events",
    "extract_action_types",
    "extract_actions",
    "build_trials_table",
    "extract_trials_table",
    "build_task_recording",
    "extract_task_recording",
    "extract_task_arguments",
    "build_task",
    "extract_task",
    # Re-exported ndx-structured-behavior types
    "StateTypesTable",
    "StatesTable",
    "EventTypesTable",
    "EventsTable",
    "ActionTypesTable",
    "ActionsTable",
    "TrialsTable",
    "TaskRecording",
    "Task",
    "TaskArgumentsTable",
]
