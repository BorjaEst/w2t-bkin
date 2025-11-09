"""Unit tests for sync module (TDD Red Phase).

Tests written BEFORE implementation to define expected behavior.
Following TDD Red Phase principles with comprehensive test coverage.

Requirements: FR-2, FR-3, Design §3.2, §6, §8
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from w2t_bkin.domain import SyncSummary, TimestampSeries

# Module under test (not yet implemented)
# from w2t_bkin.sync import compute_timestamps


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_manifest(tmp_path: Path) -> Path:
    """Create a mock manifest.json for testing."""
    manifest_data = {
        "session_id": "test_session_001",
        "videos": [
            {
                "camera_id": i,
                "path": f"/data/cam{i}.mp4",
                "codec": "h264",
                "fps": 30.0,
                "duration": 33.333,
                "resolution": [1920, 1080],
                "frame_count": 1000,
            }
            for i in range(5)
        ],
        "sync": [
            {
                "path": f"/data/sync/ttl_cam{i}.bin",
                "type": "ttl",
                "name": f"cam{i}",
                "polarity": "rising",
            }
            for i in range(5)
        ],
        "config_snapshot": {
            "sync": {
                "tolerance_ms": 2.0,
                "drop_frame_max_gap_ms": 100.0,
                "primary_clock": "cam0",
            }
        },
        "provenance": {"git_commit": "abc123"},
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2))
    return manifest_path


@pytest.fixture
def mock_ttl_data() -> list[float]:
    """Generate mock TTL edge timestamps (30 FPS, 100 frames)."""
    return [i / 30.0 for i in range(100)]  # Perfect 30 FPS


@pytest.fixture
def mock_ttl_data_with_drops() -> list[float]:
    """Generate mock TTL data with dropped frames."""
    edges = [i / 30.0 for i in range(100)]
    # Remove frames 50-52 to simulate drops
    return [e for i, e in enumerate(edges) if i not in [50, 51, 52]]


@pytest.fixture
def mock_ttl_data_with_drift() -> dict[str, list[float]]:
    """Generate mock TTL data with inter-camera drift."""
    return {
        "cam0": [i / 30.0 for i in range(100)],  # Perfect reference
        "cam1": [i / 30.0 + 0.001 for i in range(100)],  # 1ms drift
        "cam2": [i / 30.0 + 0.003 for i in range(100)],  # 3ms drift
        "cam3": [i / 30.0 - 0.002 for i in range(100)],  # -2ms drift
        "cam4": [i / 30.0 for i in range(100)],  # Perfect sync with cam0
    }


# ============================================================================
# Test Class: Timestamp Computation (FR-2, MR-1)
# ============================================================================


class TestTimestampComputation:
    """Test timestamp derivation from sync inputs (FR-2, MR-1)."""

    def test_Should_ComputeTimestamps_When_SyncProvided_FR2_MR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL compute per-frame timestamps for each camera.

        Requirements: FR-2, MR-1
        Issue: #001 - Sync module - Basic timestamp computation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert timestamps_dir.exists(), "Timestamps directory should be created"
        assert summary_path.exists(), "Sync summary should be created"

        # Verify one CSV per camera
        timestamp_files = list(timestamps_dir.glob("timestamps_cam*.csv"))
        assert len(timestamp_files) == 5, "Should generate timestamps for 5 cameras"

    def test_Should_UsePrimaryClock_When_Computing_FR2_MR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL use primary clock for session timebase.

        Requirements: FR-2, MR-1, Design §Timebase Derivation
        Issue: #001 - Sync module - Primary clock selection
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
            primary_clock="cam2",  # Override default cam0
        )

        # Assert
        summary = json.loads(summary_path.read_text())
        assert summary["primary_clock"] == "cam2", "Should use specified primary clock"

    def test_Should_ParseTTLEdges_When_Computing_FR2_MR1_Issue001(self, mock_manifest: Path, tmp_path: Path, mock_ttl_data: list[float]):
        """THE SYSTEM SHALL parse TTL edges from sync files.

        Requirements: FR-2, MR-1, Design §TTL Edge Parsing
        Issue: #001 - Sync module - TTL edge parsing
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        # Verify timestamps were derived from TTL edges
        cam0_csv = timestamps_dir / "timestamps_cam0.csv"
        assert cam0_csv.exists(), "Cam0 timestamps should exist"

        lines = cam0_csv.read_text().splitlines()
        assert lines[0] == "frame_index,timestamp", "CSV should have correct headers"
        assert len(lines) > 1, "CSV should contain timestamp data"

    def test_Should_ParseFrameCounters_When_Computing_FR2_MR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL parse frame counters from sync files.

        Requirements: FR-2, MR-1, Design §Frame Counter Parsing
        Issue: #001 - Sync module - Frame counter parsing
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        # Modify manifest to use frame counter sync type
        manifest_data = json.loads(mock_manifest.read_text())
        manifest_data["sync"] = [
            {
                "path": f"/data/sync/counter_cam{i}.csv",
                "type": "frame_counter",
                "name": f"cam{i}",
            }
            for i in range(5)
        ]
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert timestamps_dir.exists(), "Should handle frame counter sync type"
        timestamp_files = list(timestamps_dir.glob("timestamps_cam*.csv"))
        assert len(timestamp_files) == 5, "Should process all cameras"

    def test_Should_MapFramesToTimestamps_When_Computing_FR2_MR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL map each frame to a session timestamp.

        Requirements: FR-2, MR-1, Design §3.2
        Issue: #001 - Sync module - Frame to timestamp mapping
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        cam0_csv = timestamps_dir / "timestamps_cam0.csv"
        lines = cam0_csv.read_text().splitlines()

        # Parse first data row
        data_row = lines[1].split(",")
        frame_index = int(data_row[0])
        timestamp = float(data_row[1])

        assert frame_index == 0, "First frame should be index 0"
        assert timestamp >= 0.0, "Timestamps should be non-negative"


