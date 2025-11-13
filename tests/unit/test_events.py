"""Unit tests for events module (Bpod parsing and TTL alignment).

Tests Bpod .mat file parsing, trial/event extraction, and TTL-based absolute time alignment.

Requirements: FR-11 (Bpod parsing), FR-14 (QC reporting), FR-6 (TTL alignment), NFR-7 (security)
Acceptance: A4 (trial counts and event categories in QC with absolute timestamps)

Fixtures:
- Shared fixtures are defined in tests/conftest.py
- Local fixture 'valid_bpod_file' requires monkeypatch and is test-specific
"""

from datetime import datetime
import json
from pathlib import Path

import pytest

from w2t_bkin.domain import Session, Trial, TrialEvent, TrialSummary
from w2t_bkin.domain.session import TTL, BpodSession, BpodTrialType, SessionMetadata
from w2t_bkin.domain.trials import TrialOutcome
from w2t_bkin.events import (
    BpodParseError,
    BpodValidationError,
    EventsError,
    create_event_summary,
    extract_behavioral_events,
    extract_trials,
    parse_bpod_mat,
    validate_bpod_structure,
    write_event_summary,
)
from w2t_bkin.sync import SyncError, align_bpod_trials_to_ttl, get_ttl_pulses

# =============================================================================
# Local Fixtures (Test-Specific)
# =============================================================================


@pytest.fixture
def valid_bpod_file(tmp_path, monkeypatch):
    """Create a minimal valid Bpod .mat file for testing.

    Note: This fixture is local because it uses monkeypatch for mocking loadmat,
    which is specific to these parsing tests.
    """
    bpod_file = tmp_path / "test_bpod.mat"

    # Mock loadmat to return valid data
    def mock_loadmat(path, squeeze_me=True, struct_as_record=False):
        return {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [8.0, 8.1]}, "Events": {}}]},
            }
        }

    bpod_file.write_text("")

    from w2t_bkin import events

    monkeypatch.setattr(events, "loadmat", mock_loadmat)

    return bpod_file


# =============================================================================
# Test Classes
# =============================================================================


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
        trials, _ = extract_trials(parsed_bpod_data)
        assert len(trials) == 3
        assert all(isinstance(t, Trial) for t in trials)

    def test_Should_IncludeTrialTimestamps_When_Extracting(self, parsed_bpod_data):
        trials, _ = extract_trials(parsed_bpod_data)
        first_trial = trials[0]
        assert hasattr(first_trial, "start_time")
        assert hasattr(first_trial, "stop_time")
        assert first_trial.start_time == 0.0
        assert first_trial.stop_time == 9.0

    def test_Should_InferOutcomeFromStates_When_Extracting(self, parsed_bpod_data):
        """Outcome must be inferred from States (HIT/Miss), not from TrialSettings."""
        trials, _ = extract_trials(parsed_bpod_data)

        # Trial 0: HIT state is valid (not NaN) → hit
        from w2t_bkin.domain.trials import TrialOutcome

        assert trials[0].outcome == TrialOutcome.HIT

        # Trial 1: Miss state is valid (not NaN) → miss
        assert trials[1].outcome == TrialOutcome.MISS

        # Trial 2: HIT state is valid (not NaN) → hit
        assert trials[2].outcome == TrialOutcome.HIT

    def test_Should_IncludeTrialNumber_When_Extracting(self, parsed_bpod_data):
        """Trials should include trial_number field (1-indexed)."""
        trials, _ = extract_trials(parsed_bpod_data)
        assert trials[0].trial_number == 1
        assert trials[1].trial_number == 2
        assert trials[2].trial_number == 3


class TestTrialEventExtraction:
    """Test behavioral event extraction - FR-11."""

    def test_Should_ExtractEvents_When_BpodParsed(self, parsed_bpod_data):
        events = extract_behavioral_events(parsed_bpod_data)
        assert len(events) > 0
        assert all(isinstance(e, TrialEvent) for e in events)

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
        """Events should know which trial they belong to (stored in metadata)."""
        events = extract_behavioral_events(parsed_bpod_data)

        # Check trial numbers are assigned in metadata
        trial_numbers = {e.metadata.get("trial_number") if e.metadata else None for e in events}
        trial_numbers.discard(None)  # Remove None if present
        assert trial_numbers == {1.0, 2.0, 3.0}


