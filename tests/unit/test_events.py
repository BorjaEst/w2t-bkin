"""Unit tests for events module (Phase 3 - Red Phase, Bpod parsing).

Requirements: FR-11, FR-14, NFR-7
Acceptance: A4 (trial counts and event categories in QC)
"""

from datetime import datetime
import json
from pathlib import Path

import pytest

from w2t_bkin.domain import BehavioralEvent, BpodSummary, TrialData
from w2t_bkin.events import (
    BpodParseError,
    EventsError,
    create_event_summary,
    extract_behavioral_events,
    extract_trials,
    parse_bpod_mat,
    validate_bpod_structure,
    write_event_summary,
)


class TestBpodMatParsing:
    """Test Bpod .mat file parsing - FR-11."""

    def test_Should_ParseBpodMat_When_ValidFileProvided(self, valid_bpod_file):
        result = parse_bpod_mat(valid_bpod_file)
        assert result is not None
        assert "SessionData" in result

    def test_Should_RaiseError_When_BpodFileMissing(self):
        with pytest.raises(EventsError, match="not found"):
            parse_bpod_mat(Path("/nonexistent/bpod.mat"))

    def test_Should_ValidateStructure_When_ParsingBpod(self, valid_bpod_file):
        result = parse_bpod_mat(valid_bpod_file)
        is_valid = validate_bpod_structure(result)
        assert is_valid is True

    def test_Should_ValidateRealBpodStructure_When_Checking(self, parsed_bpod_data):
        """Validate real Bpod structure: SessionData with nTrials, timestamps, RawEvents."""
        assert validate_bpod_structure(parsed_bpod_data) is True

        session_data = parsed_bpod_data["SessionData"]
        assert "nTrials" in session_data
        assert "TrialStartTimestamp" in session_data
        assert "TrialEndTimestamp" in session_data
        assert "RawEvents" in session_data
        assert "Trial" in session_data["RawEvents"]


class TestTrialExtraction:
    """Test trial data extraction - FR-11."""

    def test_Should_ExtractTrials_When_BpodParsed(self, parsed_bpod_data):
        trials = extract_trials(parsed_bpod_data)
        assert len(trials) == 3
        assert all(isinstance(t, TrialData) for t in trials)

    def test_Should_IncludeTrialTimestamps_When_Extracting(self, parsed_bpod_data):
        trials = extract_trials(parsed_bpod_data)
        first_trial = trials[0]
        assert hasattr(first_trial, "start_time")
        assert hasattr(first_trial, "stop_time")
        assert first_trial.start_time == 0.0
        assert first_trial.stop_time == 9.0

    def test_Should_InferOutcomeFromStates_When_Extracting(self, parsed_bpod_data):
        """Outcome must be inferred from States (HIT/Miss), not from TrialSettings."""
        trials = extract_trials(parsed_bpod_data)

        # Trial 0: HIT state is valid (not NaN) → hit
        assert trials[0].outcome == "hit"

        # Trial 1: Miss state is valid (not NaN) → miss
        assert trials[1].outcome == "miss"

        # Trial 2: HIT state is valid (not NaN) → hit
        assert trials[2].outcome == "hit"

    def test_Should_IncludeTrialNumber_When_Extracting(self, parsed_bpod_data):
        """Trials should include trial_number field (1-indexed)."""
        trials = extract_trials(parsed_bpod_data)
        assert trials[0].trial_number == 1
        assert trials[1].trial_number == 2
        assert trials[2].trial_number == 3