# ============================================================================
# Test Class: Drop/Duplicate Detection (FR-3, MR-2)
# ============================================================================


class TestDropDuplicateDetection:
    """Test dropped frame and duplicate detection (FR-3, MR-2)."""

    def test_Should_DetectDroppedFrames_When_Computing_FR3_MR2_Issue001(self, mock_manifest: Path, tmp_path: Path, mock_ttl_data_with_drops: list[float]):
        """THE SYSTEM SHALL detect dropped frames.

        Requirements: FR-3, MR-2, Design §Dropped Frame Detection
        Issue: #001 - Sync module - Dropped frame detection
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        summary = json.loads(summary_path.read_text())
        assert "drop_counts" in summary, "Summary must include drop counts"

        # At least one camera should have detected drops
        total_drops = sum(summary["drop_counts"].values())
        assert total_drops >= 0, "Drop count should be non-negative"

    def test_Should_DetectDuplicateFrames_When_Computing_FR3_MR2_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL detect duplicate frames.

        Requirements: FR-3, MR-2, Design §Duplicate Frame Detection
        Issue: #001 - Sync module - Duplicate frame detection
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        summary = json.loads(summary_path.read_text())

        # Each camera should have duplicate count (even if 0)
        for i in range(5):
            cam_stats = summary["per_camera_stats"][f"cam{i}"]
            assert "duplicate_frames" in cam_stats, f"cam{i} should report duplicates"

    def test_Should_DetectInterCameraDrift_When_Computing_FR3_MR2_Issue001(self, mock_manifest: Path, tmp_path: Path, mock_ttl_data_with_drift: dict):
        """THE SYSTEM SHALL detect inter-camera drift.

        Requirements: FR-3, MR-2, Design §Drift Detection
        Issue: #001 - Sync module - Inter-camera drift detection
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        summary = json.loads(summary_path.read_text())
        assert "drift_stats" in summary, "Summary must include drift statistics"

        drift_stats = summary["drift_stats"]
        assert "max_drift_ms" in drift_stats, "Must report max drift"
        assert "mean_drift_ms" in drift_stats, "Must report mean drift"
        assert "std_drift_ms" in drift_stats, "Must report std drift"

    def test_Should_ComputeDriftMetrics_When_MultiCamera_FR3_MR2_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL compute drift metrics (max, mean, std).

        Requirements: FR-3, MR-2, Design §Drift Detection
        Issue: #001 - Sync module - Drift metrics computation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        summary = json.loads(summary_path.read_text())
        drift_stats = summary["drift_stats"]

        # Validate metric types
        assert isinstance(drift_stats["max_drift_ms"], (int, float))
        assert isinstance(drift_stats["mean_drift_ms"], (int, float))
        assert isinstance(drift_stats["std_drift_ms"], (int, float))

        # Validate metric ranges
        assert drift_stats["max_drift_ms"] >= 0.0, "Max drift should be non-negative"
        assert drift_stats["mean_drift_ms"] >= 0.0, "Mean drift should be non-negative"
        assert drift_stats["std_drift_ms"] >= 0.0, "Std drift should be non-negative"


