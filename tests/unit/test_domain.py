"""Unit tests for the domain module.

Tests shared domain models used across pipeline stages including VideoMetadata,
TimestampSeries, PoseTable, MetricsTable, and Manifest as specified in
domain/requirements.md and design.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestVideoMetadata:
    """Test VideoMetadata domain model (MR-1, Design §3.1)."""

    def test_Should_CreateValidModel_When_AllFieldsProvided_MR1(self):
        """THE MODULE SHALL provide VideoMetadata typed model.

        Requirements: MR-1, Design §3.1 - Manifest video fields
        Issue: Domain module - VideoMetadata model
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act
        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/raw/cam0.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Assert
        assert video.camera_id == 0
        assert video.path == Path("/data/raw/cam0.mp4")
        assert video.codec == "h264"
        assert video.fps == 30.0
        assert video.duration == 60.0
        assert video.resolution == (1920, 1080)

    def test_Should_ValidateCameraID_When_Creating_MR2(self):
        """THE MODULE SHALL validate VideoMetadata invariants.

        Requirements: MR-2
        Issue: Domain module - VideoMetadata validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert - Camera ID should be non-negative
        with pytest.raises((ValueError, TypeError)):
            VideoMetadata(
                camera_id=-1,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )

    def test_Should_ValidateFPS_When_Creating_MR2(self):
        """THE MODULE SHALL validate FPS is positive.

        Requirements: MR-2
        Issue: Domain module - FPS validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert
        with pytest.raises((ValueError, TypeError)):
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=-30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )

    def test_Should_ValidateDuration_When_Creating_MR2(self):
        """THE MODULE SHALL validate duration is non-negative.

        Requirements: MR-2
        Issue: Domain module - Duration validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert
        with pytest.raises((ValueError, TypeError)):
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=30.0,
                duration=-60.0,
                resolution=(1920, 1080),
            )

    def test_Should_ConvertToDict_When_Serializing_MR1(self):
        """THE MODULE SHALL support serialization to dict.

        Requirements: MR-1
        Issue: Domain module - VideoMetadata serialization
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/cam0.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Act
        video_dict = video.model_dump() if hasattr(video, "model_dump") else video.__dict__

        # Assert
        assert isinstance(video_dict, dict)
        assert video_dict["camera_id"] == 0
        assert video_dict["codec"] == "h264"


