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

import numpy as np
import pytest

from w2t_bkin.domain import Session, SessionMetadata
from w2t_bkin.domain.session import TTL, BpodSession, BpodTrialType
from w2t_bkin.events import (
    BpodParseError,
    BpodValidationError,
    EventsError,
    create_event_summary,
    extract_behavioral_events,
    extract_trials,
    index_bpod_data,
    parse_bpod_mat,
    split_bpod_data,
    validate_bpod_structure,
    write_event_summary,
)
from w2t_bkin.events.bpod import discover_bpod_files_from_pattern, parse_bpod, parse_bpod_from_files
from w2t_bkin.events.models import Trial, TrialEvent, TrialOutcome, TrialSummary
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

    from w2t_bkin.events import bpod

    monkeypatch.setattr(bpod, "loadmat", mock_loadmat)

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


class TestBpodRawFileAPIs:
    """Test raw-file based Bpod helpers (no Session dependency)."""

    def test_Should_DiscoverFilesFromPattern_When_ValidDirAndPattern(self, fixture_session_path):
        """discover_bpod_files_from_pattern should honor pattern and order."""
        pattern = "Bpod/*.mat"
        order = "name_asc"

        files = discover_bpod_files_from_pattern(fixture_session_path, pattern, order)

        assert len(files) >= 1
        # Ensure paths are within the session directory
        assert all(str(path).startswith(str(fixture_session_path)) for path in files)

    def test_Should_ParseFromFiles_When_SingleFileProvided(self, parsed_bpod_data, tmp_path, monkeypatch):
        """parse_bpod_from_files should behave like merge_bpod_sessions for one file."""

        # Re-use valid_bpod_file-like behavior via monkeypatch on loadmat
        bpod_file = tmp_path / "single.mat"
        bpod_file.write_text("")

        def mock_loadmat(path, squeeze_me=True, struct_as_record=False):  # noqa: D401
            return parsed_bpod_data

        from w2t_bkin.events import bpod

        monkeypatch.setattr(bpod, "loadmat", mock_loadmat)

        result = parse_bpod_from_files([bpod_file], continuous_time=True)

        assert validate_bpod_structure(result) is True
        assert result["SessionData"]["nTrials"] == parsed_bpod_data["SessionData"]["nTrials"]

    def test_Should_ParseBpod_When_PatternAndOrderProvided(self, parsed_bpod_data, fixture_session_path, tmp_path, monkeypatch):
        """parse_bpod should discover files from pattern and merge them."""

        # Create a fake Bpod file under the expected pattern path
        bpod_dir = fixture_session_path / "Bpod"
        bpod_dir.mkdir(parents=True, exist_ok=True)
        bpod_file = bpod_dir / "session_01.mat"
        bpod_file.write_text("")

        # Monkeypatch loadmat to return known parsed data
        from w2t_bkin.events import bpod as bpod_module

        def mock_loadmat(path, squeeze_me=True, struct_as_record=False):  # noqa: D401
            return parsed_bpod_data

        monkeypatch.setattr(bpod_module, "loadmat", mock_loadmat)

        result = parse_bpod(
            session_dir=fixture_session_path,
            pattern="Bpod/*.mat",
            order="name_asc",
            continuous_time=True,
        )

        assert validate_bpod_structure(result) is True
        assert result["SessionData"]["nTrials"] == parsed_bpod_data["SessionData"]["nTrials"]


