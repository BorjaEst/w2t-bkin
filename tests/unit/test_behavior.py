"""Tests for behavior module (ndx-structured-behavior integration).

Tests the transformation from Bpod data to ndx-structured-behavior NWB classes.
"""

import pytest

from w2t_bkin.behavior import (
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
)


class TestStateExtraction:
    """Test state type and state data extraction."""

    def test_extract_state_types(self, parsed_bpod_data):
        """Test extracting unique state types from Bpod data."""
        state_types = extract_state_types(parsed_bpod_data)

        # Check that we got a StateTypesTable
        assert state_types is not None
        assert hasattr(state_types, "add_row")

        # Check state names are extracted
        state_names = list(state_types["state_name"].data)
        assert len(state_names) > 0
        assert "ITI" in state_names
        assert "Response_window" in state_names

    def test_extract_states(self, parsed_bpod_data):
        """Test extracting state occurrences from Bpod data."""
        state_types = extract_state_types(parsed_bpod_data)
        states, state_indices = extract_states(parsed_bpod_data, state_types, trial_offsets=None)

        # Check that we got a StatesTable
        assert states is not None
        assert hasattr(states, "add_state")

        # Check states were extracted
        assert len(states) > 0

        # Check indices dictionary is valid
        assert isinstance(state_indices, dict)
        assert all(isinstance(k, int) for k in state_indices.keys())
        assert all(isinstance(v, list) for v in state_indices.values())

    def test_extract_states_with_offsets(self, parsed_bpod_data):
        """Test state extraction with trial offsets for absolute time."""
        state_types = extract_state_types(parsed_bpod_data)
        trial_offsets = {1: 0.0, 2: 10.0, 3: 20.0}  # Offsets for 3 trials

        states, state_indices = extract_states(parsed_bpod_data, state_types, trial_offsets=trial_offsets)

        assert len(states) > 0
        assert isinstance(state_indices, dict)
        # Verify timestamps are adjusted by offsets
        # (implementation detail - would need to check specific state times)


class TestEventExtraction:
    """Test event type and event data extraction."""

    def test_extract_event_types(self, parsed_bpod_data):
        """Test extracting unique event types from Bpod data."""
        event_types = extract_event_types(parsed_bpod_data)

        # Check that we got an EventTypesTable
        assert event_types is not None
        assert hasattr(event_types, "add_row")

        # Check event names are extracted
        event_names = list(event_types["event_name"].data)
        assert len(event_names) > 0

    def test_extract_events(self, parsed_bpod_data):
        """Test extracting event occurrences from Bpod data."""
        event_types = extract_event_types(parsed_bpod_data)
        events, event_indices = extract_events(parsed_bpod_data, event_types, trial_offsets=None)

        # Check that we got an EventsTable
        assert events is not None
        assert hasattr(events, "add_event")

        # Check events were extracted
        assert len(events) > 0


class TestActionExtraction:
    """Test action type and action data extraction."""

    def test_extract_action_types(self, parsed_bpod_data):
        """Test extracting action types from Bpod state names."""
        action_types = extract_action_types(parsed_bpod_data)

        # Check that we got an ActionTypesTable
        assert action_types is not None
        assert hasattr(action_types, "add_row")

        # Check action names (may be empty if no action states in fixture)
        action_names = list(action_types["action_name"].data)
        assert isinstance(action_names, list)

    def test_extract_actions(self, parsed_bpod_data):
        """Test extracting action occurrences from Bpod data."""
        action_types = extract_action_types(parsed_bpod_data)
        actions, action_indices = extract_actions(parsed_bpod_data, action_types, trial_offsets=None)

        # Check that we got an ActionsTable
        assert actions is not None
        assert hasattr(actions, "add_action")

        # Actions may be empty if no action states in fixture
        assert isinstance(len(actions), int)


class TestTrialsAndRecording:
    """Test trials table and task recording construction."""

    def test_build_trials_table(self, parsed_bpod_data):
        """Test building TrialsTable with references to states/events/actions."""
        # Extract all components
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        states, state_indices = extract_states(parsed_bpod_data, state_types)
        events, event_indices = extract_events(parsed_bpod_data, event_types)
        actions, action_indices = extract_actions(parsed_bpod_data, action_types)

        # Build trials table
        trials = build_trials_table(parsed_bpod_data, states, events, actions, state_indices, event_indices, action_indices)

        # Check that we got a TrialsTable
        assert trials is not None
        assert hasattr(trials, "add_trial")

        # Check trials were created
        n_trials = parsed_bpod_data["SessionData"]["nTrials"]
        assert len(trials) == n_trials

    def test_trials_contain_references(self, parsed_bpod_data):
        """Test that TrialsTable contains actual references to states/events/actions (not empty)."""
        # Extract all components
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        states, state_indices = extract_states(parsed_bpod_data, state_types)
        events, event_indices = extract_events(parsed_bpod_data, event_types)
        actions, action_indices = extract_actions(parsed_bpod_data, action_types)

        # Build trials table
        trials = build_trials_table(parsed_bpod_data, states, events, actions, state_indices, event_indices, action_indices)

        # Verify that at least one trial has non-empty references
        # (depends on test data having states/events/actions)
        has_state_refs = False
        has_event_refs = False
        has_action_refs = False

        for trial_idx in range(len(trials)):
            trial_states = trials["states"][trial_idx]
            trial_events = trials["events"][trial_idx]
            trial_actions = trials["actions"][trial_idx]

            if len(trial_states) > 0:
                has_state_refs = True
            if len(trial_events) > 0:
                has_event_refs = True
            if len(trial_actions) > 0:
                has_action_refs = True

        # At minimum, states should be present in trials
        assert has_state_refs, "Trials should contain references to states"
        # Events and actions may or may not be present depending on test data

    def test_build_task_recording(self, parsed_bpod_data):
        """Test building TaskRecording container."""
        # Extract all components
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        states, state_indices = extract_states(parsed_bpod_data, state_types)
        events, event_indices = extract_events(parsed_bpod_data, event_types)
        actions, action_indices = extract_actions(parsed_bpod_data, action_types)

        # Build task recording
        task_recording = build_task_recording(states, events, actions)

        # Check that we got a TaskRecording
        assert task_recording is not None
        assert hasattr(task_recording, "states")
        assert hasattr(task_recording, "events")
        assert hasattr(task_recording, "actions")

        # Verify tables are linked
        assert task_recording.states is states
        assert task_recording.events is events
        assert task_recording.actions is actions


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline(self, parsed_bpod_data):
        """Test complete workflow: Bpod data → ndx-structured-behavior."""
        # Extract type tables
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        # Extract data tables
        states, state_indices = extract_states(parsed_bpod_data, state_types)
        events, event_indices = extract_events(parsed_bpod_data, event_types)
        actions, action_indices = extract_actions(parsed_bpod_data, action_types)

        # Build trials and recording
        trials = build_trials_table(parsed_bpod_data, states, events, actions, state_indices, event_indices, action_indices)
        task_recording = build_task_recording(states, events, actions)

        # Verify complete structure
        assert state_types is not None
        assert event_types is not None
        assert action_types is not None
        assert states is not None
        assert events is not None
        assert actions is not None
        assert trials is not None
        assert task_recording is not None

        # Verify data consistency
        n_trials = parsed_bpod_data["SessionData"]["nTrials"]
        assert len(trials) == n_trials
        assert len(states) > 0  # At least some states
        assert len(events) >= 0  # May have no events