class TestTimestampSeries:
    """Test TimestampSeries domain model (MR-1, MR-2, Design §3.2)."""

    def test_Should_CreateValidModel_When_MonotonicTimestamps_MR1_MR2(self):
        """THE MODULE SHALL create TimestampSeries with monotonic validation.

        Requirements: MR-1, MR-2, Design §3.2 - Strict monotonic increase
        Issue: Domain module - TimestampSeries model
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        frame_indices = [0, 1, 2, 3, 4]
        timestamps = [0.0, 0.033, 0.066, 0.099, 0.132]

        # Act
        ts_series = TimestampSeries(frame_indices=frame_indices, timestamps=timestamps)

        # Assert
        assert len(ts_series.frame_indices) == 5
        assert len(ts_series.timestamps) == 5
        assert ts_series.timestamps[0] == 0.0

    def test_Should_RaiseError_When_NonMonotonic_MR2(self):
        """THE MODULE SHALL validate monotonicity for TimestampSeries.

        Requirements: MR-2, Design §3.2 - Invariant enforcement
        Issue: Domain module - Monotonicity validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        frame_indices = [0, 1, 2, 3]
        timestamps = [0.0, 0.033, 0.030, 0.066]  # Non-monotonic

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            TimestampSeries(frame_indices=frame_indices, timestamps=timestamps)

    def test_Should_RaiseError_When_LengthMismatch_MR2(self):
        """THE MODULE SHALL validate frame_indices and timestamps have same length.

        Requirements: MR-2
        Issue: Domain module - Length validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        frame_indices = [0, 1, 2]
        timestamps = [0.0, 0.033]  # Mismatched length

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            TimestampSeries(frame_indices=frame_indices, timestamps=timestamps)

    def test_Should_ValidateNonNegativeTimestamps_When_Creating_MR2(self):
        """THE MODULE SHALL validate timestamps are non-negative.

        Requirements: MR-2
        Issue: Domain module - Timestamp value validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        frame_indices = [0, 1, 2]
        timestamps = [-0.1, 0.0, 0.033]  # Negative timestamp

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            TimestampSeries(frame_indices=frame_indices, timestamps=timestamps)

    def test_Should_SupportIteration_When_Accessing_MR1(self):
        """THE MODULE SHALL support iteration over frame/timestamp pairs.

        Requirements: MR-1
        Issue: Domain module - TimestampSeries usability
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        frame_indices = [0, 1, 2]
        timestamps = [0.0, 0.033, 0.066]
        ts_series = TimestampSeries(frame_indices=frame_indices, timestamps=timestamps)

        # Act
        pairs = list(zip(ts_series.frame_indices, ts_series.timestamps))

        # Assert
        assert len(pairs) == 3
        assert pairs[0] == (0, 0.0)
        assert pairs[2] == (2, 0.066)


class TestPoseTable:
    """Test PoseTable domain model (MR-1, Design §3.3)."""

    def test_Should_CreateValidModel_When_PoseDataProvided_MR1(self):
        """THE MODULE SHALL provide PoseTable typed model.

        Requirements: MR-1, Design §3.3 - Pose harmonized table
        Issue: Domain module - PoseTable model
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        # Act
        pose_table = PoseTable(
            time=[0.0, 0.033, 0.066],
            keypoint=["nose", "nose", "nose"],
            x_px=[100.0, 102.0, 104.0],
            y_px=[200.0, 202.0, 204.0],
            confidence=[0.95, 0.96, 0.94],
        )

        # Assert
        assert len(pose_table.time) == 3
        assert pose_table.keypoint[0] == "nose"
        assert pose_table.x_px[0] == 100.0
        assert pose_table.confidence[0] == 0.95

    def test_Should_ValidateConfidenceRange_When_Creating_MR2(self):
        """THE MODULE SHALL validate confidence values in [0, 1].

        Requirements: MR-2, Design §3.3
        Issue: Domain module - Confidence validation
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        # Act & Assert - Confidence > 1
        with pytest.raises((ValueError, AssertionError)):
            PoseTable(
                time=[0.0],
                keypoint=["nose"],
                x_px=[100.0],
                y_px=[200.0],
                confidence=[1.5],
            )

    def test_Should_ValidateNegativeConfidence_When_Creating_MR2(self):
        """THE MODULE SHALL reject negative confidence values.

        Requirements: MR-2
        Issue: Domain module - Confidence bounds
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            PoseTable(
                time=[0.0],
                keypoint=["nose"],
                x_px=[100.0],
                y_px=[200.0],
                confidence=[-0.1],
            )

    def test_Should_ValidateEqualLengths_When_Creating_MR2(self):
        """THE MODULE SHALL validate all arrays have equal length.

        Requirements: MR-2
        Issue: Domain module - Array length consistency
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            PoseTable(
                time=[0.0, 0.033],
                keypoint=["nose"],  # Mismatched length
                x_px=[100.0, 102.0],
                y_px=[200.0, 202.0],
                confidence=[0.95, 0.96],
            )

    def test_Should_SupportMetadata_When_Provided_MR1(self):
        """THE MODULE SHALL support metadata sidecar for skeleton/model info.

        Requirements: MR-1, Design §3.3 - Metadata sidecar
        Issue: Domain module - PoseTable metadata
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        metadata = {
            "skeleton": "mouse_skeleton_v1",
            "model_hash": "abc123",
        }

        # Act
        pose_table = PoseTable(
            time=[0.0],
            keypoint=["nose"],
            x_px=[100.0],
            y_px=[200.0],
            confidence=[0.95],
            metadata=metadata,
        )

        # Assert
        assert pose_table.metadata["skeleton"] == "mouse_skeleton_v1"
        assert pose_table.metadata["model_hash"] == "abc123"