class TestTrialExtraction:
    """Test trial data extraction - FR-11."""

    def test_Should_ExtractTrials_When_BpodParsed(self, parsed_bpod_data):
        trials = extract_trials(parsed_bpod_data)
        assert len(trials) == 3
        assert all(isinstance(t, Trial) for t in trials)

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
        from w2t_bkin.events.models import TrialOutcome

        assert trials[0].outcome == TrialOutcome.HIT

        # Trial 1: Miss state is valid (not NaN) → miss
        assert trials[1].outcome == TrialOutcome.MISS

        # Trial 2: HIT state is valid (not NaN) → hit
        assert trials[2].outcome == TrialOutcome.HIT

    def test_Should_IncludeTrialNumber_When_Extracting(self, parsed_bpod_data):
        """Trials should include trial_number field (1-indexed)."""
        trials = extract_trials(parsed_bpod_data)
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
        trials = extract_trials(parsed_bpod_data)

        # Trial 1 has Miss state as NaN (not visited)  should be "hit"
        trials = extract_trials(parsed_bpod_data)

        from w2t_bkin.events.models import TrialOutcome

        assert trials[0].outcome == TrialOutcome.HIT
        data_with_nans = {
            "SessionData": {
                "nTrials": 1,
                "TrialStartTimestamp": [0.0],
                "TrialEndTimestamp": [10.0],
                "RawEvents": {"Trial": [{"States": {"HIT": [float("nan"), float("nan")], "Miss": [8.0, 8.1]}, "Events": {}}]},
            }
        }

        trials = extract_trials(data_with_nans)
        from w2t_bkin.events.models import TrialOutcome

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

        trials = extract_trials(data)
        # Should get a valid outcome from Trial TrialOutcome enum
        from w2t_bkin.events.models import TrialOutcome

        assert trials[0].outcome in [TrialOutcome.HIT, TrialOutcome.MISS, TrialOutcome.CORRECT_REJECTION, TrialOutcome.FALSE_ALARM]

    def test_Should_NotLeakPathInError_When_ParseFails(self, tmp_path, monkeypatch):
        """Should avoid leaking full file paths in error messages (security)."""
        from w2t_bkin.events import BpodParseError, parse_bpod_mat

        # Create a file that will fail to parse
        bad_file = tmp_path / "sensitive" / "path" / "to" / "bpod.mat"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_bytes(b"not a valid mat file")

        # Mock loadmat to fail
        from w2t_bkin.events import bpod

        def mock_loadmat(*args, **kwargs):
            raise ValueError("Parse error")

        monkeypatch.setattr(bpod, "loadmat", mock_loadmat)

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
        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

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

        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in session.TTLs}
        session_dir = Path(session.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)
        assert "missing" in ttl_pulses
        assert ttl_pulses["missing"] == []

    def test_Should_AlignTrials_When_ValidSync(self, mock_session_with_ttl, bpod_data_with_sync):
        """Should align all trials when sync signals match TTL pulses."""
        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

        # Extract trial type configs and call primitive API (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, warnings = align_bpod_trials_to_ttl(trial_type_configs, bpod_data_with_sync, ttl_pulses)

        assert len(trial_offsets) == 3
        assert len(warnings) == 0

        # Extract trials with absolute timestamps
        aligned_trials = extract_trials(bpod_data_with_sync, trial_offsets=trial_offsets)

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

        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)
        # Extract trial type configs (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, warnings = align_bpod_trials_to_ttl(trial_type_configs, bpod_data, ttl_pulses)

        # Extract trials with offsets (only trial 1 should have offset)
        aligned_trials = extract_trials(bpod_data, trial_offsets=trial_offsets)

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

        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)  # Only 3 pulses
        # Extract trial type configs (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, warnings = align_bpod_trials_to_ttl(trial_type_configs, bpod_data, ttl_pulses)

        # Extract trials - should get all 5 trials, but only 3 will have absolute timestamps
        aligned_trials = extract_trials(bpod_data, trial_offsets=trial_offsets)

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

        # Extract primitives from Session (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)  # 3 pulses
        # Extract trial type configs (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, warnings = align_bpod_trials_to_ttl(trial_type_configs, bpod_data, ttl_pulses)

        # Extract trial with offset
        aligned_trials = extract_trials(bpod_data, trial_offsets=trial_offsets)

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

        # Extract trial type configs (Phase 2 pattern) - empty list should raise error
        trial_type_configs = session.bpod.trial_types
        with pytest.raises(SyncError, match="No trial_type sync configuration"):
            align_bpod_trials_to_ttl(trial_type_configs, bpod_data_with_sync, {})

    def test_Should_AlignMergedBpod_When_NonZeroTrialStartTimestamp(self, mock_session_with_ttl):
        """Should correctly align merged Bpod files with non-zero TrialStartTimestamp."""
        # Simulate merged Bpod data where second file's trials have offset TrialStartTimestamp
        # This happens when continuous_time=True during merge
        bpod_data = {
            "SessionData": {
                "nTrials": 3,
                "TrialStartTimestamp": [0.0, 100.0, 200.0],  # File 1: 0s, File 2: starts at 100s, File 3: starts at 200s
                "TrialEndTimestamp": [9.0, 108.0, 210.0],
                "TrialTypes": [1, 2, 1],
                "RawEvents": {
                    "Trial": [
                        # Trial 1: W2L_Audio at 6.0s (rel to trial), TTL at 10.0s (abs)
                        {"States": {"W2L_Audio": [6.0, 7.0], "HIT": [7.5, 7.6]}, "Events": {}},
                        # Trial 2: A2L_Audio at 5.0s (rel to trial), starts at 100s, TTL at 110.0s (abs)
                        # In merged timeline: 100.0 + 5.0 = 105.0s → should align to TTL 110.0s
                        {"States": {"A2L_Audio": [5.0, 6.0], "Miss": [7.0, 7.1]}, "Events": {}},
                        # Trial 3: W2L_Audio at 6.5s (rel to trial), starts at 200s, TTL at 210.0s (abs)
                        # In merged timeline: 200.0 + 6.5 = 206.5s → should align to TTL 210.0s
                        {"States": {"W2L_Audio": [6.5, 7.5], "HIT": [8.0, 8.1]}, "Events": {}},
                    ]
                },
                "Info": {"SessionDate": "13-Nov-2025", "SessionStartTime_UTC": "10:00:00"},
            }
        }

        # TTL pulses for alignment
        ttl_pulses = {
            "ttl_cue": [10.0, 110.0, 210.0],  # All sync signals use ttl_cue channel
        }

        # Extract trial type configs (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, warnings = align_bpod_trials_to_ttl(trial_type_configs, bpod_data, ttl_pulses)

        assert len(trial_offsets) == 3
        assert len(warnings) == 0

        # Trial 1: TrialStart=0.0, sync at 6.0 (rel) → 0.0+6.0=6.0 (merged) → TTL 10.0 → offset = 10.0 - 6.0 = 4.0
        assert trial_offsets[1] == pytest.approx(4.0)

        # Trial 2: TrialStart=100.0, sync at 5.0 (rel) → 100.0+5.0=105.0 (merged) → TTL 110.0 → offset = 110.0 - 105.0 = 5.0
        assert trial_offsets[2] == pytest.approx(5.0)

        # Trial 3: TrialStart=200.0, sync at 6.5 (rel) → 200.0+6.5=206.5 (merged) → TTL 210.0 → offset = 210.0 - 206.5 = 3.5
        assert trial_offsets[3] == pytest.approx(3.5)

        # Extract trials with absolute timestamps to verify alignment
        aligned_trials = extract_trials(bpod_data, trial_offsets=trial_offsets)

        assert len(aligned_trials) == 3

        # Verify absolute start times
        # Trial 1: offset + TrialStart = 4.0 + 0.0 = 4.0
        assert aligned_trials[0].start_time == pytest.approx(4.0)
        assert aligned_trials[0].stop_time == pytest.approx(13.0)

        # Trial 2: offset + TrialStart = 5.0 + 100.0 = 105.0
        assert aligned_trials[1].start_time == pytest.approx(105.0)
        assert aligned_trials[1].stop_time == pytest.approx(113.0)

        # Trial 3: offset + TrialStart = 3.5 + 200.0 = 203.5
        assert aligned_trials[2].start_time == pytest.approx(203.5)
        assert aligned_trials[2].stop_time == pytest.approx(213.5)

        # Verify sync signals align to TTL pulses
        # Trial 1: start + sync_rel = 4.0 + 6.0 = 10.0 ✓
        # Trial 2: start + sync_rel = 105.0 + 5.0 = 110.0 ✓
        # Trial 3: start + sync_rel = 203.5 + 6.5 = 210.0 ✓