class TestEventSummaryCreation:
    """Test event summary generation - FR-14, A4."""

    def test_Should_CreateSummary_When_TrialsExtracted(self, trial_list, event_list):
        summary = create_event_summary("test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert isinstance(summary, TrialSummary)
        assert summary.total_trials == len(trial_list)

    def test_Should_CountTrialOutcomes_When_CreatingSummary(self, trial_list, event_list):
        """A4: Include trial counts by outcome in QC report."""
        summary = create_event_summary("test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert hasattr(summary, "outcome_counts")
        assert isinstance(summary.outcome_counts, dict)
        # Should count hits and misses
        assert summary.outcome_counts.get("hit", 0) == 2
        assert summary.outcome_counts.get("miss", 0) == 1

    def test_Should_ListEventCategories_When_CreatingSummary(self, trial_list, event_list):
        """A4: List unique event categories in QC report."""
        summary = create_event_summary("test", trials=trial_list, events=event_list, bpod_files=["/path/bpod.mat"])
        assert len(summary.event_categories) > 0
        # Should extract unique event types
        expected_types = {"BNC1High", "BNC1Low", "Flex1Trig2"}
        assert set(summary.event_categories).intersection(expected_types)


class TestEdgeCasesAndErrorHandling:
    """Test edge cases specific to Bpod data structure."""

    def test_Should_HandleNaNStates_When_StateNotVisited(self, parsed_bpod_data):
        """States with [NaN, NaN] indicate state was not visited in that trial."""
        trials, _ = extract_trials(parsed_bpod_data)

        # Trial 1 has Miss state as NaN (not visited) → should be "hit"
        from w2t_bkin.domain.trials import TrialOutcome

        assert trials[0].outcome == TrialOutcome.HIT

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

        trials, _ = extract_trials(data_with_nans)
        from w2t_bkin.domain.trials import TrialOutcome

        assert trials[0].outcome == TrialOutcome.MISS

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

        # Should create separate TrialEvent for each timestamp
        bnc1_high_events = [e for e in events if e.event_type == "BNC1High"]
        assert len(bnc1_high_events) >= 2  # At least 2 BNC1High events across trials


class TestSecurityAndValidation:
    """Test security features and input validation."""

    def test_Should_RaiseError_When_FileTooLarge(self, tmp_path, monkeypatch):
        """Should reject files exceeding size limit (security)."""
        from w2t_bkin.events import BpodValidationError, parse_bpod_mat

        # Create a large dummy file
        large_file = tmp_path / "large_bpod.mat"
        large_file.write_text("x" * (101 * 1024 * 1024))  # 101 MB

        with pytest.raises(BpodValidationError, match="too large"):
            parse_bpod_mat(large_file)

    def test_Should_RaiseError_When_InvalidExtension(self, tmp_path):
        """Should reject files with invalid extensions (security)."""
        from w2t_bkin.events import BpodValidationError, parse_bpod_mat

        invalid_file = tmp_path / "bpod.txt"
        invalid_file.write_text("data")

        with pytest.raises(BpodValidationError, match="Invalid file extension"):
            parse_bpod_mat(invalid_file)

    def test_Should_SanitizeEventTypes_When_Extracting(self, monkeypatch):
        """Should sanitize event types from external data (security)."""
        from w2t_bkin.events import extract_behavioral_events

        # Data with potentially malicious event names
        data_with_bad_events = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {
                    "Trial": [
                        {
                            "States": {"HIT": [8.0, 8.1]},
                            "Events": {
                                "Normal\x00Event": [1.0],  # Null byte
                                "Event\nWith\nNewlines": [2.0],  # Newlines
                                "A" * 200: [3.0],  # Too long
                            },
                        }
                    ]
                },
            }
        }

        events = extract_behavioral_events(data_with_bad_events)

        # All event types should be sanitized
        for event in events:
            assert "\x00" not in event.event_type
            assert "\n" not in event.event_type
            assert len(event.event_type) <= 100

    def test_Should_ValidateOutcomes_When_Inferring(self):
        """Should validate outcomes against whitelist (security)."""
        from w2t_bkin.events import extract_trials

        # Create data that would infer to a non-whitelisted outcome
        # The system should default to "unknown" for invalid outcomes
        data = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [8.0, 8.1]}, "Events": {}}]},
            }
        }

        trials, _ = extract_trials(data)
        # Should get a valid outcome from Trial TrialOutcome enum
        from w2t_bkin.domain.trials import TrialOutcome

        assert trials[0].outcome in [TrialOutcome.HIT, TrialOutcome.MISS, TrialOutcome.CORRECT_REJECTION, TrialOutcome.FALSE_ALARM]

    def test_Should_NotLeakPathInError_When_ParseFails(self, tmp_path, monkeypatch):
        """Should avoid leaking full file paths in error messages (security)."""
        from w2t_bkin.events import BpodParseError, parse_bpod_mat

        # Create a file that will fail to parse
        bad_file = tmp_path / "sensitive" / "path" / "to" / "bpod.mat"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_bytes(b"not a valid mat file")

        # Mock loadmat to fail
        from w2t_bkin import events

        def mock_loadmat(*args, **kwargs):
            raise ValueError("Parse error")

        monkeypatch.setattr(events, "loadmat", mock_loadmat)

        with pytest.raises(BpodParseError) as exc_info:
            parse_bpod_mat(bad_file)

        # Error message should not contain the full sensitive path
        error_msg = str(exc_info.value)
        assert "sensitive/path/to" not in error_msg
        assert "bpod.mat" not in error_msg  # Should only show generic message