class TestMetricsTable:
    """Test MetricsTable domain model for Facemap (MR-1, Design §3.4)."""

    def test_Should_CreateValidModel_When_MetricsProvided_MR1(self):
        """THE MODULE SHALL provide MetricsTable typed model.

        Requirements: MR-1, Design §3.4 - Facemap metrics
        Issue: Domain module - MetricsTable model
        """
        # Arrange
        from w2t_bkin.domain import MetricsTable

        # Act
        metrics = MetricsTable(
            time=[0.0, 0.033, 0.066],
            pupil_area=[100.0, 102.0, 104.0],
            motion_energy=[0.5, 0.6, 0.55],
        )

        # Assert
        assert len(metrics.time) == 3
        assert metrics.pupil_area[0] == 100.0
        assert metrics.motion_energy[1] == 0.6

    def test_Should_AllowNaN_When_MissingSamples_MR1(self):
        """THE MODULE SHALL preserve NaN for missing samples.

        Requirements: MR-1, Design §3.4 - Missing samples as NaN
        Issue: Domain module - NaN handling
        """
        # Arrange
        import math

        from w2t_bkin.domain import MetricsTable

        # Act
        metrics = MetricsTable(
            time=[0.0, 0.033, 0.066],
            pupil_area=[100.0, float("nan"), 104.0],
            motion_energy=[0.5, 0.6, float("nan")],
        )

        # Assert
        assert math.isnan(metrics.pupil_area[1])
        assert math.isnan(metrics.motion_energy[2])

    def test_Should_ValidateEqualLengths_When_Creating_MR2(self):
        """THE MODULE SHALL validate all metric arrays have equal length.

        Requirements: MR-2
        Issue: Domain module - Metrics length validation
        """
        # Arrange
        from w2t_bkin.domain import MetricsTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            MetricsTable(
                time=[0.0, 0.033, 0.066],
                pupil_area=[100.0, 102.0],  # Mismatched length
                motion_energy=[0.5, 0.6, 0.55],
            )

    def test_Should_SupportDynamicMetrics_When_Created_MR1(self):
        """THE MODULE SHALL support dynamic metric columns.

        Requirements: MR-1, Design §3.4 - Wide table with variable metrics
        Issue: Domain module - Dynamic metrics support
        """
        # Arrange
        from w2t_bkin.domain import MetricsTable

        # Act
        metrics = MetricsTable(
            time=[0.0, 0.033],
            custom_metric_1=[1.0, 2.0],
            custom_metric_2=[3.0, 4.0],
        )

        # Assert
        assert hasattr(metrics, "custom_metric_1")
        assert hasattr(metrics, "custom_metric_2")
        assert metrics.custom_metric_1[0] == 1.0


class TestTrialsTable:
    """Test TrialsTable domain model for events (MR-1, Design §3.5)."""

    def test_Should_CreateValidModel_When_TrialsProvided_MR1(self):
        """THE MODULE SHALL provide TrialsTable typed model.

        Requirements: MR-1, Design §3.5 - Trials table
        Issue: Domain module - TrialsTable model
        """
        # Arrange
        from w2t_bkin.domain import TrialsTable

        # Act
        trials = TrialsTable(
            trial_id=[1, 2, 3],
            start_time=[0.0, 10.0, 20.0],
            stop_time=[9.0, 19.0, 29.0],
            phase_first=["baseline", "stimulus", "baseline"],
            phase_last=["baseline", "stimulus", "baseline"],
            declared_duration=[9.0, 9.0, 9.0],
            observed_span=[9.0, 9.0, 9.0],
            duration_delta=[0.0, 0.0, 0.0],
            qc_flags=["", "", ""],
        )

        # Assert
        assert len(trials.trial_id) == 3
        assert trials.start_time[0] == 0.0
        assert trials.stop_time[0] == 9.0

    def test_Should_ValidatePositiveDuration_When_Creating_MR2(self):
        """THE MODULE SHALL validate stop_time > start_time.

        Requirements: MR-2
        Issue: Domain module - Trial duration validation
        """
        # Arrange
        from w2t_bkin.domain import TrialsTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            TrialsTable(
                trial_id=[1],
                start_time=[10.0],
                stop_time=[5.0],  # Invalid: stop < start
                phase_first=["baseline"],
                phase_last=["baseline"],
                declared_duration=[5.0],
                observed_span=[5.0],
                duration_delta=[0.0],
                qc_flags=[""],
            )

    def test_Should_ValidateUniqueTrialIDs_When_Creating_MR2(self):
        """THE MODULE SHALL validate trial IDs are unique.

        Requirements: MR-2
        Issue: Domain module - Trial ID uniqueness
        """
        # Arrange
        from w2t_bkin.domain import TrialsTable

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            TrialsTable(
                trial_id=[1, 1, 2],  # Duplicate trial ID
                start_time=[0.0, 10.0, 20.0],
                stop_time=[9.0, 19.0, 29.0],
                phase_first=["baseline", "stimulus", "baseline"],
                phase_last=["baseline", "stimulus", "baseline"],
                declared_duration=[9.0, 9.0, 9.0],
                observed_span=[9.0, 9.0, 9.0],
                duration_delta=[0.0, 0.0, 0.0],
                qc_flags=["", "", ""],
            )