class TestBehavioralEventExtraction:
    """Test behavioral event extraction - FR-11."""

    def test_Should_ExtractEvents_When_BpodParsed(self, parsed_bpod_data):
        events = extract_behavioral_events(parsed_bpod_data)
        assert len(events) > 0
        assert all(isinstance(e, BehavioralEvent) for e in events)

    def test_Should_FlattenAllEventTypes_When_Extracting(self, parsed_bpod_data):
        """Events are keyed by name (Flex1Trig2, BNC1High, etc), must flatten all."""
        events = extract_behavioral_events(parsed_bpod_data)

        event_types = {e.event_type for e in events}
        # Should extract various event types from the real structure
        assert "Flex1Trig2" in event_types or "BNC1High" in event_types or "Tup" in event_types

    def test_Should_IncludeEventTimestamps_When_Extracting(self, parsed_bpod_data):
        """Each event timestamp should be extracted (events can have multiple timestamps)."""
        events = extract_behavioral_events(parsed_bpod_data)

        first_event = events[0]
        assert hasattr(first_event, "timestamp")
        assert isinstance(first_event.timestamp, float)

    def test_Should_LinkEventsToTrials_When_Extracting(self, parsed_bpod_data):
        """Events should know which trial they belong to."""
        events = extract_behavioral_events(parsed_bpod_data)

        # Check trial numbers are assigned
        trial_numbers = {e.trial_number for e in events}
        assert trial_numbers == {1, 2, 3}


class TestEventSummaryCreation:
    """Test event summary generation - FR-14, A4."""

    def test_Should_CreateSummary_When_TrialsExtracted(self, trial_list, event_list):
        summary = create_event_summary(session_id="test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert isinstance(summary, BpodSummary)
        assert summary.total_trials == len(trial_list)

    def test_Should_CountTrialOutcomes_When_CreatingSummary(self, trial_list, event_list):
        """A4: Include trial counts by outcome in QC report."""
        summary = create_event_summary(session_id="test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert hasattr(summary, "outcome_counts")
        assert isinstance(summary.outcome_counts, dict)
        # Should count hits and misses
        assert summary.outcome_counts.get("hit", 0) == 2
        assert summary.outcome_counts.get("miss", 0) == 1

    def test_Should_ListEventCategories_When_CreatingSummary(self, trial_list, event_list):
        """A4: List unique event categories in QC report."""
        summary = create_event_summary(session_id="test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert len(summary.event_categories) > 0
        # Should extract unique event types
        expected_types = {"BNC1High", "BNC1Low", "Flex1Trig2"}
        assert set(summary.event_categories).intersection(expected_types)


# Fixtures
@pytest.fixture
def valid_bpod_file(tmp_path, monkeypatch):
    """Create a minimal valid Bpod .mat file for testing."""
    bpod_file = tmp_path / "test_bpod.mat"

    # Mock the loadmat function to return valid data when this file is loaded
    def mock_loadmat(path, squeeze_me=True, struct_as_record=False):
        return {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [8.0, 8.1]}, "Events": {}}]},
            }
        }

    # Create the file (empty is fine, we're mocking the load)
    bpod_file.write_text("")

    # Patch loadmat in the events module
    from w2t_bkin import events

    monkeypatch.setattr(events, "loadmat", mock_loadmat)

    return bpod_file


@pytest.fixture
def parsed_bpod_data():
    """Realistic Bpod structure based on actual .mat files."""
    return {
        "SessionData": {
            "nTrials": 3,
            "TrialStartTimestamp": [0.0, 10.0, 20.0],
            "TrialEndTimestamp": [9.0, 19.0, 29.0],
            "TrialTypes": [1, 2, 1],
            "TrialSettings": [
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
                {"GUI": {"rewardamount_R": 35, "reward_delay": 0.4}},
            ],
            "RawEvents": {
                "Trial": [
                    {
                        "States": {
                            "ITI": [0.0, 7.0],
                            "Response_window": [7.0, 8.5],
                            "HIT": [8.5, 8.6],
                            "RightReward": [8.6, 9.0],
                            "Miss": [float("nan"), float("nan")],
                        },
                        "Events": {"Flex1Trig2": [0.0001, 7.1], "BNC1High": [1.5, 8.5], "BNC1Low": [1.6, 8.6], "Tup": [7.0, 8.5, 8.6, 9.0]},
                    },
                    {
                        "States": {
                            "ITI": [0.0, 6.0],
                            "Response_window": [6.0, 8.0],
                            "Miss": [8.0, 8.1],
                            "HIT": [float("nan"), float("nan")],
                            "RightReward": [float("nan"), float("nan")],
                        },
                        "Events": {"Flex1Trig2": [0.0001, 6.1], "Tup": [6.0, 8.0, 8.1]},
                    },
                    {
                        "States": {
                            "ITI": [0.0, 7.5],
                            "Response_window": [7.5, 9.0],
                            "HIT": [9.0, 9.1],
                            "RightReward": [9.1, 9.5],
                            "Miss": [float("nan"), float("nan")],
                        },
                        "Events": {"Flex1Trig2": [0.0001, 7.6], "BNC1High": [2.0, 9.0], "BNC1Low": [2.1, 9.1], "Tup": [7.5, 9.0, 9.1, 9.5]},
                    },
                ]
            },
        }
    }


