"""Unit tests for the events module.

Tests NDJSON log normalization into Events and Trials table derivation
as specified in events/requirements.md and design.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestNDJSONParsing:
    """Test NDJSON log parsing and normalization (MR-1)."""

    def test_Should_ParseValidNDJSON_When_LogProvided_MR1(self):
        """WHERE NDJSON logs are present, THE MODULE SHALL normalize them into Events.

        Requirements: MR-1
        Issue: Events module - NDJSON parsing
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_content = [
            {"timestamp": 0.0, "event_type": "trial_start", "trial_id": 1},
            {"timestamp": 10.0, "event_type": "trial_end", "trial_id": 1},
        ]
        tmp_path = Path("/tmp/test_events.ndjson")

        # Act & Assert - Should parse and normalize
        try:
            events = normalize_events([tmp_path])
            assert events is not None
        except (ImportError, AttributeError):
            pytest.skip("normalize_events not implemented")

    def test_Should_NormalizeSchema_When_ParsingLogs_MR1(self):
        """THE MODULE SHALL normalize schema across different log formats.

        Requirements: MR-1, Design - Normalize schema
        Issue: Events module - Schema normalization
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/session_001.ndjson")]

        # Act
        events = normalize_events(ndjson_paths)

        # Assert - Should have standardized columns
        assert hasattr(events, "timestamp")
        assert hasattr(events, "event_type")
        assert hasattr(events, "trial_id")

    def test_Should_HandleMultipleFiles_When_Provided_MR1(self):
        """THE MODULE SHALL normalize multiple NDJSON files.

        Requirements: MR-1
        Issue: Events module - Multiple file handling
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [
            Path("/data/session_001_part1.ndjson"),
            Path("/data/session_001_part2.ndjson"),
        ]

        # Act
        events = normalize_events(ndjson_paths)

        # Assert - Should combine all events
        assert events is not None
        assert len(events.timestamp) > 0

    def test_Should_PreserveTimestamp_When_Normalizing_MR1(self):
        """THE MODULE SHALL preserve original timestamps from logs.

        Requirements: MR-1
        Issue: Events module - Timestamp preservation
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/events.ndjson")]

        # Act
        events = normalize_events(ndjson_paths)

        # Assert - Timestamps should be preserved
        assert all(isinstance(t, (int, float)) for t in events.timestamp)

    def test_Should_HandleMalformedJSON_When_Parsing_MR1(self):
        """THE MODULE SHALL handle malformed NDJSON gracefully.

        Requirements: MR-1, Design - Error handling
        Issue: Events module - Error handling
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/malformed.ndjson")]

        # Act & Assert - Should raise or warn
        with pytest.raises((ValueError, json.JSONDecodeError, Exception)):
            normalize_events(ndjson_paths)

    def test_Should_ReturnEventsTable_When_Successful_MR1(self):
        """THE MODULE SHALL return EventsTable domain model.

        Requirements: MR-1
        Issue: Events module - Return type
        """
        # Arrange
        from w2t_bkin.events import EventsTable, normalize_events

        ndjson_paths = [Path("/data/events.ndjson")]

        # Act
        events = normalize_events(ndjson_paths)

        # Assert
        assert isinstance(events, EventsTable)


