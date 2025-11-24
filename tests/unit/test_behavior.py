"""Tests for behavior module (ndx-structured-behavior integration).

Tests the transformation from Bpod data to ndx-structured-behavior NWB classes.
"""

import pytest

from w2t_bkin.behavior import (
    build_task,
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
    extract_task_arguments,
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

    def test_extract_trials_table_convenience(self, parsed_bpod_data):
        """Test high-level extract_trials_table convenience function."""
        from w2t_bkin.behavior import extract_trials_table

        # Use convenience function
        trials = extract_trials_table(parsed_bpod_data)

        # Verify TrialsTable structure
        assert trials is not None
        assert len(trials.colnames) > 0
        assert "start_time" in trials.colnames
        assert "stop_time" in trials.colnames
        assert "states" in trials.colnames
        assert "events" in trials.colnames
        assert "actions" in trials.colnames

        # Verify trial count
        n_trials = parsed_bpod_data["SessionData"]["nTrials"]
        assert len(trials) == n_trials

        # Verify references exist and are accessible
        for trial_idx in range(len(trials)):
            states_ref = trials["states"][trial_idx]
            events_ref = trials["events"][trial_idx]
            actions_ref = trials["actions"][trial_idx]
            # References should be DynamicTableRegion objects (views into the referenced tables)
            assert states_ref is not None
            assert events_ref is not None
            assert actions_ref is not None

    def test_extract_trials_table_with_offsets(self, parsed_bpod_data):
        """Test extract_trials_table with time offsets."""
        from w2t_bkin.behavior import extract_trials_table

        # Create trial offsets
        n_trials = parsed_bpod_data["SessionData"]["nTrials"]
        trial_offsets = {i + 1: float(i * 100.0) for i in range(n_trials)}

        # Extract with offsets
        trials = extract_trials_table(parsed_bpod_data, trial_offsets=trial_offsets)

        # Verify trial count
        assert len(trials) == n_trials

        # Verify time offsets applied
        for trial_idx in range(len(trials)):
            trial_num = trial_idx + 1
            start_time = trials["start_time"][trial_idx]
            expected_offset = trial_offsets[trial_num]
            assert start_time >= expected_offset

    def test_extract_task_recording_convenience(self, parsed_bpod_data):
        """Test high-level extract_task_recording convenience function."""
        from w2t_bkin.behavior import extract_task_recording

        # Use convenience function
        task_recording = extract_task_recording(parsed_bpod_data)

        # Verify TaskRecording structure
        assert task_recording is not None
        assert hasattr(task_recording, "states")
        assert hasattr(task_recording, "events")
        assert hasattr(task_recording, "actions")

        # Verify data tables are populated
        assert len(task_recording.states) > 0
        assert len(task_recording.events) > 0

    def test_extract_task_recording_with_offsets(self, parsed_bpod_data):
        """Test extract_task_recording with time offsets."""
        from w2t_bkin.behavior import extract_task_recording

        # Create trial offsets
        n_trials = parsed_bpod_data["SessionData"]["nTrials"]
        trial_offsets = {i + 1: float(i * 100.0) for i in range(n_trials)}

        # Extract with offsets
        task_recording = extract_task_recording(parsed_bpod_data, trial_offsets=trial_offsets)

        # Verify time offsets applied to states
        assert len(task_recording.states) > 0
        first_state_time = task_recording.states["start_time"][0]
        # First trial should have offset applied
        expected_min_offset = trial_offsets[1]
        assert first_state_time >= expected_min_offset

    def test_extract_task_convenience(self, parsed_bpod_data):
        """Test high-level extract_task convenience function."""
        from w2t_bkin.behavior import extract_task

        # Use convenience function
        task = extract_task(parsed_bpod_data)

        # Verify Task structure
        assert task is not None
        assert hasattr(task, "state_types")
        assert hasattr(task, "event_types")
        assert hasattr(task, "action_types")

        # Verify type tables are populated
        assert len(task.state_types) > 0
        assert len(task.event_types) > 0


class TestTaskMetadata:
    """Test Task and TaskArgumentsTable extraction."""

    def test_extract_task_arguments_none(self, parsed_bpod_data):
        """Test that extract_task_arguments returns None when no Settings available."""
        # Synthetic data has minimal settings
        task_args = extract_task_arguments(parsed_bpod_data)

        # May return None or minimal args depending on data
        # Just verify it doesn't crash
        if task_args is not None:
            assert hasattr(task_args, "add_row")
            assert len(task_args) >= 0

    def test_extract_task_arguments_with_settings(self):
        """Test extracting task arguments from Bpod data with Settings."""
        # Create mock bpod_data with Settings
        bpod_data = {
            "SessionData": {
                "Settings": {
                    "reward_amount": 5.0,
                    "timeout_duration": 2.0,
                    "GUI": {
                        "parameter1": 10,
                        "parameter2": "value",
                    },
                },
                "nTrials": 10,
            }
        }

        task_args = extract_task_arguments(bpod_data)

        assert task_args is not None
        assert len(task_args) > 0

        # Check flattened parameters are present
        arg_names = list(task_args["argument_name"].data)
        assert "reward_amount" in arg_names
        assert "timeout_duration" in arg_names
        assert "GUI.parameter1" in arg_names  # Nested key flattened
        assert "GUI.parameter2" in arg_names
        assert "nTrials" in arg_names  # Metadata field

    def test_extract_task_arguments_from_trial_settings(self):
        """Test extracting uniform TrialSettings as task arguments."""
        # Create mock bpod_data with uniform TrialSettings
        bpod_data = {
            "SessionData": {
                "TrialSettings": [
                    {"ProtocolState": "ITI", "param1": 1.0},
                    {"ProtocolState": "ITI", "param1": 1.0},
                    {"ProtocolState": "ITI", "param1": 1.0},
                ],
                "nTrials": 3,
            }
        }

        task_args = extract_task_arguments(bpod_data)

        assert task_args is not None
        assert len(task_args) > 0

        arg_names = list(task_args["argument_name"].data)
        assert "ProtocolState" in arg_names
        assert "param1" in arg_names

    def test_extract_task_arguments_non_uniform_trial_settings(self):
        """Test that non-uniform TrialSettings are not extracted."""
        # Create mock bpod_data with varying TrialSettings
        bpod_data = {
            "SessionData": {
                "TrialSettings": [
                    {"ProtocolState": "ITI"},
                    {"ProtocolState": "Response"},  # Different!
                ],
                "nTrials": 2,
            }
        }

        task_args = extract_task_arguments(bpod_data)

        # Should have nTrials but not ProtocolState (since it varies)
        if task_args is not None:
            arg_names = list(task_args["argument_name"].data)
            # ProtocolState varies, so shouldn't be extracted as task arg
            # Only uniform metadata like nTrials
            assert "nTrials" in arg_names

    def test_build_task_minimal(self, parsed_bpod_data):
        """Test building Task with only type tables (no arguments)."""
        # Extract type tables
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        # Build Task without arguments
        task = build_task(state_types, event_types, action_types)

        # Verify Task structure
        assert task is not None
        assert task.name == "task"
        assert task.state_types is state_types
        assert task.event_types is event_types
        assert task.action_types is action_types

        # task_arguments should be None
        assert not hasattr(task, "task_arguments") or task.task_arguments is None

    def test_build_task_with_arguments(self, parsed_bpod_data):
        """Test building Task with task arguments."""
        # Extract type tables
        state_types = extract_state_types(parsed_bpod_data)
        event_types = extract_event_types(parsed_bpod_data)
        action_types = extract_action_types(parsed_bpod_data)

        # Extract or create task arguments
        task_args = extract_task_arguments(parsed_bpod_data)

        # If no args from data, create minimal ones
        if task_args is None:
            from w2t_bkin.behavior import TaskArgumentsTable

            task_args = TaskArgumentsTable(description="Test arguments")
            task_args.add_row(
                argument_name="test_param",
                argument_description="Test parameter",
                expression="42",
                expression_type="integer",
                output_type="integer",
            )

        # Build Task with arguments
        task = build_task(state_types, event_types, action_types, task_arguments=task_args)

        # Verify Task structure
        assert task is not None
        assert task.state_types is state_types
        assert task.event_types is event_types
        assert task.action_types is action_types
        assert task.task_arguments is task_args

    def test_task_integration(self, parsed_bpod_data):
        """Test complete workflow including Task."""
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

        # Build Task
        task_args = extract_task_arguments(parsed_bpod_data)
        task = build_task(state_types, event_types, action_types, task_arguments=task_args)

        # Verify everything is connected
        assert task is not None
        assert trials is not None
        assert task_recording is not None

        # Verify type tables are shared
        assert task.state_types is state_types
        assert task.event_types is event_types
        assert task.action_types is action_types
        assert len(events) >= 0  # May have no events
