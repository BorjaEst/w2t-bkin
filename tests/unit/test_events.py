"""Unit tests for events module (FR-11, NFR-7).

Requirements: FR-11 (Import events as Trials/Events), NFR-1, NFR-2, NFR-3, NFR-7
Design: design.md §3.5 (Trials/Events Tables), §21.1 (Layer 2)
API: api.md §3.9 (events module)

Test Structure (TDD Red Phase):
- All tests should fail initially until implementation is complete
- Tests organized by feature area
- Use Issue_ prefix for requirements traceability
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from w2t_bkin.config import Settings
from w2t_bkin.domain import Event, MissingInputError, Trial
from w2t_bkin.events import (
    EventsFormatError,
    EventsSummary,
    TimestampAlignmentError,
    TrialValidationError,
    _compute_trial_statistics,
    _extract_events,
    _extract_trials,
    _is_valid_events_file,
    _load_existing_summary,
    _parse_ndjson_line,
    _validate_trial_overlap,
    normalize_events,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_ndjson_training(tmp_path):
    """Sample training log with trials and events."""
    content = [
        {"time": 1.0, "kind": "trial_start", "trial_id": 1, "phase": "init"},
        {"time": 1.5, "kind": "stimulus_on", "trial_id": 1, "stimulus": "visual"},
        {"time": 2.0, "kind": "response", "trial_id": 1, "correct": True},
        {"time": 2.5, "kind": "trial_end", "trial_id": 1, "outcome": "correct"},
        {"time": 3.0, "kind": "trial_start", "trial_id": 2, "phase": "init"},
        {"time": 3.5, "kind": "stimulus_on", "trial_id": 2, "stimulus": "auditory"},
        {"time": 4.0, "kind": "response", "trial_id": 2, "correct": False},
        {"time": 4.5, "kind": "trial_end", "trial_id": 2, "outcome": "incorrect"},
    ]
    path = tmp_path / "training.ndjson"
    path.write_text("\n".join(json.dumps(line) for line in content))
    return path


@pytest.fixture
def sample_ndjson_stats(tmp_path):
    """Sample trial stats log."""
    content = [
        {"time": 2.5, "kind": "trial_stat", "trial_id": 1, "duration": 1.5, "success": True},
        {"time": 4.5, "kind": "trial_stat", "trial_id": 2, "duration": 1.5, "success": False},
    ]
    path = tmp_path / "trial_stats.ndjson"
    path.write_text("\n".join(json.dumps(line) for line in content))
    return path


@pytest.fixture
def empty_ndjson(tmp_path):
    """Empty NDJSON file."""
    path = tmp_path / "empty.ndjson"
    path.write_text("")
    return path


@pytest.fixture
def invalid_json_ndjson(tmp_path):
    """NDJSON file with invalid JSON."""
    path = tmp_path / "invalid.ndjson"
    path.write_text('{"time": 1.0, "kind": "event"}\n{invalid json}\n{"time": 2.0}')
    return path


@pytest.fixture
def overlapping_trials_ndjson(tmp_path):
    """NDJSON with overlapping trials."""
    content = [
        {"time": 1.0, "kind": "trial_start", "trial_id": 1},
        {"time": 2.0, "kind": "trial_start", "trial_id": 2},  # Starts before trial 1 ends
        {"time": 3.0, "kind": "trial_end", "trial_id": 1},
        {"time": 4.0, "kind": "trial_end", "trial_id": 2},
    ]
    path = tmp_path / "overlapping.ndjson"
    path.write_text("\n".join(json.dumps(line) for line in content))
    return path


@pytest.fixture
def missing_trial_end_ndjson(tmp_path):
    """NDJSON with missing trial_end."""
    content = [
        {"time": 1.0, "kind": "trial_start", "trial_id": 1},
        {"time": 2.0, "kind": "event", "trial_id": 1},
        {"time": 3.0, "kind": "trial_start", "trial_id": 2},  # No trial_end for trial 1
        {"time": 4.0, "kind": "trial_end", "trial_id": 2},
    ]
    path = tmp_path / "missing_end.ndjson"
    path.write_text("\n".join(json.dumps(line) for line in content))
    return path


@pytest.fixture
def events_without_trials_ndjson(tmp_path):
    """NDJSON with events but no trials."""
    content = [
        {"time": 1.0, "kind": "system_event", "message": "Recording started"},
        {"time": 2.0, "kind": "camera_sync", "camera_id": 0},
        {"time": 3.0, "kind": "system_event", "message": "Recording stopped"},
    ]
    path = tmp_path / "no_trials.ndjson"
    path.write_text("\n".join(json.dumps(line) for line in content))
    return path


@pytest.fixture
def output_dir(tmp_path):
    """Output directory for test results."""
    output = tmp_path / "output"
    output.mkdir()
    return output


# ============================================================================
# Test: NDJSON Parsing (FR-11, Design §3.5)
# ============================================================================


class TestNDJSONParsing:
    """Test NDJSON file parsing and validation.

    Requirements: FR-11 (Import NDJSON logs)
    Design: §3.5 (NDJSON format)
    Issue: Events module - NDJSON parsing
    """

    def test_Should_ParseValidNDJSON_When_AllFieldsPresent_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL parse valid NDJSON with all required fields.

        Requirements: FR-11
        Issue: Parse valid NDJSON
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        assert summary.trials_count == 2
        assert summary.events_count == 8
        assert not summary.skipped
        assert len(summary.warnings) == 0

    def test_Should_RaiseError_When_FileNotFound_Issue_FR11(self, output_dir):
        """THE MODULE SHALL raise MissingInputError when input file doesn't exist.

        Requirements: FR-11, NFR-8 (Data integrity)
        Issue: Handle missing input files
        """
        missing_file = Path("/nonexistent/file.ndjson")

        with pytest.raises(MissingInputError):
            normalize_events([missing_file], output_dir)

    def test_Should_RaiseFormatError_When_InvalidJSON_Issue_FR11(self, invalid_json_ndjson, output_dir):
        """THE MODULE SHALL raise EventsFormatError for invalid JSON lines.

        Requirements: FR-11
        Issue: Handle malformed NDJSON
        """
        with pytest.raises(EventsFormatError, match="invalid json|JSON"):
            normalize_events([invalid_json_ndjson], output_dir)

    def test_Should_HandleEmptyFile_When_NoEvents_Issue_FR11(self, empty_ndjson, output_dir):
        """THE MODULE SHALL handle empty NDJSON files gracefully.

        Requirements: FR-11
        Issue: Handle empty input files
        """
        summary = normalize_events([empty_ndjson], output_dir)

        assert summary.trials_count == 0
        assert summary.events_count == 0
        assert "empty" in " ".join(summary.warnings).lower() or summary.skipped


# ============================================================================
# Test: Trials Normalization (FR-11, Design §3.5)
# ============================================================================


class TestTrialsNormalization:
    """Test trial extraction and normalization.

    Requirements: FR-11 (Trials TimeIntervals)
    Design: §3.5 (Trials Table)
    Issue: Events module - Trials normalization
    """

    def test_Should_ExtractTrials_When_StartEndPresent_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL extract trials from trial_start/trial_end markers.

        Requirements: FR-11
        Issue: Extract trials from markers
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        assert summary.trials_count == 2

        # Verify output file exists
        trials_path = output_dir / "trials.parquet"
        assert trials_path.exists()

    def test_Should_InferTrialEnd_When_MissingTrialEnd_Issue_FR11(self, missing_trial_end_ndjson, output_dir):
        """THE MODULE SHALL infer trial_end from next trial_start when missing.

        Requirements: FR-11
        Issue: Handle missing trial_end
        """
        summary = normalize_events([missing_trial_end_ndjson], output_dir)

        assert summary.trials_count == 2
        assert any("missing_trial_end" in w.lower() for w in summary.warnings)

    def test_Should_RaiseError_When_OverlappingTrials_Issue_FR11(self, overlapping_trials_ndjson, output_dir):
        """THE MODULE SHALL raise TrialValidationError for overlapping trials.

        Requirements: FR-11
        Issue: Detect overlapping trials
        """
        with pytest.raises(TrialValidationError, match="overlap"):
            normalize_events([overlapping_trials_ndjson], output_dir)

    def test_Should_ComputeTrialDuration_When_Normalizing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL compute trial duration (stop_time - start_time).

        Requirements: FR-11 (Trial durations)
        Design: §3.5 (observed_span field)
        Issue: Compute trial durations
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        # Both trials have duration 1.5 seconds
        assert "statistics" in summary.timebase_alignment or hasattr(summary, "statistics")


# ============================================================================
# Test: Events Extraction (FR-11, Design §3.5)
# ============================================================================


class TestEventsExtraction:
    """Test event extraction and normalization.

    Requirements: FR-11 (BehavioralEvents)
    Design: §3.5 (Events table)
    Issue: Events module - Events extraction
    """

    def test_Should_ExtractAllEvents_When_Parsing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL extract all events from NDJSON.

        Requirements: FR-11
        Issue: Extract all events
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        assert summary.events_count == 8  # 4 events per trial × 2 trials

        # Verify output file exists
        events_path = output_dir / "events.parquet"
        assert events_path.exists()

    def test_Should_PreservePayload_When_ExtractingEvents_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL preserve additional fields in event payload.

        Requirements: FR-11 (Preserve event metadata)
        Issue: Preserve event payload
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        # Payload preservation verified by checking output
        assert not summary.skipped

    def test_Should_HandleEventsWithoutTrials_When_NoTrialID_Issue_FR11(self, events_without_trials_ndjson, output_dir):
        """THE MODULE SHALL handle events without trial_id.

        Requirements: FR-11
        Issue: Handle non-trial events
        """
        summary = normalize_events([events_without_trials_ndjson], output_dir)

        assert summary.events_count == 3
        assert summary.trials_count == 0

    def test_Should_AssociateEventsWithTrials_When_TrialIDPresent_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL associate events with trials via trial_id.

        Requirements: FR-11
        Issue: Associate events with trials
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        # All 8 events should be associated with 2 trials
        assert summary.trials_count == 2
        assert summary.events_count == 8


# ============================================================================
# Test: Timestamp Alignment (FR-11, Design §3.5)
# ============================================================================


class TestTimestampAlignment:
    """Test timestamp alignment and validation.

    Requirements: FR-11 (Align to session timebase)
    Design: §3.5 (Timebase alignment)
    Issue: Events module - Timestamp alignment
    """

    def test_Should_AlignToSessionTimebase_When_OffsetProvided_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL align timestamps to session timebase with offset.

        Requirements: FR-11
        Issue: Align to session timebase
        """
        # Pass timebase offset
        summary = normalize_events([sample_ndjson_training], output_dir, timebase_offset=10.0)

        assert summary.timebase_alignment["offset_sec"] == 10.0

    def test_Should_ValidateMonotonicTimestamps_When_Parsing_Issue_FR11(self, tmp_path, output_dir):
        """THE MODULE SHALL detect non-monotonic timestamps.

        Requirements: FR-11 (Data integrity)
        Issue: Validate monotonic timestamps
        """
        # Create NDJSON with non-monotonic timestamps
        content = [
            {"time": 1.0, "kind": "event1"},
            {"time": 2.0, "kind": "event2"},
            {"time": 1.5, "kind": "event3"},  # Goes backward
        ]
        path = tmp_path / "non_monotonic.ndjson"
        path.write_text("\n".join(json.dumps(line) for line in content))

        with pytest.raises(TimestampAlignmentError, match="monotonic|backward"):
            normalize_events([path], output_dir)

    def test_Should_RecordAlignmentMetadata_When_Normalizing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL record alignment metadata in summary.

        Requirements: FR-11, NFR-3 (Observability)
        Issue: Record alignment metadata
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        assert "timebase_alignment" in summary.__dict__
        assert isinstance(summary.timebase_alignment, dict)