@pytest.fixture
def trial_list():
    return [
        TrialData(trial_number=1, start_time=0.0, stop_time=9.0, outcome="hit"),
        TrialData(trial_number=2, start_time=10.0, stop_time=19.0, outcome="miss"),
        TrialData(trial_number=3, start_time=20.0, stop_time=29.0, outcome="hit"),
    ]


@pytest.fixture
def event_list():
    """Realistic Bpod events based on actual data."""
    return [
        BehavioralEvent(event_type="Flex1Trig2", timestamp=0.0001, trial_number=1),
        BehavioralEvent(event_type="BNC1High", timestamp=1.5, trial_number=1),
        BehavioralEvent(event_type="BNC1Low", timestamp=1.6, trial_number=1),
        BehavioralEvent(event_type="Flex1Trig2", timestamp=7.1, trial_number=1),
        BehavioralEvent(event_type="BNC1High", timestamp=8.5, trial_number=1),
        BehavioralEvent(event_type="Flex1Trig2", timestamp=0.0001, trial_number=2),
        BehavioralEvent(event_type="Flex1Trig2", timestamp=0.0001, trial_number=3),
        BehavioralEvent(event_type="BNC1High", timestamp=2.0, trial_number=3),
        BehavioralEvent(event_type="BNC1Low", timestamp=2.1, trial_number=3),
    ]


class TestEdgeCasesAndErrorHandling:
    """Test edge cases specific to Bpod data structure."""

    def test_Should_HandleNaNStates_When_StateNotVisited(self, parsed_bpod_data):
        """States with [NaN, NaN] indicate state was not visited in that trial."""
        trials = extract_trials(parsed_bpod_data)

        # Trial 1 has Miss state as NaN (not visited) → should be "hit"
        assert trials[0].outcome == "hit"

    def test_Should_SkipNaNStates_When_InferringOutcome(self):
        """Only non-NaN states should be considered for outcome inference."""
        data_with_nans = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [float("nan"), float("nan")], "Miss": [8.0, 8.1]}, "Events": {}}]},
            }
        }

        trials = extract_trials(data_with_nans)
        assert trials[0].outcome == "miss"

    def test_Should_HandleTrialsWithoutEvents_When_Extracting(self):
        """Some trials may have empty Events dict."""
        data_no_events = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [8.0, 8.1]}, "Events": {}}]},
            }
        }

        events = extract_behavioral_events(data_no_events)
        assert len(events) == 0

    def test_Should_HandleMultipleTimestampsPerEvent_When_Extracting(self, parsed_bpod_data):
        """Events like BNC1High can have multiple timestamps within a trial."""
        events = extract_behavioral_events(parsed_bpod_data)

        # Should create separate BehavioralEvent for each timestamp
        bnc1_high_events = [e for e in events if e.event_type == "BNC1High"]
        assert len(bnc1_high_events) >= 2  # At least 2 BNC1High events across trials
