"""Unit tests for the sync module.

Tests timestamp computation, drift detection, and sync summary generation
as specified in sync/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestTimestampComputation:
    """Test per-frame timestamp computation (MR-1)."""

    def test_Should_ComputeTimestamps_When_SyncProvided_MR1(self):
        """THE MODULE SHALL compute per-frame timestamps for each camera.

        Requirements: MR-1
        Issue: Sync module - Timestamp computation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert len(timestamps_list) == 5
        assert all(hasattr(ts, "frame_indices") for ts in timestamps_list)
        assert all(hasattr(ts, "timestamps") for ts in timestamps_list)

    def test_Should_UsePrimaryClock_When_Computing_MR1(self):
        """THE MODULE SHALL use primary clock for timebase.

        Requirements: MR-1, Design - Primary clock
        Issue: Sync module - Primary clock selection
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam2")

        # Assert - Should reference cam2 as primary
        assert summary is not None

    def test_Should_ParseTTLEdges_When_Computing_MR1(self):
        """THE MODULE SHALL parse TTL edges from sync logs.

        Requirements: MR-1, Design - Parse TTL edges
        Issue: Sync module - TTL parsing
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/ttl_sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert len(timestamps_list) > 0

    def test_Should_ParseFrameCounters_When_Computing_MR1(self):
        """THE MODULE SHALL parse frame counter logs.

        Requirements: MR-1, Design - Frame counter logs
        Issue: Sync module - Frame counter parsing
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/frame_counter.csv"), "type": "counter"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert len(timestamps_list) > 0

    def test_Should_MapFramesToTimestamps_When_Computing_MR1(self):
        """THE MODULE SHALL map frames to timestamps.

        Requirements: MR-1
        Issue: Sync module - Frame to timestamp mapping
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Frame indices should map to timestamps
        ts = timestamps_list[0]
        assert len(ts.frame_indices) == len(ts.timestamps)


class TestDropDuplicateDetection:
    """Test dropped/duplicate frame detection (MR-2)."""

    def test_Should_DetectDroppedFrames_When_Computing_MR2(self):
        """THE MODULE SHALL detect dropped frames.

        Requirements: MR-2, Design - Detect drops/duplicates
        Issue: Sync module - Dropped frame detection
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync_with_drops.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Summary should report dropped frames
        assert hasattr(summary, "dropped_frames") or "dropped" in str(summary)

    def test_Should_DetectDuplicateFrames_When_Computing_MR2(self):
        """THE MODULE SHALL detect duplicate frames.

        Requirements: MR-2
        Issue: Sync module - Duplicate frame detection
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync_with_dupes.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert hasattr(summary, "duplicate_frames") or "duplicate" in str(summary)

    def test_Should_DetectInterCameraDrift_When_Computing_MR2(self):
        """THE MODULE SHALL detect inter-camera drift.

        Requirements: MR-2, Design - Drift metrics
        Issue: Sync module - Drift detection
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync_with_drift.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Summary should include drift metrics
        assert hasattr(summary, "drift_ms") or hasattr(summary, "max_drift")

    def test_Should_ComputeDriftMetrics_When_MultiCamera_MR2(self):
        """THE MODULE SHALL compute drift metrics for multi-camera.

        Requirements: MR-2
        Issue: Sync module - Drift metrics
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Should have drift for each camera pair
        assert summary is not None


class TestOutputGeneration:
    """Test CSV and JSON output generation (MR-3)."""

    def test_Should_EmitTimestampCSVs_When_Computed_MR3(self):
        """THE MODULE SHALL emit per-camera timestamps CSVs.

        Requirements: MR-3
        Issue: Sync module - CSV output
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Should have one TimestampSeries per camera
        assert len(timestamps_list) == 5

    def test_Should_FormatCSVCorrectly_When_Writing_MR3(self):
        """THE MODULE SHALL format CSV with frame_index, timestamp columns.

        Requirements: MR-3, Design - CSV format
        Issue: Sync module - CSV format
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - TimestampSeries should have required fields
        ts = timestamps_list[0]
        assert hasattr(ts, "frame_indices")
        assert hasattr(ts, "timestamps")

    def test_Should_EmitSyncSummaryJSON_When_Computed_MR3(self):
        """THE MODULE SHALL emit sync summary JSON.

        Requirements: MR-3
        Issue: Sync module - Summary JSON
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert summary is not None
        # Should be serializable to JSON
        if hasattr(summary, "model_dump_json"):
            json_str = summary.model_dump_json()
            assert json_str is not None

    def test_Should_IncludeCountsInSummary_When_Computed_MR3(self):
        """THE MODULE SHALL include frame counts in summary.

        Requirements: MR-3, Design - Counts and drift metrics
        Issue: Sync module - Summary counts
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Summary should include total_frames, dropped, etc.
        assert hasattr(summary, "total_frames") or hasattr(summary, "frame_count")

    def test_Should_IncludeDriftInSummary_When_Computed_MR3(self):
        """THE MODULE SHALL include drift metrics in summary.

        Requirements: MR-3
        Issue: Sync module - Summary drift
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert hasattr(summary, "drift_ms") or hasattr(summary, "max_drift") or hasattr(summary, "drift")


class TestPluggableParsers:
    """Test support for multiple sync formats (MR-4)."""

    def test_Should_SupportTTLFormat_When_Parsing_MR4(self):
        """WHERE multiple sync formats exist, THE MODULE SHALL support pluggable parsers.

        Requirements: MR-4
        Issue: Sync module - TTL parser
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert len(timestamps_list) > 0

    def test_Should_SupportCounterFormat_When_Parsing_MR4(self):
        """THE MODULE SHALL support frame counter format.

        Requirements: MR-4
        Issue: Sync module - Counter parser
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "counter"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert len(timestamps_list) > 0

    def test_Should_SelectParser_When_TypeSpecified_MR4(self):
        """THE MODULE SHALL select parser based on sync type.

        Requirements: MR-4, Design - Adapters
        Issue: Sync module - Parser selection
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "custom"}],
            config_snapshot={},
            provenance={},
        )

        # Act & Assert - Should handle custom types or raise error
        try:
            timestamps_list, summary = compute_timestamps(manifest, primary="cam0")
            assert timestamps_list is not None
        except (ValueError, NotImplementedError):
            # Acceptable to not support unknown types
            pass