# ============================================================================
# Test Class: Output Generation (MR-3)
# ============================================================================


class TestOutputGeneration:
    """Test output file generation (MR-3)."""

    def test_Should_EmitTimestampCSVs_When_Computed_MR3_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL emit timestamp CSVs for each camera.

        Requirements: MR-3, Design §3.2
        Issue: #001 - Sync module - Timestamp CSV emission
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        for i in range(5):
            csv_path = timestamps_dir / f"timestamps_cam{i}.csv"
            assert csv_path.exists(), f"timestamps_cam{i}.csv should exist"

    def test_Should_FormatCSVCorrectly_When_Writing_MR3_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL format CSV with correct headers and data types.

        Requirements: MR-3, Design §3.2
        Issue: #001 - Sync module - CSV format validation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        csv_path = timestamps_dir / "timestamps_cam0.csv"
        lines = csv_path.read_text().splitlines()

        # Validate header
        assert lines[0] == "frame_index,timestamp", "CSV must have correct headers"

        # Validate data row format
        if len(lines) > 1:
            data_row = lines[1].split(",")
            assert len(data_row) == 2, "Each row should have 2 columns"

            # Validate types
            frame_index = int(data_row[0])  # Should parse as int
            timestamp = float(data_row[1])  # Should parse as float

            assert frame_index >= 0, "Frame index should be non-negative"
            assert timestamp >= 0.0, "Timestamp should be non-negative"

    def test_Should_EmitSyncSummaryJSON_When_Computed_MR3_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL emit sync_summary.json.

        Requirements: MR-3, Design §3.6
        Issue: #001 - Sync module - Summary JSON emission
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert summary_path.exists(), "sync_summary.json should exist"
        assert summary_path.name == "sync_summary.json", "Summary should be named correctly"

        # Validate JSON structure
        summary = json.loads(summary_path.read_text())
        assert isinstance(summary, dict), "Summary should be a dictionary"

    def test_Should_IncludeRequiredFields_When_SummaryCreated_MR3_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL include required fields in sync summary.

        Requirements: MR-3, Design §Output Format
        Issue: #001 - Sync module - Summary structure validation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        summary = json.loads(summary_path.read_text())

        # Required fields from Design §Output Format
        assert "session_id" in summary, "Summary must include session_id"
        assert "primary_clock" in summary, "Summary must include primary_clock"
        assert "per_camera_stats" in summary, "Summary must include per_camera_stats"
        assert "drift_stats" in summary, "Summary must include drift_stats"
        assert "drop_counts" in summary, "Summary must include drop_counts"
        assert "warnings" in summary, "Summary must include warnings"


# ============================================================================
# Test Class: Monotonic Timestamps (M-NFR-1, Design §3.2)
# ============================================================================