class TestExtractTrialsWithAlignment:
    """Test extract_trials integration with TTL alignment."""

    def test_Should_UseAlignment_When_OffsetsProvided(self, mock_session_with_ttl, bpod_data_with_sync):
        """Should use TTL alignment when trial_offsets provided."""
        # Get TTL pulses and compute offsets (Phase 2 pattern)
        ttl_patterns = {ttl.id: ttl.paths for ttl in mock_session_with_ttl.TTLs}
        session_dir = Path(mock_session_with_ttl.session_dir)
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)
        # Extract trial type configs (Phase 2 pattern)
        trial_type_configs = mock_session_with_ttl.bpod.trial_types
        trial_offsets, _ = align_bpod_trials_to_ttl(trial_type_configs, bpod_data_with_sync, ttl_pulses)

        # Extract trials with absolute timestamps
        trials = extract_trials(bpod_data_with_sync, trial_offsets=trial_offsets)

        assert len(trials) == 3
        assert trials[0].start_time == pytest.approx(4.0)  # Absolute timestamp

    def test_Should_UseRelativeTime_When_NoOffsets(self, bpod_data_with_sync):
        """Should use relative timestamps when no trial_offsets provided."""
        trials = extract_trials(bpod_data_with_sync)

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


# =============================================================================
# Bpod Data Manipulation Tests (Indexing and I/O)
# =============================================================================


