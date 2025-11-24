"""Re-export ndx-structured-behavior classes.

This module provides a single import location for all ndx-structured-behavior
types used in the behavior module. Following the pattern from pose/models.py,
we re-export community-standard classes rather than defining custom models.

All behavioral data uses ndx-structured-behavior types directly:
    - StateTypesTable, StatesTable: Trial state sequences
    - EventTypesTable, EventsTable: Hardware events (port pokes, triggers)
    - ActionTypesTable, ActionsTable: Actions (rewards, stimuli)
    - TrialsTable: Trial structure with references to states/events/actions
    - TaskRecording: Container for states/events/actions tables
"""

from ndx_structured_behavior import ActionsTable, ActionTypesTable, EventsTable, EventTypesTable, StatesTable, StateTypesTable, TaskRecording, TrialsTable

__all__ = [
    "StateTypesTable",
    "StatesTable",
    "EventTypesTable",
    "EventsTable",
    "ActionTypesTable",
    "ActionsTable",
    "TrialsTable",
    "TaskRecording",
]