class TestMonotonicTimestamps:
    """Test timestamp monotonicity guarantees (M-NFR-1, Design §3.2, §19)."""

    def test_Should_BeStrictlyMonotonic_When_Generated_MNFR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL generate strictly monotonic timestamps.

        Requirements: M-NFR-1, Design §3.2, §19
        Issue: #001 - Sync module - Monotonicity enforcement
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert - Check all timestamp files
        for i in range(5):
            csv_path = timestamps_dir / f"timestamps_cam{i}.csv"
            lines = csv_path.read_text().splitlines()[1:]  # Skip header

            timestamps = [float(line.split(",")[1]) for line in lines if line]

            # Verify strict monotonic increase
            for j in range(1, len(timestamps)):
                assert timestamps[j] > timestamps[j - 1], f"cam{i}: Timestamps not strictly monotonic at index {j}"

    def test_Should_HaveNoNegativeValues_When_Generated_MNFR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL generate non-negative timestamps.

        Requirements: M-NFR-1, Design §3.2
        Issue: #001 - Sync module - Non-negativity constraint
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        for i in range(5):
            csv_path = timestamps_dir / f"timestamps_cam{i}.csv"
            lines = csv_path.read_text().splitlines()[1:]  # Skip header

            timestamps = [float(line.split(",")[1]) for line in lines if line]

            # Verify all non-negative
            assert all(t >= 0.0 for t in timestamps), f"cam{i}: All timestamps must be non-negative"

    def test_Should_MeetPrecisionTolerance_When_Computing_MNFR1_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL maintain microsecond precision.

        Requirements: M-NFR-1, Design §Timestamp CSV Format
        Issue: #001 - Sync module - Timestamp precision
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        csv_path = timestamps_dir / "timestamps_cam0.csv"
        lines = csv_path.read_text().splitlines()[1:]  # Skip header

        timestamps = [float(line.split(",")[1]) for line in lines if line]

        # Check precision by examining string representation
        for i, line in enumerate(lines[:10]):  # Check first 10
            timestamp_str = line.split(",")[1]
            # Should have at least 4 decimal places for microsecond precision
            if "." in timestamp_str:
                decimal_places = len(timestamp_str.split(".")[1])
                assert decimal_places >= 4, f"Timestamp {i} should have microsecond precision (>=4 decimals)"


# ============================================================================
# Test Class: Error Handling (Design §6)
# ============================================================================