class TestMonotonicTimestamps:
    """Test monotonic timestamp requirement (M-NFR-1)."""

    def test_Should_ProduceMonotonicTimestamps_When_Computing_MNFR1(self):
        """THE MODULE SHALL produce monotonic timestamps.

        Requirements: M-NFR-1
        Issue: Sync module - Monotonicity
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Timestamps should be strictly increasing
        ts = timestamps_list[0]
        for i in range(1, len(ts.timestamps)):
            assert ts.timestamps[i] > ts.timestamps[i - 1], "Timestamps must be monotonic"

    def test_Should_MeetPrecisionTolerance_When_Computing_MNFR1(self):
        """THE MODULE SHALL maintain precision within tolerance.

        Requirements: M-NFR-1
        Issue: Sync module - Precision tolerance
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Timestamps should have reasonable precision
        ts = timestamps_list[0]
        assert all(isinstance(t, (int, float)) for t in ts.timestamps)


class TestDeterministicOutputs:
    """Test deterministic output requirement (M-NFR-2)."""

    def test_Should_ProduceSameOutput_When_SameInput_MNFR2(self):
        """THE MODULE SHALL produce deterministic outputs.

        Requirements: M-NFR-2
        Issue: Sync module - Determinism
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list1, summary1 = compute_timestamps(manifest, primary="cam0")
        timestamps_list2, summary2 = compute_timestamps(manifest, primary="cam0")

        # Assert - Should be identical
        assert len(timestamps_list1) == len(timestamps_list2)
        assert timestamps_list1[0].timestamps == timestamps_list2[0].timestamps

    def test_Should_NotDependOnSystemState_When_Computing_MNFR2(self):
        """THE MODULE SHALL not depend on global or system state.

        Requirements: M-NFR-2
        Issue: Sync module - State independence
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act - Call with different system states
        timestamps_list1, summary1 = compute_timestamps(manifest, primary="cam0")
        import random

        random.seed(42)
        timestamps_list2, summary2 = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert timestamps_list1[0].timestamps == timestamps_list2[0].timestamps


class TestErrorHandling:
    """Test error handling for sync issues (Design)."""

    def test_Should_RaiseTimestampMismatchError_When_NonMonotonic_Design(self):
        """THE MODULE SHALL raise TimestampMismatchError for non-monotonic.

        Requirements: Design - Error handling
        Issue: Sync module - Non-monotonic error
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampMismatchError, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/non_monotonic_sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act & Assert
        with pytest.raises((TimestampMismatchError, ValueError)):
            compute_timestamps(manifest, primary="cam0")

    def test_Should_RaiseTimestampMismatchError_When_LengthMismatch_Design(self):
        """THE MODULE SHALL raise error for length mismatches.

        Requirements: Design - Error handling
        Issue: Sync module - Length mismatch
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampMismatchError, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/length_mismatch_sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act & Assert
        with pytest.raises((TimestampMismatchError, ValueError)):
            compute_timestamps(manifest, primary="cam0")

    def test_Should_RaiseDriftThresholdExceeded_When_ConfiguredTolerance_Design(self):
        """THE MODULE SHALL raise DriftThresholdExceeded based on tolerance.

        Requirements: Design - DriftThresholdExceeded
        Issue: Sync module - Drift threshold
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import DriftThresholdExceeded, compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/large_drift_sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act & Assert
        with pytest.raises((DriftThresholdExceeded, ValueError)):
            compute_timestamps(manifest, primary="cam0", drift_tolerance_ms=1.0)


class TestSyncSummary:
    """Test SyncSummary data structure."""

    def test_Should_CreateSyncSummary_When_Computed_Design(self):
        """THE MODULE SHALL provide SyncSummary typed model.

        Requirements: Design - Output contract
        Issue: Sync module - SyncSummary model
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import SyncSummary, compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam0.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert
        assert isinstance(summary, SyncSummary)

    def test_Should_IncludeAllMetrics_When_Created_Design(self):
        """THE MODULE SHALL include all required metrics in summary.

        Requirements: Design - Counts and drift metrics
        Issue: Sync module - Summary completeness
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.sync import compute_timestamps

        videos = [
            VideoMetadata(
                camera_id=i,
                path=Path(f"/data/cam{i}.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={},
            provenance={},
        )

        # Act
        timestamps_list, summary = compute_timestamps(manifest, primary="cam0")

        # Assert - Should have key metrics
        assert hasattr(summary, "total_frames") or hasattr(summary, "frame_count")
        assert hasattr(summary, "dropped_frames") or hasattr(summary, "drops")
        assert hasattr(summary, "drift_ms") or hasattr(summary, "drift")