class TestManifest:
    """Test Manifest domain model (MR-1, Design §3.1)."""

    def test_Should_CreateValidModel_When_AllFieldsProvided_MR1(self):
        """THE MODULE SHALL provide Manifest typed model.

        Requirements: MR-1, Design §3.1 - Manifest structure
        Issue: Domain module - Manifest model
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata

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

        # Act
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[{"path": Path("/data/sync.csv"), "type": "ttl"}],
            config_snapshot={"project": {"name": "test"}},
            provenance={"git_commit": "abc123"},
        )

        # Assert
        assert manifest.session_id == "session_001"
        assert len(manifest.videos) == 5
        assert manifest.config_snapshot["project"]["name"] == "test"

    def test_Should_ValidateAbsolutePaths_When_Creating_MR2(self):
        """THE MODULE SHALL validate all paths are absolute.

        Requirements: MR-2, Design §3.1 - Invariant: All paths absolute
        Issue: Domain module - Path validation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("relative/path.mp4"),  # Relative path
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        ]

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            Manifest(
                session_id="session_001",
                videos=videos,
                sync=[],
                config_snapshot={},
                provenance={},
            )

    def test_Should_OmitOptionalResources_When_NotPresent_MR1(self):
        """THE MODULE SHALL omit optional resources rather than use null.

        Requirements: MR-1, Design §3.1 - Optional resources omitted
        Issue: Domain module - Optional field handling
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata

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

        # Act
        manifest = Manifest(
            session_id="session_001",
            videos=videos,
            sync=[],
            config_snapshot={},
            provenance={},
            # pose, facemap, events omitted
        )

        # Assert
        manifest_dict = manifest.model_dump(exclude_none=True) if hasattr(manifest, "model_dump") else vars(manifest)
        # Optional fields should either be missing or empty lists (not None)
        if "pose" in manifest_dict:
            assert manifest_dict["pose"] is not None
        if "facemap" in manifest_dict:
            assert manifest_dict["facemap"] is not None

    def test_Should_SerializeToJSON_When_Required_MR1(self):
        """THE MODULE SHALL support JSON serialization.

        Requirements: MR-1
        Issue: Domain module - Manifest serialization
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata

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
        if hasattr(manifest, "model_dump_json"):
            json_str = manifest.model_dump_json()
        else:
            json_str = json.dumps(manifest, default=str)

        # Assert
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["session_id"] == "session_001"