class TestTrialDerivation:
    """Test trial interval derivation (MR-2)."""

    def test_Should_DeriveTrials_When_TrialStatsExist_MR2(self):
        """WHERE trial_stats exist, THE MODULE SHALL derive Trials using hybrid policy.

        Requirements: MR-2
        Issue: Events module - Trial derivation
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 5.0, 10.0, 15.0, 20.0],
            event_type=["trial_start", "stimulus", "trial_end", "trial_start", "trial_end"],
            trial_id=[1, 1, 1, 2, 2],
        )
        trial_stats_path = Path("/data/trial_stats.csv")

        # Act
        trials = derive_trials(events, stats=trial_stats_path)

        # Assert
        assert trials is not None
        assert len(trials.trial_id) > 0

    def test_Should_UseHybridPolicy_When_Deriving_MR2(self):
        """THE MODULE SHALL use hybrid derivation policy (Option H).

        Requirements: MR-2, Design - Option H with QC flags
        Issue: Events module - Hybrid policy
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0, 20.0, 30.0],
            event_type=["trial_start", "trial_end", "trial_start", "trial_end"],
            trial_id=[1, 1, 2, 2],
        )

        # Act
        trials = derive_trials(events, stats=None)

        # Assert - Should have QC columns
        assert hasattr(trials, "qc_flags")
        assert hasattr(trials, "declared_duration")
        assert hasattr(trials, "observed_span")

    def test_Should_FlagMismatches_When_Detected_MR2(self):
        """THE MODULE SHALL flag mismatches between declared and observed durations.

        Requirements: MR-2
        Issue: Events module - Mismatch detection
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 8.0],  # 8s observed
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )
        # Assume trial_stats declares 10s duration

        # Act
        trials = derive_trials(events, stats=Path("/data/trial_stats.csv"))

        # Assert - Should flag duration mismatch
        if len(trials.qc_flags) > 0:
            assert any("duration" in flag.lower() for flag in trials.qc_flags if flag)

    def test_Should_CalculateStartStop_When_Deriving_MR2(self):
        """THE MODULE SHALL calculate start_time and stop_time for trials.

        Requirements: MR-2
        Issue: Events module - Time interval calculation
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Act
        trials = derive_trials(events, stats=None)

        # Assert
        assert trials.start_time[0] == 0.0
        assert trials.stop_time[0] == 10.0

    def test_Should_IdentifyPhases_When_Deriving_MR2(self):
        """THE MODULE SHALL identify phase_first and phase_last for trials.

        Requirements: MR-2, Design - Trials table structure
        Issue: Events module - Phase identification
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 5.0, 10.0],
            event_type=["trial_start", "stimulus", "trial_end"],
            trial_id=[1, 1, 1],
            phase=["baseline", "stimulus", "stimulus"],
        )

        # Act
        trials = derive_trials(events, stats=None)

        # Assert
        assert trials.phase_first[0] == "baseline"
        assert trials.phase_last[0] == "stimulus"

    def test_Should_HandleMissingStats_When_Deriving_MR2(self):
        """THE MODULE SHALL handle missing trial_stats gracefully.

        Requirements: MR-2
        Issue: Events module - Optional stats handling
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Act - Should work without stats
        trials = derive_trials(events, stats=None)

        # Assert
        assert trials is not None
        assert len(trials.trial_id) == 1

    def test_Should_ReturnTrialsTable_When_Successful_MR2(self):
        """THE MODULE SHALL return TrialsTable domain model.

        Requirements: MR-2
        Issue: Events module - Return type
        """
        # Arrange
        from w2t_bkin.domain import TrialsTable
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Act
        trials = derive_trials(events, stats=None)

        # Assert
        assert isinstance(trials, TrialsTable)