# =============================================================================
# TTL Alignment Tests
# =============================================================================


class TestTTLAlignment:
    """Test TTL-based absolute time alignment - FR-6."""

    def test_Should_LoadTTLPulses_When_ValidSession(self, mock_session_with_ttl):
        """Should load TTL pulses from session TTL files."""
        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)

        assert "ttl_cue" in ttl_pulses
        assert len(ttl_pulses["ttl_cue"]) == 3
        assert ttl_pulses["ttl_cue"] == [10.0, 25.0, 40.0]

    def test_Should_ReturnEmptyList_When_NoTTLFiles(self, tmp_path):
        """Should return empty list when TTL files not found."""
        session = Session(
            session=SessionMetadata(
                id="test",
                subject_id="m1",
                date="2025-11-13",
                experimenter="Test",
                description="Test",
                sex="M",
                age="P60",
                genotype="WT",
            ),
            bpod=BpodSession(path="Bpod/*.mat", order="name_asc", trial_types=[]),
            TTLs=[TTL(id="missing", description="Missing TTL", paths="TTLs/missing*.txt")],
            cameras=[],
            session_dir=str(tmp_path),
        )

        ttl_pulses = get_ttl_pulses(session)
        assert "missing" in ttl_pulses
        assert ttl_pulses["missing"] == []

    def test_Should_AlignTrials_When_ValidSync(self, mock_session_with_ttl, bpod_data_with_sync):
        """Should align all trials when sync signals match TTL pulses."""
        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)

        trial_offsets, warnings = align_bpod_trials_to_ttl(mock_session_with_ttl, bpod_data_with_sync, ttl_pulses)

        assert len(trial_offsets) == 3
        assert len(warnings) == 0

        # Extract trials with absolute timestamps
        aligned_trials, _ = extract_trials(bpod_data_with_sync, trial_offsets=trial_offsets)

        assert len(aligned_trials) == 3

        # Trial 1: W2L_Audio at 6.0 (rel) → TTL at 10.0 (abs) → offset 4.0
        assert trial_offsets[1] == pytest.approx(4.0)
        assert aligned_trials[0].start_time == pytest.approx(4.0)
        assert aligned_trials[0].stop_time == pytest.approx(13.0)

        # Trial 2: A2L_Audio at 5.0 (rel) → TTL at 25.0 (abs) → offset 20.0
        assert trial_offsets[2] == pytest.approx(20.0)
        assert aligned_trials[1].start_time == pytest.approx(20.0)
        assert aligned_trials[1].stop_time == pytest.approx(28.5)

        # Trial 3: W2L_Audio at 6.5 (rel) → TTL at 40.0 (abs) → offset 33.5
        assert trial_offsets[3] == pytest.approx(33.5)
        assert aligned_trials[2].start_time == pytest.approx(33.5)
        assert aligned_trials[2].stop_time == pytest.approx(43.5)

    def test_Should_SkipTrial_When_SyncSignalMissing(self, mock_session_with_ttl):
        """Should skip trials when sync signal state is not visited."""
        bpod_data = {
            "SessionData": {
                "nTrials": 2,
                "TrialStartTimestamp": [0.0, 0.0],
                "TrialEndTimestamp": [9.0, 8.0],
                "TrialTypes": [1, 1],
                "RawEvents": {
                    "Trial": [
                        {"States": {"W2L_Audio": [6.0, 7.0], "HIT": [7.5, 7.6]}, "Events": {}},
                        {"States": {"ITI": [0.0, 5.0], "Miss": [7.0, 7.1]}, "Events": {}},  # No W2L_Audio
                    ]
                },
                "Info": {"SessionDate": "13-Nov-2025", "SessionStartTime_UTC": "10:00:00"},
            }
        }

        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)
        trial_offsets, warnings = align_bpod_trials_to_ttl(mock_session_with_ttl, bpod_data, ttl_pulses)

        # Extract trials with offsets (only trial 1 should have offset)
        aligned_trials, _ = extract_trials(bpod_data, trial_offsets=trial_offsets)

        assert len(aligned_trials) == 2  # Both trials extracted, but only 1 has absolute timestamp
        assert 1 in trial_offsets
        assert 2 not in trial_offsets
        assert any("Trial 2" in w and "sync_signal" in w for w in warnings)

    def test_Should_WarnOnFewerTTLPulses(self, mock_session_with_ttl):
        """Should warn when fewer TTL pulses than trials needing alignment."""
        bpod_data = {
            "SessionData": {
                "nTrials": 5,
                "TrialStartTimestamp": [0.0] * 5,
                "TrialEndTimestamp": [9.0] * 5,
                "TrialTypes": [1] * 5,
                "RawEvents": {"Trial": [{"States": {"W2L_Audio": [6.0, 7.0], "HIT": [7.5, 7.6]}, "Events": {}}] * 5},
                "Info": {"SessionDate": "13-Nov-2025", "SessionStartTime_UTC": "10:00:00"},
            }
        }

        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)  # Only 3 pulses
        trial_offsets, warnings = align_bpod_trials_to_ttl(mock_session_with_ttl, bpod_data, ttl_pulses)

        # Extract trials - should get all 5 trials, but only 3 will have absolute timestamps
        aligned_trials, _ = extract_trials(bpod_data, trial_offsets=trial_offsets)

        assert len(aligned_trials) == 5  # All trials extracted
        assert len(trial_offsets) == 3  # Only 3 have offsets
        assert any("Trial 4" in w for w in warnings)
        assert any("Trial 5" in w for w in warnings)

    def test_Should_WarnOnUnusedPulses(self, mock_session_with_ttl):
        """Should warn when extra TTL pulses remain unused."""
        bpod_data = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [9.0],
                "TrialTypes": [1],
                "RawEvents": {"Trial": [{"States": {"W2L_Audio": [6.0, 7.0], "HIT": [7.5, 7.6]}, "Events": {}}]},
                "Info": {"SessionDate": "13-Nov-2025", "SessionStartTime_UTC": "10:00:00"},
            }
        }

        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)  # 3 pulses
        trial_offsets, warnings = align_bpod_trials_to_ttl(mock_session_with_ttl, bpod_data, ttl_pulses)

        # Extract trial with offset
        aligned_trials, _ = extract_trials(bpod_data, trial_offsets=trial_offsets)

        assert len(aligned_trials) == 1
        assert any("unused pulses" in w for w in warnings)

    def test_Should_RaiseError_When_NoTrialTypeConfig(self, bpod_data_with_sync, tmp_path):
        """Should raise error when session has no trial_type configuration."""
        session = Session(
            session=SessionMetadata(
                id="test",
                subject_id="m1",
                date="2025-11-13",
                experimenter="Test",
                description="Test",
                sex="M",
                age="P60",
                genotype="WT",
            ),
            bpod=BpodSession(path="Bpod/*.mat", order="name_asc", trial_types=[]),
            TTLs=[],
            cameras=[],
            session_dir=str(tmp_path),
        )

        with pytest.raises(SyncError, match="No trial_type sync configuration"):
            align_bpod_trials_to_ttl(session, bpod_data_with_sync, {})