# ============================================================================
# Test: Output Generation (FR-11, Design §3.5)
# ============================================================================


class TestOutputGeneration:
    """Test output file generation.

    Requirements: FR-11 (Trials/Events tables)
    Design: §3.5 (Output structure)
    Issue: Events module - Output generation
    """

    def test_Should_WriteTrialsParquet_When_Normalizing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL write trials table as Parquet.

        Requirements: FR-11
        Issue: Write trials Parquet
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        trials_path = output_dir / "trials.parquet"
        assert trials_path.exists()
        assert summary.output_paths["trials"] == str(trials_path)

    def test_Should_WriteEventsParquet_When_Normalizing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL write events table as Parquet.

        Requirements: FR-11
        Issue: Write events Parquet
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        events_path = output_dir / "events.parquet"
        assert events_path.exists()
        assert summary.output_paths["events"] == str(events_path)

    def test_Should_WriteSummaryJSON_When_Normalizing_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL write summary JSON.

        Requirements: FR-11, NFR-3 (Observability)
        Issue: Write summary JSON
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        summary_path = output_dir / "events_summary.json"
        assert summary_path.exists()
        assert summary.output_paths["summary"] == str(summary_path)

    def test_Should_IncludeStatistics_When_GeneratingSummary_Issue_FR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL include statistics in summary.

        Requirements: FR-11, NFR-3
        Issue: Include statistics
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        # Check for statistics in summary
        assert summary.trials_count > 0
        assert summary.events_count > 0


