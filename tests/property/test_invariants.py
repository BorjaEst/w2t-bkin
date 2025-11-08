"""Property-based tests for system invariants.

Validates critical invariants that must hold across all valid inputs:
- Timestamps are strictly monotonic
- Confidence values in [0, 1]
- Trials are non-overlapping
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.property


class TestTimestampInvariants:
    """Property tests for timestamp generation (Design §3.2, §19)."""

    def test_Should_BeStrictlyMonotonic_When_TimestampsGenerated_Design32(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """All generated timestamps SHALL be strictly increasing.

        Requirements: Design §3.2, §19 - Validation Checklist
        Issue: Design phase - Timestamp monotonicity invariant
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Act
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Assert - Check all timestamp files
        import pandas as pd

        for ts_file in timestamps_dir.glob("timestamps_cam*.csv"):
            df = pd.read_csv(ts_file)
            timestamps = df["timestamp"].values

            # Strictly monotonic: each value > previous value
            is_monotonic = all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))
            assert is_monotonic, f"Timestamps in {ts_file.name} must be strictly monotonic"

    def test_Should_HaveNoNegativeValues_When_TimestampsGenerated_Design32(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Timestamps SHALL be non-negative float values.

        Requirements: Design §3.2
        Issue: Design phase - Timestamp value constraints
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Act
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Assert
        import pandas as pd

        for ts_file in timestamps_dir.glob("timestamps_cam*.csv"):
            df = pd.read_csv(ts_file)
            assert (df["timestamp"] >= 0).all(), f"All timestamps in {ts_file.name} must be non-negative"

    def test_Should_MatchVideoFrameCount_When_TimestampsGenerated_Design32(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Timestamp count SHALL equal decoded frame count for each camera.

        Requirements: Design §3.2
        Issue: Design phase - Frame count consistency
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        manifest = json.loads(manifest_path.read_text())

        # Act
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Assert
        import pandas as pd

        for video_meta in manifest["videos"]:
            camera_id = video_meta["camera_id"]
            expected_frames = video_meta["frame_count"]

            ts_file = timestamps_dir / f"timestamps_cam{camera_id}.csv"
            df = pd.read_csv(ts_file)

            assert len(df) == expected_frames, f"Camera {camera_id} timestamp count must match frame count"


class TestPoseInvariants:
    """Property tests for pose data (Design §3.3, FR-5)."""

    def test_Should_HaveConfidenceInRange_When_PoseHarmonized_FR5_Design9(self, synthetic_session: Path, temp_workdir: Path):
        """All pose confidence values SHALL be in [0.0, 1.0] range.

        Requirements: FR-5, Design §9 - Property tests
        Issue: Design phase - Pose confidence bounds
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        # Create mock DLC output with confidence values
        dlc_output = synthetic_session / "pose_dlc.h5"
        # Mock creation would populate with test data

        # Act
        harmonized_pose_path = harmonize_pose(
            pose_file=dlc_output,
            format="dlc",
            output_dir=temp_workdir / "pose",
        )

        # Assert
        import pandas as pd

        pose_df = pd.read_parquet(harmonized_pose_path)
        confidence_values = pose_df["confidence"]

        assert (confidence_values >= 0.0).all(), "All confidence values must be >= 0.0"
        assert (confidence_values <= 1.0).all(), "All confidence values must be <= 1.0"

    def test_Should_HaveValidKeypoints_When_PoseHarmonized_Design33(self, synthetic_session: Path, temp_workdir: Path):
        """Harmonized pose SHALL have valid keypoint identifiers.

        Requirements: Design §3.3 - Canonical skeleton mapping
        Issue: Design phase - Keypoint validation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_output = synthetic_session / "pose_dlc.h5"

        # Act
        harmonized_pose_path = harmonize_pose(
            pose_file=dlc_output,
            format="dlc",
            output_dir=temp_workdir / "pose",
        )

        # Assert
        import pandas as pd

        pose_df = pd.read_parquet(harmonized_pose_path)
        keypoints = pose_df["keypoint"].unique()

        # Should have canonical skeleton keypoints (defined in domain model)
        assert len(keypoints) > 0, "Must have at least one keypoint"
        assert all(isinstance(kp, str) for kp in keypoints), "Keypoints must be string identifiers"

    def test_Should_HaveTimeSorted_When_PoseHarmonized_Design33(self, synthetic_session: Path, temp_workdir: Path):
        """Harmonized pose time column SHALL be sorted.

        Requirements: Design §3.3
        Issue: Design phase - Pose temporal ordering
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_output = synthetic_session / "pose_dlc.h5"

        # Act
        harmonized_pose_path = harmonize_pose(
            pose_file=dlc_output,
            format="dlc",
            output_dir=temp_workdir / "pose",
        )

        # Assert
        import pandas as pd

        pose_df = pd.read_parquet(harmonized_pose_path)
        time_values = pose_df["time"].values

        # Check sorted (allowing for repeated times across different keypoints)
        is_sorted = all(time_values[i] <= time_values[i + 1] for i in range(len(time_values) - 1))
        assert is_sorted, "Time column must be sorted"


class TestTrialsInvariants:
    """Property tests for trials and events (Design §3.5, FR-11)."""

    def test_Should_BeNonOverlapping_When_TrialsGenerated_FR11_Design9(self, synthetic_session: Path, temp_workdir: Path):
        """Derived trials SHALL never overlap in time.

        Requirements: FR-11, Design §9, §19 - Validation Checklist
        Issue: Design phase - Trial temporal integrity
        """
        # Arrange
        from w2t_bkin.events import import_events

        training_log = synthetic_session / "behavior_training.ndjson"

        # Act
        trials_path, _ = import_events(
            event_logs=[training_log],
            output_dir=temp_workdir / "events",
        )

        # Assert
        import pandas as pd

        trials_df = pd.read_csv(trials_path)
        trials_df = trials_df.sort_values("start_time")

        # Check no overlap: each trial's stop_time <= next trial's start_time
        for i in range(len(trials_df) - 1):
            current_stop = trials_df.iloc[i]["stop_time"]
            next_start = trials_df.iloc[i + 1]["start_time"]
            assert current_stop <= next_start, f"Trial {i} overlaps with trial {i+1}"

    def test_Should_HavePositiveDuration_When_TrialsGenerated_Design35(self, synthetic_session: Path, temp_workdir: Path):
        """All trials SHALL have positive duration (stop > start).

        Requirements: Design §3.5
        Issue: Design phase - Trial duration validity
        """
        # Arrange
        from w2t_bkin.events import import_events

        training_log = synthetic_session / "behavior_training.ndjson"

        # Act
        trials_path, _ = import_events(
            event_logs=[training_log],
            output_dir=temp_workdir / "events",
        )

        # Assert
        import pandas as pd

        trials_df = pd.read_csv(trials_path)
        durations = trials_df["stop_time"] - trials_df["start_time"]

        assert (durations > 0).all(), "All trials must have positive duration"

    def test_Should_HaveUniqueIDs_When_TrialsGenerated_Design35(self, synthetic_session: Path, temp_workdir: Path):
        """All trial IDs SHALL be unique.

        Requirements: Design §3.5
        Issue: Design phase - Trial ID uniqueness
        """
        # Arrange
        from w2t_bkin.events import import_events

        training_log = synthetic_session / "behavior_training.ndjson"

        # Act
        trials_path, _ = import_events(
            event_logs=[training_log],
            output_dir=temp_workdir / "events",
        )

        # Assert
        import pandas as pd

        trials_df = pd.read_csv(trials_path)
        trial_ids = trials_df["trial_id"]

        assert len(trial_ids) == len(trial_ids.unique()), "All trial IDs must be unique"


class TestManifestInvariants:
    """Property tests for manifest structure (Design §3.1, FR-12)."""

    def test_Should_HaveAbsolutePaths_When_ManifestBuilt_Design31_NFR1(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """All paths in manifest.json SHALL be absolute.

        Requirements: Design §3.1, NFR-1 (Reproducibility)
        Issue: Design phase - Manifest path invariant
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        # Act
        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Assert
        manifest = json.loads(manifest_path.read_text())

        # Check all video paths
        for video in manifest.get("videos", []):
            path = Path(video["path"])
            assert path.is_absolute(), f"Video path {path} must be absolute"

        # Check all sync paths
        for sync in manifest.get("sync", []):
            path = Path(sync["path"])
            assert path.is_absolute(), f"Sync path {path} must be absolute"

        # Check optional paths
        for pose in manifest.get("pose", []):
            path = Path(pose["path"])
            assert path.is_absolute(), f"Pose path {path} must be absolute"

    def test_Should_OmitOptionalFields_When_ResourcesNotPresent_Design31(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Optional resources SHALL be omitted (not null) when absent.

        Requirements: Design §3.1 - Invariant specification
        Issue: Design phase - Manifest optional fields
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        # Act
        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Assert
        manifest = json.loads(manifest_path.read_text())

        # If pose not present, key should be omitted or empty list (not null)
        if "pose" in manifest:
            assert manifest["pose"] is not None, "Present keys must not be null"
        # Same for facemap
        if "facemap" in manifest:
            assert manifest["facemap"] is not None, "Present keys must not be null"

    def test_Should_IncludeProvenance_When_ManifestBuilt_NFR11(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Manifest SHALL include config snapshot and provenance.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Design phase - Provenance capture
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        # Act
        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Assert
        manifest = json.loads(manifest_path.read_text())

        assert "config_snapshot" in manifest, "Manifest must include config snapshot"
        assert "provenance" in manifest, "Manifest must include provenance metadata"
        assert manifest["config_snapshot"] is not None, "Config snapshot must not be null"