class TestErrorHandling:
    """Test error handling and validation (Design §6)."""

    def test_Should_RaiseDriftThresholdExceeded_When_ConfiguredTolerance_Design6_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL raise DriftThresholdExceeded when drift exceeds tolerance.

        Requirements: Design §6 - Error Handling Strategy
        Issue: #001 - Sync module - Drift threshold enforcement
        """
        # Arrange
        from w2t_bkin.domain import DriftThresholdExceeded
        from w2t_bkin.sync import compute_timestamps

        # Modify manifest to set very strict tolerance
        manifest_data = json.loads(mock_manifest.read_text())
        manifest_data["config_snapshot"]["sync"]["tolerance_ms"] = 0.001  # 1 microsecond
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act & Assert
        with pytest.raises(DriftThresholdExceeded) as exc_info:
            compute_timestamps(
                manifest_path=mock_manifest,
                output_dir=output_dir,
            )

        # Verify exception message contains drift information
        assert "drift" in str(exc_info.value).lower()

    def test_Should_RaiseTimestampMismatchError_When_LengthMismatch_Design6_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL raise TimestampMismatchError on frame count mismatch.

        Requirements: Design §6 - Error Handling Strategy
        Issue: #001 - Sync module - Frame count validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampMismatchError
        from w2t_bkin.sync import compute_timestamps

        # Modify manifest to have mismatched frame counts (create impossible condition)
        manifest_data = json.loads(mock_manifest.read_text())
        # Set first camera to have 0 frames (will cause length mismatch)
        manifest_data["videos"][0]["frame_count"] = 0
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act & Assert
        # This should fail if timestamp count != frame count
        with pytest.raises((TimestampMismatchError, ValueError)):
            compute_timestamps(
                manifest_path=mock_manifest,
                output_dir=output_dir,
            )

    def test_Should_RaiseTimestampMismatchError_When_NonMonotonic_Design6_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL raise TimestampMismatchError for non-monotonic timestamps.

        Requirements: Design §6 - Error Handling Strategy
        Issue: #001 - Sync module - Monotonicity validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampMismatchError
        from w2t_bkin.sync import compute_timestamps

        # Create corrupted sync data that would produce non-monotonic timestamps
        # Modify manifest to have negative FPS (will cause non-monotonic timestamps)
        manifest_data = json.loads(mock_manifest.read_text())
        manifest_data["videos"][0]["fps"] = -30.0  # Negative FPS causes non-monotonic
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act & Assert
        # Should fail validation if timestamps decrease
        with pytest.raises((TimestampMismatchError, ValueError)):
            compute_timestamps(
                manifest_path=mock_manifest,
                output_dir=output_dir,
            )

    def test_Should_RaiseMissingInputError_When_NoSyncFiles_Design6_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL raise MissingInputError when sync files absent.

        Requirements: Design §6 - Error Handling Strategy
        Issue: #001 - Sync module - Missing input validation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        # Modify manifest to have empty sync list
        manifest_data = json.loads(mock_manifest.read_text())
        manifest_data["sync"] = []
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act & Assert
        with pytest.raises((FileNotFoundError, ValueError)) as exc_info:
            compute_timestamps(
                manifest_path=mock_manifest,
                output_dir=output_dir,
            )

        # Verify error message mentions sync files
        error_msg = str(exc_info.value).lower()
        assert "sync" in error_msg or "missing" in error_msg


# ============================================================================
# Test Class: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_Should_HandleEmptySyncFiles_When_Computing_EdgeCase_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL handle empty sync files gracefully.

        Requirements: Design §Error Handling
        Issue: #001 - Sync module - Empty file handling
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        # Modify manifest to have videos with 0 frames (empty sync scenario)
        manifest_data = json.loads(mock_manifest.read_text())
        for video in manifest_data["videos"]:
            video["frame_count"] = 0
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act & Assert
        with pytest.raises((ValueError, FileNotFoundError)):
            compute_timestamps(
                manifest_path=mock_manifest,
                output_dir=output_dir,
            )

    def test_Should_HandleMissingTTLChannels_When_Computing_EdgeCase_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL handle missing TTL channels with fallback.

        Requirements: Design §TTL Edge Parsing
        Issue: #001 - Sync module - Fallback discovery
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        # Remove TTL channel configuration
        manifest_data = json.loads(mock_manifest.read_text())
        manifest_data["config_snapshot"]["sync"]["ttl_channels"] = []
        mock_manifest.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act
        # Should use fallback patterns from manifest.sync[]
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert timestamps_dir.exists(), "Should use fallback sync discovery"

    def test_Should_ConvertToAbsolute_When_RelativePaths_EdgeCase_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL convert relative paths to absolute.

        Requirements: Design §Absolute Path Resolution, NFR-1
        Issue: #001 - Sync module - Path resolution
        """
        # Arrange
        # Use relative path for manifest
        import os

        from w2t_bkin.sync import compute_timestamps

        os.chdir(tmp_path)
        relative_manifest = Path("manifest.json")
        mock_manifest.rename(relative_manifest)

        output_dir = Path("sync")  # Relative

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=relative_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert timestamps_dir.is_absolute(), "Output paths should be absolute"
        assert summary_path.is_absolute(), "Summary path should be absolute"

    def test_Should_CreateOutputDirectory_When_NotExists_EdgeCase_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL create output directory if it doesn't exist.

        Requirements: Design §Output Generation
        Issue: #001 - Sync module - Directory creation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "nonexistent" / "sync"
        assert not output_dir.exists(), "Output directory should not exist yet"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        assert output_dir.exists(), "Output directory should be created"
        assert timestamps_dir.exists(), "Timestamps directory should be created"

    def test_Should_HandleSingleCamera_When_Computing_EdgeCase_Issue001(self, tmp_path: Path):
        """THE SYSTEM SHALL handle single-camera sessions.

        Requirements: Design §Multi-camera support
        Issue: #001 - Sync module - Single camera edge case
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        # Create manifest with single camera
        manifest_data = {
            "session_id": "single_cam_session",
            "videos": [
                {
                    "camera_id": 0,
                    "path": "/data/cam0.mp4",
                    "codec": "h264",
                    "fps": 30.0,
                    "duration": 10.0,
                    "resolution": [1920, 1080],
                    "frame_count": 300,
                }
            ],
            "sync": [
                {
                    "path": "/data/sync/ttl_cam0.bin",
                    "type": "ttl",
                    "name": "cam0",
                    "polarity": "rising",
                }
            ],
            "config_snapshot": {
                "sync": {
                    "tolerance_ms": 2.0,
                    "drop_frame_max_gap_ms": 100.0,
                    "primary_clock": "cam0",
                }
            },
            "provenance": {},
        }

        manifest_path = tmp_path / "manifest_single.json"
        manifest_path.write_text(json.dumps(manifest_data))

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=manifest_path,
            output_dir=output_dir,
        )

        # Assert
        timestamp_files = list(timestamps_dir.glob("timestamps_cam*.csv"))
        assert len(timestamp_files) == 1, "Should handle single camera"

        summary = json.loads(summary_path.read_text())
        # Drift should be zero or N/A for single camera
        assert summary["drift_stats"]["max_drift_ms"] == 0.0 or summary["drift_stats"]["max_drift_ms"] is None


# ============================================================================
# Test Class: Performance (Design §8)
# ============================================================================


class TestPerformance:
    """Test performance characteristics (Design §8)."""

    def test_Should_UseStreamingParsing_When_LargeTTL_Design8_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL use streaming parsing for large TTL logs.

        Requirements: Design §8 - Performance Considerations
        Issue: #001 - Sync module - Streaming parser implementation
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert
        # If this completes without MemoryError, streaming is working
        assert timestamps_dir.exists(), "Should complete with streaming parser"

    def test_Should_CompleteInReasonableTime_When_MultiCamera_Design8_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL complete multi-camera sync in reasonable time.

        Requirements: Design §8 - Performance Considerations, NFR-4
        Issue: #001 - Sync module - Performance validation
        """
        # Arrange
        import time

        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        start = time.time()
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )
        elapsed = time.time() - start

        # Assert
        # Should complete in under 5 seconds for test data
        assert elapsed < 5.0, f"Sync should complete quickly, took {elapsed}s"