class TestBpodDataManipulation:
    """Test Bpod data indexing and file I/O operations."""

    # Indexing tests
    def test_Should_IndexFirstTrials_When_FilteringBpodData(self, sample_bpod_data):
        """Should correctly index and keep first N trials."""
        filtered = index_bpod_data(sample_bpod_data, [0, 1, 2])

        assert filtered["SessionData"]["nTrials"] == 3
        assert len(filtered["SessionData"]["TrialStartTimestamp"]) == 3
        assert len(filtered["SessionData"]["RawEvents"]["Trial"]) == 3
        np.testing.assert_array_equal(filtered["SessionData"]["TrialStartTimestamp"], np.array([0.0, 1.0, 2.0]))

    def test_Should_IndexNonSequentialTrials_When_FilteringBpodData(self, sample_bpod_data):
        """Should correctly index non-sequential trials."""
        filtered = index_bpod_data(sample_bpod_data, [1, 3])

        assert filtered["SessionData"]["nTrials"] == 2
        np.testing.assert_array_equal(filtered["SessionData"]["TrialStartTimestamp"], np.array([1.0, 3.0]))
        np.testing.assert_array_equal(filtered["SessionData"]["TrialTypes"], np.array([2, 2]))

    def test_Should_IndexSingleTrial_When_FilteringBpodData(self, sample_bpod_data):
        """Should correctly index a single trial."""
        filtered = index_bpod_data(sample_bpod_data, [2])

        assert filtered["SessionData"]["nTrials"] == 1
        assert filtered["SessionData"]["TrialStartTimestamp"][0] == 2.0

    def test_Should_RaiseIndexError_When_IndexOutOfBounds(self, sample_bpod_data):
        """Should raise IndexError for out-of-bounds indices."""
        with pytest.raises(IndexError, match="out of bounds"):
            index_bpod_data(sample_bpod_data, [0, 10])

    def test_Should_RaiseIndexError_When_NegativeIndex(self, sample_bpod_data):
        """Should raise IndexError for negative indices."""
        with pytest.raises(IndexError, match="out of bounds"):
            index_bpod_data(sample_bpod_data, [-1, 0])

    def test_Should_RaiseValueError_When_EmptyIndices(self, sample_bpod_data):
        """Should raise ValueError for empty index list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            index_bpod_data(sample_bpod_data, [])

    def test_Should_RaiseBpodParseError_When_InvalidStructure(self):
        """Should raise BpodParseError for invalid data structure."""
        invalid_data = {"SessionData": {"nTrials": 5}}

        with pytest.raises(BpodParseError, match="Invalid Bpod structure"):
            index_bpod_data(invalid_data, [0, 1])

    def test_Should_PreserveOriginalData_When_Indexing(self, sample_bpod_data):
        """Should not modify original data when indexing (deep copy)."""
        original_n_trials = sample_bpod_data["SessionData"]["nTrials"]
        original_start_times = sample_bpod_data["SessionData"]["TrialStartTimestamp"].copy()

        filtered = index_bpod_data(sample_bpod_data, [0, 1])

        # Verify original unchanged
        assert sample_bpod_data["SessionData"]["nTrials"] == original_n_trials
        np.testing.assert_array_equal(sample_bpod_data["SessionData"]["TrialStartTimestamp"], original_start_times)
        # Verify filtered is different
        assert filtered["SessionData"]["nTrials"] == 2

    # I/O tests
    def test_Should_WriteAndReadBpodMat_When_ValidData(self, sample_bpod_data, tmp_path):
        """Should write and read back Bpod data correctly."""
        from w2t_bkin.events import write_bpod_mat

        output_path = tmp_path / "test_session.mat"
        write_bpod_mat(sample_bpod_data, output_path)

        assert output_path.exists()

        reloaded = parse_bpod_mat(output_path)
        assert validate_bpod_structure(reloaded)

        from w2t_bkin.utils import convert_matlab_struct

        session_data = convert_matlab_struct(reloaded["SessionData"])
        assert session_data["nTrials"] == 5

    def test_Should_CreateDirectories_When_WritingBpodMat(self, sample_bpod_data, tmp_path):
        """Should create parent directories when writing."""
        from w2t_bkin.events import write_bpod_mat

        output_path = tmp_path / "subdir" / "nested" / "test_session.mat"
        write_bpod_mat(sample_bpod_data, output_path)

        assert output_path.exists()

    def test_Should_RaiseBpodValidationError_When_WritingInvalidStructure(self, tmp_path):
        """Should raise BpodValidationError when writing invalid data."""
        from w2t_bkin.events import write_bpod_mat
        from w2t_bkin.exceptions import BpodValidationError

        invalid_data = {"SessionData": {"nTrials": 5}}
        output_path = tmp_path / "invalid.mat"

        with pytest.raises(BpodValidationError, match="Invalid Bpod structure"):
            write_bpod_mat(invalid_data, output_path)

    # Integrated workflow tests
    def test_Should_FilterAndSaveSuccessfully_When_CompleteWorkflow(self, sample_bpod_data, tmp_path):
        """Should complete full workflow: filter → save → reload → filter again."""
        from w2t_bkin.events import write_bpod_mat
        from w2t_bkin.utils import convert_matlab_struct

        # Step 1: Filter to first 3 trials
        filtered = index_bpod_data(sample_bpod_data, [0, 1, 2])

        # Step 2: Save filtered data
        output_path = tmp_path / "filtered_session.mat"
        write_bpod_mat(filtered, output_path)

        # Step 3: Reload filtered data
        reloaded = parse_bpod_mat(output_path)
        assert validate_bpod_structure(reloaded)

        session_data = convert_matlab_struct(reloaded["SessionData"])
        assert session_data["nTrials"] == 3

        # Step 4: Filter again to single trial
        single_trial = index_bpod_data(reloaded, [1])
        single_session = convert_matlab_struct(single_trial["SessionData"])
        assert single_session["nTrials"] == 1

    def test_Should_PreserveAllData_When_WriteReadCycle(self, sample_bpod_data, tmp_path):
        """Should preserve all essential data through write → read cycle."""
        from w2t_bkin.events import write_bpod_mat
        from w2t_bkin.utils import convert_matlab_struct

        output_path = tmp_path / "test_roundtrip.mat"
        write_bpod_mat(sample_bpod_data, output_path)

        reloaded = parse_bpod_mat(output_path)
        original_session = sample_bpod_data["SessionData"]
        reloaded_session = convert_matlab_struct(reloaded["SessionData"])

        # Verify core fields
        assert reloaded_session["nTrials"] == original_session["nTrials"]
        np.testing.assert_allclose(reloaded_session["TrialStartTimestamp"], original_session["TrialStartTimestamp"], rtol=1e-10)
        np.testing.assert_allclose(reloaded_session["TrialEndTimestamp"], original_session["TrialEndTimestamp"], rtol=1e-10)
        np.testing.assert_array_equal(reloaded_session["TrialTypes"], original_session["TrialTypes"])

        # Verify trial structure
        original_raw = original_session["RawEvents"]
        reloaded_raw = convert_matlab_struct(reloaded_session["RawEvents"])
        assert len(reloaded_raw["Trial"]) == len(original_raw["Trial"])

    def test_Should_PreserveTrialData_When_Indexing(self, sample_bpod_data):
        """Should preserve all trial data (states, events, settings) when indexing."""
        from w2t_bkin.utils import convert_matlab_struct

        trial_indices = [1, 3]
        filtered = index_bpod_data(sample_bpod_data, trial_indices)

        original_session = sample_bpod_data["SessionData"]
        filtered_session = filtered["SessionData"]

        # Verify correct trials selected
        expected_start_times = [original_session["TrialStartTimestamp"][i] for i in trial_indices]
        np.testing.assert_array_equal(filtered_session["TrialStartTimestamp"], expected_start_times)

        # Verify trial structure integrity
        original_trials = original_session["RawEvents"]["Trial"]
        filtered_trials = filtered_session["RawEvents"]["Trial"]
        assert len(filtered_trials) == len(trial_indices)

        # Verify each trial's states and events preserved
        for filtered_idx, original_idx in enumerate(trial_indices):
            original_trial = original_trials[original_idx]
            filtered_trial = filtered_trials[filtered_idx]

            # States preserved
            if "States" in original_trial:
                assert set(filtered_trial["States"].keys()) == set(original_trial["States"].keys())
                for state_name in original_trial["States"].keys():
                    np.testing.assert_array_equal(np.array(filtered_trial["States"][state_name]), np.array(original_trial["States"][state_name]))

            # Events preserved
            if "Events" in original_trial:
                assert set(filtered_trial["Events"].keys()) == set(original_trial["Events"].keys())

    def test_Should_MergeWrittenFiles_When_UsingParseSession(self, sample_bpod_data, tmp_path):
        """Should successfully merge multiple Bpod files written with write_bpod_mat.

        This test reproduces the issue where write_bpod_mat creates files with
        mat_struct objects that aren't properly handled during merge.
        """
        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat

        # Create filtered datasets
        filtered_data1 = index_bpod_data(sample_bpod_data, [0, 1])
        filtered_data2 = index_bpod_data(sample_bpod_data, [2, 3])

        # Write to files
        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_file01.mat"
        file2 = bpod_dir / "session_file02.mat"

        write_bpod_mat(filtered_data1, file1)
        write_bpod_mat(filtered_data2, file2)

        # Attempt to merge using merge_bpod_sessions
        merged_data = merge_bpod_sessions([file1, file2])

        # Verify merge succeeded
        assert merged_data["SessionData"]["nTrials"] == 4
        assert len(merged_data["SessionData"]["TrialStartTimestamp"]) == 4

        # Verify trials are accessible
        trials = extract_trials(merged_data)
        assert len(trials) == 4

    def test_Should_MergeThreeFiles_When_UsingParseSession(self, sample_bpod_data, tmp_path):
        """Should successfully merge three or more Bpod files."""
        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat

        # Create filtered datasets
        filtered_data1 = index_bpod_data(sample_bpod_data, [0])
        filtered_data2 = index_bpod_data(sample_bpod_data, [1, 2])
        filtered_data3 = index_bpod_data(sample_bpod_data, [3, 4])

        # Write to files
        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_file01.mat"
        file2 = bpod_dir / "session_file02.mat"
        file3 = bpod_dir / "session_file03.mat"

        write_bpod_mat(filtered_data1, file1)
        write_bpod_mat(filtered_data2, file2)
        write_bpod_mat(filtered_data3, file3)

        # Merge all three files
        merged_data = merge_bpod_sessions([file1, file2, file3])

        # Verify merge succeeded
        assert merged_data["SessionData"]["nTrials"] == 5
        assert len(merged_data["SessionData"]["TrialStartTimestamp"]) == 5

        # Verify trials are accessible and in correct order
        trials = extract_trials(merged_data)
        assert len(trials) == 5

    def test_Should_OffsetTimestamps_When_Merging(self, sample_bpod_data, tmp_path):
        """Should correctly offset timestamps when merging multiple files."""
        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat

        # Create filtered datasets with known timestamps
        filtered_data1 = index_bpod_data(sample_bpod_data, [0, 1])
        filtered_data2 = index_bpod_data(sample_bpod_data, [2, 3])

        # Write to files
        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_file01.mat"
        file2 = bpod_dir / "session_file02.mat"

        write_bpod_mat(filtered_data1, file1)
        write_bpod_mat(filtered_data2, file2)

        # Merge files
        merged_data = merge_bpod_sessions([file1, file2])

        # Get merged timestamps
        start_times = merged_data["SessionData"]["TrialStartTimestamp"]
        end_times = merged_data["SessionData"]["TrialEndTimestamp"]

        # First file timestamps should be unchanged (trials 0, 1)
        assert start_times[0] == 0.0
        assert start_times[1] == 1.0

        # Second file timestamps should be offset by last end time of first file (1.5)
        # Original trial 2 starts at 2.0, offset by 1.5 → 3.5
        # Original trial 3 starts at 3.0, offset by 1.5 → 4.5
        assert start_times[2] == pytest.approx(3.5)
        assert start_times[3] == pytest.approx(4.5)

    def test_Should_ParseSingleFile_When_NoMergingNeeded(self, sample_bpod_data, tmp_path):
        """Should handle single file case without merging logic."""
        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat

        # Create single file
        filtered_data = index_bpod_data(sample_bpod_data, [0, 1, 2])

        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_file01.mat"

        write_bpod_mat(filtered_data, file1)

        # "Merge" single file
        merged_data = merge_bpod_sessions([file1])

        # Convert SessionData if it's a mat_struct
        from w2t_bkin.utils import convert_matlab_struct

        session_data = merged_data["SessionData"]
        if hasattr(session_data, "__dict__"):
            session_data = convert_matlab_struct(session_data)

        # Verify data is identical to original
        assert session_data["nTrials"] == 3
        assert len(session_data["TrialStartTimestamp"]) == 3

    def test_Should_SplitAndRoundtrip_When_SplittingBpodData(self, sample_bpod_data, tmp_path):
        """Should split Bpod data into multiple files and merge back with continuous timeline.

        This validates the new split_bpod_data helper for the workflow:

        - split a unified Bpod dataset into chunks
        - write each chunk as its own .mat file
        - later merge the files back with merge_bpod_sessions
        - verify that the merged timeline is continuous and preserves per-chunk ordering
        """

        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat
        from w2t_bkin.utils import convert_matlab_struct

        # Original timestamps (relative timeline)
        original_session = sample_bpod_data["SessionData"]
        original_session = convert_matlab_struct(original_session)
        original_start = np.asarray(original_session["TrialStartTimestamp"], dtype=float)
        original_end = np.asarray(original_session["TrialEndTimestamp"], dtype=float)

        # Split into two chunks: first 2 trials, then remaining trials
        split_indices = [[0, 1], [2, 3, 4]]
        chunks = split_bpod_data(sample_bpod_data, split_indices)

        assert len(chunks) == 2
        assert chunks[0]["SessionData"]["nTrials"] == 2
        assert chunks[1]["SessionData"]["nTrials"] == 3

        # Write each chunk to disk
        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_split01.mat"
        file2 = bpod_dir / "session_split02.mat"

        write_bpod_mat(chunks[0], file1)
        write_bpod_mat(chunks[1], file2)

        # Merge back into a continuous session
        merged = merge_bpod_sessions([file1, file2])
        merged_session = convert_matlab_struct(merged["SessionData"])

        # Verify trial count
        assert merged_session["nTrials"] == original_session["nTrials"]

        merged_start = np.asarray(merged_session["TrialStartTimestamp"], dtype=float)
        merged_end = np.asarray(merged_session["TrialEndTimestamp"], dtype=float)

        # Trials from the first chunk should retain their original timestamps
        np.testing.assert_allclose(merged_start[:2], original_start[:2], rtol=1e-10)
        np.testing.assert_allclose(merged_end[:2], original_end[:2], rtol=1e-10)

        # Trials from the second chunk should be offset by the last end time
        offset = original_end[1]
        expected_start_chunk2 = original_start[2:] + offset
        expected_end_chunk2 = original_end[2:] + offset

        np.testing.assert_allclose(merged_start[2:], expected_start_chunk2, rtol=1e-10)
        np.testing.assert_allclose(merged_end[2:], expected_end_chunk2, rtol=1e-10)

    def test_Should_PreservePerFileTimestamps_When_MergingWithoutContinuousTime(self, sample_bpod_data, tmp_path):
        """Should preserve per-file timestamps when merging with continuous_time=False.

        When continuous_time=False, the merge should concatenate trials without
        applying time offsets, preserving each file's original timebase.
        """
        from w2t_bkin.events import merge_bpod_sessions, write_bpod_mat
        from w2t_bkin.utils import convert_matlab_struct

        # Split into two chunks
        split_indices = [[0, 1], [2, 3, 4]]
        chunks = split_bpod_data(sample_bpod_data, split_indices)

        # Write each chunk to disk
        bpod_dir = tmp_path / "Bpod"
        bpod_dir.mkdir(parents=True)
        file1 = bpod_dir / "session_split01.mat"
        file2 = bpod_dir / "session_split02.mat"

        write_bpod_mat(chunks[0], file1)
        write_bpod_mat(chunks[1], file2)

        # Merge with continuous_time=False
        merged = merge_bpod_sessions([file1, file2], continuous_time=False)
        merged_session = convert_matlab_struct(merged["SessionData"])

        # Get original timestamps from each chunk
        chunk1_session = convert_matlab_struct(chunks[0]["SessionData"])
        chunk2_session = convert_matlab_struct(chunks[1]["SessionData"])

        chunk1_start = np.asarray(chunk1_session["TrialStartTimestamp"], dtype=float)
        chunk1_end = np.asarray(chunk1_session["TrialEndTimestamp"], dtype=float)
        chunk2_start = np.asarray(chunk2_session["TrialStartTimestamp"], dtype=float)
        chunk2_end = np.asarray(chunk2_session["TrialEndTimestamp"], dtype=float)

        merged_start = np.asarray(merged_session["TrialStartTimestamp"], dtype=float)
        merged_end = np.asarray(merged_session["TrialEndTimestamp"], dtype=float)

        # Verify timestamps are preserved exactly (no offset)
        np.testing.assert_allclose(merged_start[:2], chunk1_start, rtol=1e-10)
        np.testing.assert_allclose(merged_end[:2], chunk1_end, rtol=1e-10)
        np.testing.assert_allclose(merged_start[2:], chunk2_start, rtol=1e-10)
        np.testing.assert_allclose(merged_end[2:], chunk2_end, rtol=1e-10)