class TestExtractTrialsWithAlignment:
    """Test extract_trials integration with TTL alignment."""

    def test_Should_UseAlignment_When_OffsetsProvided(self, mock_session_with_ttl, bpod_data_with_sync):
        """Should use TTL alignment when trial_offsets provided."""
        # Get TTL pulses and compute offsets
        ttl_pulses = get_ttl_pulses(mock_session_with_ttl)
        trial_offsets, _ = align_bpod_trials_to_ttl(mock_session_with_ttl, bpod_data_with_sync, ttl_pulses)

        # Extract trials with absolute timestamps
        trials, _ = extract_trials(bpod_data_with_sync, trial_offsets=trial_offsets)

        assert len(trials) == 3
        assert trials[0].start_time == pytest.approx(4.0)  # Absolute timestamp

    def test_Should_UseRelativeTime_When_NoOffsets(self, bpod_data_with_sync):
        """Should use relative timestamps when no trial_offsets provided."""
        trials, _ = extract_trials(bpod_data_with_sync)

        assert len(trials) == 3
        assert trials[0].start_time == 0.0  # Relative timestamp


class TestExtractEventsWithAlignment:
    """Test behavioral event extraction with absolute timestamps."""

    def test_Should_UseAbsoluteTime_When_OffsetsProvided(self, bpod_data_with_sync):
        """Should convert event timestamps to absolute time when offsets provided."""
        trial_offsets = {1: 4.0, 2: 20.0, 3: 33.5}

        events = extract_behavioral_events(bpod_data_with_sync, trial_offsets=trial_offsets)

        # Trial 1: Port1In at 7.5 (rel) → 4.0 + 7.5 = 11.5 (abs)
        trial1_events = [e for e in events if e.metadata.get("trial_number") == 1.0]
        assert len(trial1_events) == 1
        assert trial1_events[0].timestamp == pytest.approx(11.5)

        # Trial 3: Port1In at 8.0 (rel) → 33.5 + 8.0 = 41.5 (abs)
        trial3_events = [e for e in events if e.metadata.get("trial_number") == 3.0]
        assert len(trial3_events) == 1
        assert trial3_events[0].timestamp == pytest.approx(41.5)

    def test_Should_UseRelativeTime_When_NoOffsets(self, bpod_data_with_sync):
        """Should use relative timestamps when no offsets provided."""
        events = extract_behavioral_events(bpod_data_with_sync)

        trial1_events = [e for e in events if e.metadata.get("trial_number") == 1.0]
        assert len(trial1_events) == 1
        assert trial1_events[0].timestamp == pytest.approx(7.5)  # Relative