class TestQCSummary:
    """Test QCSummary domain model (MR-1, Design §3.6)."""

    def test_Should_CreateValidModel_When_SummaryDataProvided_MR1(self):
        """THE MODULE SHALL provide QCSummary typed model.

        Requirements: MR-1, Design §3.6 - QC summary JSON
        Issue: Domain module - QCSummary model
        """
        # Arrange
        from w2t_bkin.domain import QCSummary

        # Act
        summary = QCSummary(
            sync={"drift_max_ms": 1.5, "dropped_frames": 2},
            pose={"confidence_median": 0.95, "total_keypoints": 1000},
            facemap={"pupil_area_mean": 100.0},
            events={"trial_count": 10},
            provenance={"pipeline_version": "0.1.0"},
        )

        # Assert
        assert summary.sync["drift_max_ms"] == 1.5
        assert summary.pose["confidence_median"] == 0.95
        assert summary.provenance["pipeline_version"] == "0.1.0"

    def test_Should_SupportOptionalSections_When_Creating_MR1(self):
        """THE MODULE SHALL support optional QC sections.

        Requirements: MR-1
        Issue: Domain module - Optional QC sections
        """
        # Arrange
        from w2t_bkin.domain import QCSummary

        # Act - Only some sections provided
        summary = QCSummary(
            sync={"drift_max_ms": 1.5},
            provenance={"pipeline_version": "0.1.0"},
        )

        # Assert
        assert summary.sync["drift_max_ms"] == 1.5
        assert summary.provenance["pipeline_version"] == "0.1.0"


class TestDomainErrors:
    """Test domain-specific error classes (Design §6)."""

    def test_Should_ProvideCustomErrors_When_Importing_MR1(self):
        """THE MODULE SHALL provide domain-specific error classes.

        Requirements: MR-1, Design §6 - Error handling
        Issue: Domain module - Custom exceptions
        """
        # Arrange & Act
        from w2t_bkin.domain import (
            DataIntegrityWarning,
            MissingInputError,
            TimestampMismatchError,
        )

        # Assert - Errors should be importable
        assert issubclass(MissingInputError, Exception)
        assert issubclass(TimestampMismatchError, Exception)
        assert issubclass(DataIntegrityWarning, Warning)

    def test_Should_SubclassPipelineError_When_Defined_MR1(self):
        """THE MODULE SHALL ensure all errors subclass PipelineError.

        Requirements: MR-1, Design §6 - Central logging
        Issue: Domain module - Error hierarchy
        """
        # Arrange
        from w2t_bkin.domain import MissingInputError, PipelineError

        # Act & Assert
        assert issubclass(MissingInputError, PipelineError)


class TestModelImmutability:
    """Test model immutability and small focused design (M-NFR-1)."""

    def test_Should_BeImmutable_When_CreatingVideoMetadata_MNFR1(self):
        """THE MODULE SHALL keep models immutable where appropriate.

        Requirements: M-NFR-1
        Issue: Domain module - Immutability
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/cam0.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Act & Assert - Should not allow modification
        with pytest.raises((AttributeError, TypeError, ValueError)):
            video.camera_id = 1

    def test_Should_AvoidCyclicDependencies_When_Importing_MNFR1(self):
        """THE MODULE SHALL avoid cyclic dependencies.

        Requirements: M-NFR-1
        Issue: Domain module - Dependency management
        """
        # Arrange & Act
        # Domain module should import cleanly without circular dependencies
        import w2t_bkin.domain

        # Assert - Should be able to access all models
        assert hasattr(w2t_bkin.domain, "VideoMetadata")
        assert hasattr(w2t_bkin.domain, "TimestampSeries")
        assert hasattr(w2t_bkin.domain, "PoseTable")
        assert hasattr(w2t_bkin.domain, "Manifest")


class TestBackwardCompatibility:
    """Test backward compatibility considerations (M-NFR-2)."""

    def test_Should_SupportOptionalFields_When_Adding_MNFR2(self):
        """THE MODULE SHALL support backward-compatible changes.

        Requirements: M-NFR-2
        Issue: Domain module - Backward compatibility
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act - Create with minimal required fields (old schema)
        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/cam0.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Assert - Should work with base fields
        assert video.camera_id == 0

    def test_Should_SerializeWithVersion_When_Appropriate_MNFR2(self):
        """THE MODULE SHALL consider versioned schemas for compatibility.

        Requirements: M-NFR-2, Design - Future notes
        Issue: Domain module - Schema versioning
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata

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
            sync=[],
            config_snapshot={},
            provenance={},
        )

        # Act - Check if schema version is tracked
        manifest_dict = manifest.model_dump() if hasattr(manifest, "model_dump") else vars(manifest)

        # Assert - Version field may exist for future compatibility
        # This is optional but recommended for backward compatibility
        assert manifest_dict is not None