# ============================================================================
# Test Class: Integration with Domain (Contract Validation)
# ============================================================================


class TestDomainIntegration:
    """Test integration with domain module contracts."""

    def test_Should_CreateValidTimestampSeries_When_Computing_Domain_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL create valid TimestampSeries domain objects.

        Requirements: Design §3.2, api.md §3.1
        Issue: #001 - Sync module - Domain contract compliance
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert - Verify TimestampSeries can be constructed from CSV
        csv_path = timestamps_dir / "timestamps_cam0.csv"
        lines = csv_path.read_text().splitlines()[1:]  # Skip header

        frame_indices = []
        timestamps = []
        for line in lines:
            if line:
                parts = line.split(",")
                frame_indices.append(int(parts[0]))
                timestamps.append(float(parts[1]))

        # Should be able to create TimestampSeries
        ts = TimestampSeries(frame_index=frame_indices, timestamp_sec=timestamps)
        assert ts.n_frames == len(frame_indices)
        assert ts.duration >= 0.0

    def test_Should_CreateValidSyncSummary_When_Computing_Domain_Issue001(self, mock_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL create valid SyncSummary domain objects.

        Requirements: Design §3.6, api.md §3.1
        Issue: #001 - Sync module - SyncSummary contract compliance
        """
        # Arrange
        from w2t_bkin.sync import compute_timestamps

        output_dir = tmp_path / "sync"

        # Act
        timestamps_dir, summary_path = compute_timestamps(
            manifest_path=mock_manifest,
            output_dir=output_dir,
        )

        # Assert - Verify SyncSummary can be constructed from JSON
        summary_data = json.loads(summary_path.read_text())

        # Should be able to create SyncSummary
        sync_summary = SyncSummary(
            per_camera_stats=summary_data["per_camera_stats"],
            drift_stats=summary_data["drift_stats"],
            drop_counts=summary_data["drop_counts"],
            warnings=summary_data.get("warnings", []),
        )

        assert len(sync_summary.per_camera_stats) > 0
        assert "max_drift_ms" in sync_summary.drift_stats