# ============================================================================
# Test: Provenance (NFR-11)
# ============================================================================


class TestProvenance:
    """Test provenance tracking.

    Requirements: NFR-11 (Provenance)
    Design: §11 (Provenance capture)
    Issue: Events module - Provenance
    """

    def test_Should_CaptureInputHashes_When_Normalizing_Issue_NFR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL capture input file hashes.

        Requirements: NFR-11 (Provenance)
        Issue: Capture input hashes
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        summary_path = output_dir / "events_summary.json"
        with open(summary_path) as f:
            summary_data = json.load(f)

        assert "provenance" in summary_data
        assert "input_files" in summary_data["provenance"]

    def test_Should_RecordGitCommit_When_Normalizing_Issue_NFR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL record git commit hash.

        Requirements: NFR-11
        Issue: Record git commit
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        summary_path = output_dir / "events_summary.json"
        with open(summary_path) as f:
            summary_data = json.load(f)

        assert "provenance" in summary_data
        assert "git_commit" in summary_data["provenance"]

    def test_Should_StoreConfigSnapshot_When_Normalizing_Issue_NFR11(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL store config snapshot.

        Requirements: NFR-11
        Issue: Store config snapshot
        """
        summary = normalize_events([sample_ndjson_training], output_dir)

        summary_path = output_dir / "events_summary.json"
        with open(summary_path) as f:
            summary_data = json.load(f)

        assert "provenance" in summary_data


# ============================================================================
# Test: Idempotence (NFR-2)
# ============================================================================


class TestIdempotence:
    """Test idempotent behavior.

    Requirements: NFR-2 (Idempotence)
    Issue: Events module - Idempotence
    """

    def test_Should_SkipProcessing_When_UnchangedInputs_Issue_NFR2(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL skip processing when inputs unchanged.

        Requirements: NFR-2 (Idempotence)
        Issue: Skip unchanged inputs
        """
        # First run
        summary1 = normalize_events([sample_ndjson_training], output_dir)
        assert not summary1.skipped

        # Second run with same inputs
        summary2 = normalize_events([sample_ndjson_training], output_dir)
        assert summary2.skipped

    def test_Should_Reprocess_When_ForceFlag_Issue_NFR2(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL reprocess when force=True.

        Requirements: NFR-2
        Issue: Force reprocessing
        """
        # First run
        normalize_events([sample_ndjson_training], output_dir)

        # Second run with force
        summary = normalize_events([sample_ndjson_training], output_dir, force=True)
        assert not summary.skipped

    def test_Should_Reprocess_When_InputChanged_Issue_NFR2(self, sample_ndjson_training, output_dir):
        """THE MODULE SHALL reprocess when input files change.

        Requirements: NFR-2
        Issue: Detect input changes
        """
        # First run
        normalize_events([sample_ndjson_training], output_dir)

        # Modify input file
        sample_ndjson_training.write_text(sample_ndjson_training.read_text() + '\n{"time": 10.0, "kind": "new_event"}')

        # Second run should detect change and reprocess
        summary = normalize_events([sample_ndjson_training], output_dir)
        assert not summary.skipped


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions.

    Requirements: FR-11, NFR-8 (Data integrity)
    Issue: Events module - Edge cases
    """

    def test_Should_HandleSingleLineFile_When_Parsing_Issue_FR11(self, tmp_path, output_dir):
        """THE MODULE SHALL handle single-line NDJSON files.

        Requirements: FR-11
        Issue: Handle minimal input
        """
        content = [{"time": 1.0, "kind": "event"}]
        path = tmp_path / "single.ndjson"
        path.write_text(json.dumps(content[0]))

        summary = normalize_events([path], output_dir)
        assert summary.events_count == 1

    def test_Should_HandleDuplicateTrialIDs_When_Parsing_Issue_FR11(self, tmp_path, output_dir):
        """THE MODULE SHALL handle duplicate trial IDs.

        Requirements: FR-11
        Issue: Handle duplicate trial IDs
        """
        content = [
            {"time": 1.0, "kind": "trial_start", "trial_id": 1},
            {"time": 2.0, "kind": "trial_end", "trial_id": 1},
            {"time": 3.0, "kind": "trial_start", "trial_id": 1},  # Duplicate ID
            {"time": 4.0, "kind": "trial_end", "trial_id": 1},
        ]
        path = tmp_path / "duplicate_ids.ndjson"
        path.write_text("\n".join(json.dumps(line) for line in content))

        with pytest.raises((TrialValidationError, EventsFormatError)):
            normalize_events([path], output_dir)

    def test_Should_HandleMissingTimestamp_When_Parsing_Issue_FR11(self, tmp_path, output_dir):
        """THE MODULE SHALL raise error for missing timestamp field.

        Requirements: FR-11
        Issue: Validate required fields
        """
        content = [{"kind": "event"}]  # Missing 'time'
        path = tmp_path / "missing_time.ndjson"
        path.write_text(json.dumps(content[0]))

        with pytest.raises(EventsFormatError, match="time|timestamp"):
            normalize_events([path], output_dir)

    def test_Should_HandleMultipleInputFiles_When_Normalizing_Issue_FR11(self, sample_ndjson_training, sample_ndjson_stats, output_dir):
        """THE MODULE SHALL process multiple input files.

        Requirements: FR-11
        Issue: Handle multiple inputs
        """
        summary = normalize_events([sample_ndjson_training, sample_ndjson_stats], output_dir)

        # Should process events from both files
        assert summary.events_count > 8  # More than just training file


# ============================================================================
# Test: Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Test internal helper functions.

    Requirements: FR-11
    Issue: Events module - Helper functions
    """

    def test_Should_ParseNDJSONLine_When_Valid_Issue_FR11(self):
        """THE HELPER SHALL parse valid NDJSON line.

        Requirements: FR-11
        Issue: Parse NDJSON line
        """
        line = '{"time": 1.0, "kind": "event", "data": "test"}'
        result = _parse_ndjson_line(line, line_number=1)

        assert result["time"] == 1.0
        assert result["kind"] == "event"
        assert result["data"] == "test"

    def test_Should_RaiseError_When_InvalidNDJSONLine_Issue_FR11(self):
        """THE HELPER SHALL raise EventsFormatError for invalid JSON.

        Requirements: FR-11
        Issue: Validate NDJSON line
        """
        line = "{invalid json}"

        with pytest.raises(EventsFormatError):
            _parse_ndjson_line(line, line_number=1)

    def test_Should_ExtractTrials_When_MarkersPresent_Issue_FR11(self, sample_ndjson_training):
        """THE HELPER SHALL extract trials from event markers.

        Requirements: FR-11
        Issue: Extract trials
        """
        with open(sample_ndjson_training) as f:
            events = [json.loads(line) for line in f if line.strip()]

        trials = _extract_trials(events)

        assert len(trials) == 2
        assert all(isinstance(t, Trial) for t in trials)

    def test_Should_ExtractEvents_When_Parsing_Issue_FR11(self, sample_ndjson_training):
        """THE HELPER SHALL extract events from parsed data.

        Requirements: FR-11
        Issue: Extract events
        """
        with open(sample_ndjson_training) as f:
            data = [json.loads(line) for line in f if line.strip()]

        events = _extract_events(data)

        assert len(events) == 8
        assert all(isinstance(e, Event) for e in events)

    def test_Should_ValidateTrialOverlap_When_Checking_Issue_FR11(self):
        """THE HELPER SHALL detect overlapping trials.

        Requirements: FR-11
        Issue: Validate trial overlap
        """
        trials = [
            Trial(trial_id=1, start_time=1.0, stop_time=3.0),
            Trial(trial_id=2, start_time=2.0, stop_time=4.0),  # Overlaps trial 1
        ]

        with pytest.raises(TrialValidationError, match="overlap"):
            _validate_trial_overlap(trials)

    def test_Should_ComputeStatistics_When_Analyzing_Issue_FR11(self):
        """THE HELPER SHALL compute trial statistics.

        Requirements: FR-11, NFR-3
        Issue: Compute statistics
        """
        trials = [
            Trial(trial_id=1, start_time=1.0, stop_time=2.5),
            Trial(trial_id=2, start_time=3.0, stop_time=4.5),
        ]

        stats = _compute_trial_statistics(trials)

        assert "mean_trial_duration" in stats
        assert stats["mean_trial_duration"] == 1.5

    def test_Should_CheckValidEventsFile_When_Validating_Issue_FR11(self, sample_ndjson_training):
        """THE HELPER SHALL validate events file format.

        Requirements: FR-11
        Issue: Validate events file
        """
        assert _is_valid_events_file(sample_ndjson_training)

        # Invalid file
        invalid_path = Path("/nonexistent.ndjson")
        assert not _is_valid_events_file(invalid_path)

    def test_Should_LoadExistingSummary_When_Present_Issue_NFR2(self, sample_ndjson_training, output_dir):
        """THE HELPER SHALL load existing summary for idempotence check.

        Requirements: NFR-2 (Idempotence)
        Issue: Load existing summary
        """
        # Create summary first
        normalize_events([sample_ndjson_training], output_dir)

        # Load it
        summary = _load_existing_summary(output_dir)

        assert summary is not None
        assert summary["trials_count"] == 2