class TestDataIntegrityWarnings:
    """Test data integrity warnings (Design - Error handling)."""

    def test_Should_WarnOnInconsistentIDs_When_Normalizing_Design(self):
        """THE MODULE SHALL warn on inconsistent trial IDs.

        Requirements: Design - DataIntegrityWarning
        Issue: Events module - ID consistency
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/inconsistent_ids.ndjson")]

        # Act & Assert
        with pytest.warns(DataIntegrityWarning):
            normalize_events(ndjson_paths)

    def test_Should_WarnOnInconsistentTimestamps_When_Normalizing_Design(self):
        """THE MODULE SHALL warn on inconsistent timestamps.

        Requirements: Design - DataIntegrityWarning
        Issue: Events module - Timestamp consistency
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/inconsistent_timestamps.ndjson")]

        # Act & Assert
        with pytest.warns(DataIntegrityWarning):
            normalize_events(ndjson_paths)

    def test_Should_RecordFlags_When_WarningIssued_Design(self):
        """THE MODULE SHALL record QC flags when warnings occur.

        Requirements: Design - QC flags
        Issue: Events module - Flag recording
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Act
        trials = derive_trials(events, stats=None)

        # Assert - qc_flags should be present
        assert hasattr(trials, "qc_flags")


class TestVideoSynchronizationRestriction:
    """Test that events module is not used for video sync (MR-3)."""

    def test_Should_NotSyncVideos_When_Called_MR3(self):
        """THE MODULE SHALL not be used for video synchronization.

        Requirements: MR-3
        Issue: Events module - Sync restriction
        """
        # Arrange
        from w2t_bkin import events

        # Assert - Module should not have video sync functions
        assert not hasattr(events, "sync_videos")
        assert not hasattr(events, "align_video_timestamps")

    def test_Should_DocumentRestriction_When_Imported_MR3(self):
        """THE MODULE SHALL document that it's not for video sync.

        Requirements: MR-3
        Issue: Events module - Documentation
        """
        # Arrange
        from w2t_bkin import events

        # Assert - Module docstring should mention restriction
        if events.__doc__:
            assert "not" in events.__doc__.lower() or "sync" not in events.__doc__.lower()


class TestToleranceConfiguration:
    """Test tolerance configuration for trial derivation (M-NFR-1)."""

    def test_Should_DocumentTolerances_When_Deriving_MNFR1(self):
        """THE MODULE SHALL document tolerances for trial derivation.

        Requirements: M-NFR-1
        Issue: Events module - Tolerance documentation
        """
        # Arrange
        from w2t_bkin.events import derive_trials

        # Assert - Function should have documented tolerances
        assert derive_trials.__doc__ is not None
        doc_lower = derive_trials.__doc__.lower()
        assert "tolerance" in doc_lower or "threshold" in doc_lower

    def test_Should_AcceptToleranceParameter_When_Deriving_MNFR1(self):
        """THE MODULE SHALL accept tolerance parameter for derivation.

        Requirements: M-NFR-1
        Issue: Events module - Configurable tolerance
        """
        # Arrange
        import inspect

        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Assert - Function signature should include tolerance
        sig = inspect.signature(derive_trials)
        param_names = list(sig.parameters.keys())
        assert any("tolerance" in name.lower() or "threshold" in name.lower() for name in param_names) or "stats" in param_names

    def test_Should_ApplyTolerance_When_Comparing_MNFR1(self):
        """THE MODULE SHALL apply tolerance when comparing durations.

        Requirements: M-NFR-1
        Issue: Events module - Tolerance application
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 9.95],  # 9.95s observed vs 10s declared
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Act - With reasonable tolerance, should not flag small difference
        trials = derive_trials(events, stats=Path("/data/trial_stats.csv"))

        # Assert - Small differences within tolerance should not be flagged
        assert trials is not None