class TestEventSummaryWithAlignment:
    """Test event summary creation with alignment statistics."""

    def test_Should_IncludeAlignmentStats_When_Provided(self):
        """Should include alignment statistics when provided."""
        trials = [
            Trial(trial_number=1, trial_type=1, start_time=4.0, stop_time=13.0, outcome=TrialOutcome.HIT),
            Trial(trial_number=2, trial_type=2, start_time=20.0, stop_time=28.5, outcome=TrialOutcome.MISS),
        ]
        warnings = ["Trial 3: sync_signal not found"]

        summary = create_event_summary(
            "test-session",
            trials=trials,
            events=[],
            bpod_files=["test.mat"],
            n_total_trials=3,
            alignment_warnings=warnings,
        )

        assert summary.total_trials == 3
        assert summary.n_aligned == 2
        assert summary.n_dropped == 1
        assert "Trial 3" in summary.alignment_warnings[0]

    def test_Should_OmitAlignmentStats_When_NotProvided(self):
        """Should set alignment stats to None when not using alignment."""
        trials = [
            Trial(trial_number=1, trial_type=1, start_time=0.0, stop_time=9.0, outcome=TrialOutcome.HIT),
        ]

        summary = create_event_summary("test-session", trials=trials, events=[], bpod_files=["test.mat"])

        assert summary.total_trials == 1
        assert summary.n_aligned is None
        assert summary.n_dropped is None
        assert summary.alignment_warnings == []