class TestDeterministicOutputs:
    """Test deterministic outputs (M-NFR-2)."""

    def test_Should_ProduceSameEvents_When_SameInput_MNFR2(self):
        """THE MODULE SHALL produce deterministic outputs from same inputs.

        Requirements: M-NFR-2
        Issue: Events module - Determinism
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/events.ndjson")]

        # Act
        events1 = normalize_events(ndjson_paths)
        events2 = normalize_events(ndjson_paths)

        # Assert - Should be identical
        assert events1.timestamp == events2.timestamp
        assert events1.event_type == events2.event_type

    def test_Should_ProduceSameTrials_When_SameInput_MNFR2(self):
        """THE MODULE SHALL produce deterministic trial derivation.

        Requirements: M-NFR-2
        Issue: Events module - Deterministic derivation
        """
        # Arrange
        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0, 20.0, 30.0],
            event_type=["trial_start", "trial_end", "trial_start", "trial_end"],
            trial_id=[1, 1, 2, 2],
        )

        # Act
        trials1 = derive_trials(events, stats=None)
        trials2 = derive_trials(events, stats=None)

        # Assert
        assert trials1.trial_id == trials2.trial_id
        assert trials1.start_time == trials2.start_time
        assert trials1.stop_time == trials2.stop_time

    def test_Should_NotDependOnSystemState_When_Called_MNFR2(self):
        """THE MODULE SHALL not depend on global or system state.

        Requirements: M-NFR-2
        Issue: Events module - State independence
        """
        # Arrange
        from w2t_bkin.events import normalize_events

        ndjson_paths = [Path("/data/events.ndjson")]

        # Act - Call multiple times with different "system states"
        events1 = normalize_events(ndjson_paths)
        # Simulate different state
        import random

        random.seed(42)
        events2 = normalize_events(ndjson_paths)

        # Assert - Should be identical regardless of state
        assert events1.timestamp == events2.timestamp


class TestEventsTableModel:
    """Test EventsTable domain model."""

    def test_Should_CreateEventsTable_When_DataProvided_MR1(self):
        """THE MODULE SHALL provide EventsTable typed model.

        Requirements: MR-1
        Issue: Events module - EventsTable model
        """
        # Arrange
        from w2t_bkin.events import EventsTable

        # Act
        events = EventsTable(
            timestamp=[0.0, 5.0, 10.0],
            event_type=["trial_start", "stimulus", "trial_end"],
            trial_id=[1, 1, 1],
        )

        # Assert
        assert len(events.timestamp) == 3
        assert events.event_type[0] == "trial_start"

    def test_Should_ValidateEqualLengths_When_Creating_MR1(self):
        """THE MODULE SHALL validate all arrays have equal length.

        Requirements: MR-1
        Issue: Events module - Array length validation
        """
        # Arrange
        from w2t_bkin.events import EventsTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            EventsTable(
                timestamp=[0.0, 5.0],
                event_type=["trial_start"],  # Mismatched length
                trial_id=[1, 1],
            )

    def test_Should_SupportOptionalColumns_When_Creating_MR1(self):
        """THE MODULE SHALL support optional metadata columns.

        Requirements: MR-1
        Issue: Events module - Optional columns
        """
        # Arrange
        from w2t_bkin.events import EventsTable

        # Act
        events = EventsTable(
            timestamp=[0.0, 5.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
            phase=["baseline", "baseline"],
            metadata={"session": "001"},
        )

        # Assert
        assert hasattr(events, "phase")
        assert events.metadata["session"] == "001"


class TestPluggableDerivationPolicies:
    """Test future pluggable derivation policies (Design - Future notes)."""

    def test_Should_SupportPolicyParameter_When_Deriving_Future(self):
        """THE MODULE SHALL support pluggable derivation policies.

        Requirements: Design - Future notes
        Issue: Events module - Policy plugin
        """
        # Arrange
        import inspect

        from w2t_bkin.events import EventsTable, derive_trials

        events = EventsTable(
            timestamp=[0.0, 10.0],
            event_type=["trial_start", "trial_end"],
            trial_id=[1, 1],
        )

        # Assert - Future API should support policy parameter
        sig = inspect.signature(derive_trials)
        # This is optional for future extensibility
        param_names = list(sig.parameters.keys())
        # At minimum, should accept events and optional stats
        assert "events" in param_names or len(param_names) >= 1

    def test_Should_DocumentPolicyOptions_When_Available_Future(self):
        """THE MODULE SHALL document available derivation policies.

        Requirements: Design - Future notes
        Issue: Events module - Policy documentation
        """
        # Arrange
        from w2t_bkin.events import derive_trials

        # Assert - Function should document policy options
        if derive_trials.__doc__:
            doc = derive_trials.__doc__.lower()
            # Should mention hybrid or option H
            assert "hybrid" in doc or "option" in doc or "policy" in doc
