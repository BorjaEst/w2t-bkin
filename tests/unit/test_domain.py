"""Unit tests for the domain module.

Tests all data contracts and domain models as specified in design.md §3 and api.md §3.1.
All tests follow TDD Red Phase principles with clear EARS requirements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# VideoMetadata Tests
# ============================================================================


class TestVideoMetadata:
    """Test VideoMetadata domain model (API §3.1)."""

    def test_Should_CreateVideoMetadata_When_ValidInputs_Issue_Domain_VideoMeta(self):
        """THE SYSTEM SHALL create VideoMetadata with valid inputs.

        Requirements: FR-1 (Ingest five camera videos)
        Design: §3.1 (Manifest JSON)
        Issue: Domain - VideoMetadata creation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act
        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/cam0.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Assert
        assert video.camera_id == 0
        assert video.path == Path("/data/cam0.mp4")
        assert video.codec == "h264"
        assert video.fps == 30.0
        assert video.duration == 60.0
        assert video.resolution == (1920, 1080)

    def test_Should_RaiseValueError_When_NegativeCameraId_Issue_Domain_VideoIdValidation(self):
        """THE SYSTEM SHALL reject negative camera_id.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - VideoMetadata camera_id validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            VideoMetadata(
                camera_id=-1,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        assert "camera_id" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_NonPositiveFPS_Issue_Domain_VideoFPSValidation(self):
        """THE SYSTEM SHALL reject non-positive fps.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - VideoMetadata fps validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=0.0,
                duration=60.0,
                resolution=(1920, 1080),
            )
        assert "fps" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_NegativeDuration_Issue_Domain_VideoDurationValidation(self):
        """THE SYSTEM SHALL reject negative duration.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - VideoMetadata duration validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=30.0,
                duration=-10.0,
                resolution=(1920, 1080),
            )
        assert "duration" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_InvalidResolution_Issue_Domain_VideoResolutionValidation(self):
        """THE SYSTEM SHALL reject invalid resolution tuples.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - VideoMetadata resolution validation
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        # Act & Assert - resolution with zero
        with pytest.raises(ValueError) as exc_info:
            VideoMetadata(
                camera_id=0,
                path=Path("/data/cam.mp4"),
                codec="h264",
                fps=30.0,
                duration=60.0,
                resolution=(0, 1080),
            )
        assert "resolution" in str(exc_info.value).lower()

    def test_Should_BeFrozen_When_Immutable_Issue_Domain_VideoImmutability(self):
        """THE SYSTEM SHALL make VideoMetadata immutable.

        Requirements: NFR-1 (Reproducibility)
        Issue: Domain - VideoMetadata immutability
        """
        # Arrange
        from w2t_bkin.domain import VideoMetadata

        video = VideoMetadata(
            camera_id=0,
            path=Path("/data/cam.mp4"),
            codec="h264",
            fps=30.0,
            duration=60.0,
            resolution=(1920, 1080),
        )

        # Act & Assert
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            video.camera_id = 1


# ============================================================================
# Manifest Tests
# ============================================================================


class TestManifest:
    """Test Manifest domain model (API §3.1)."""

    def test_Should_CreateManifest_When_ValidInputs_Issue_Domain_ManifestCreation(self):
        """THE SYSTEM SHALL create Manifest with valid inputs.

        Requirements: FR-1 (Ingest assets), NFR-1 (Reproducibility)
        Design: §3.1 (Manifest JSON)
        Issue: Domain - Manifest creation
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
        sync = [{"path": "/data/sync_ttl.csv", "type": "ttl"}]

        # Act
        manifest = Manifest(
            session_id="test_001",
            videos=videos,
            sync=sync,
        )

        # Assert
        assert manifest.session_id == "test_001"
        assert len(manifest.videos) == 5
        assert len(manifest.sync) == 1

    def test_Should_RaiseValueError_When_EmptySessionId_Issue_Domain_ManifestSessionValidation(self):
        """THE SYSTEM SHALL reject empty session_id.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - Manifest session_id validation
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
        sync = [{"path": "/data/sync.csv", "type": "ttl"}]

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Manifest(session_id="", videos=videos, sync=sync)
        assert "session_id" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_EmptyVideosList_Issue_Domain_ManifestVideosValidation(self):
        """THE SYSTEM SHALL reject empty videos list.

        Requirements: FR-1 (Ingest five camera videos)
        Issue: Domain - Manifest videos validation
        """
        # Arrange
        from w2t_bkin.domain import Manifest

        sync = [{"path": "/data/sync.csv", "type": "ttl"}]

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Manifest(session_id="test_001", videos=[], sync=sync)
        assert "videos" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_EmptySyncList_Issue_Domain_ManifestSyncValidation(self):
        """THE SYSTEM SHALL reject empty sync list.

        Requirements: FR-2 (Hardware sync inputs required)
        Issue: Domain - Manifest sync validation
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

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Manifest(session_id="test_001", videos=videos, sync=[])
        assert "sync" in str(exc_info.value).lower()

    def test_Should_AllowOptionalFields_When_NotProvided_Issue_Domain_ManifestOptionals(self):
        """THE SYSTEM SHALL allow optional fields (pose, facemap, events).

        Requirements: NFR-7 (Modularity - optional stages)
        Issue: Domain - Manifest optional fields
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
        sync = [{"path": "/data/sync.csv", "type": "ttl"}]

        # Act
        manifest = Manifest(session_id="test_001", videos=videos, sync=sync)

        # Assert
        assert manifest.events == []
        assert manifest.pose == []
        assert manifest.facemap == []


# ============================================================================
# TimestampSeries Tests
# ============================================================================


class TestTimestampSeries:
    """Test TimestampSeries domain model (API §3.1)."""

    def test_Should_CreateTimestampSeries_When_ValidInputs_Issue_Domain_TimestampCreation(self):
        """THE SYSTEM SHALL create TimestampSeries with monotonic timestamps.

        Requirements: FR-2 (Compute per-frame timestamps)
        Design: §3.2 (Timestamp CSV - monotonic increase)
        Issue: Domain - TimestampSeries creation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        # Act
        ts = TimestampSeries(
            frame_index=[0, 1, 2, 3],
            timestamp_sec=[0.0, 0.0333, 0.0666, 0.1000],
        )

        # Assert
        assert ts.n_frames == 4
        assert ts.duration == pytest.approx(0.1000, abs=1e-6)

    def test_Should_RaiseValueError_When_LengthMismatch_Issue_Domain_TimestampLengthValidation(self):
        """THE SYSTEM SHALL reject mismatched frame_index and timestamp_sec lengths.

        Requirements: Design §3.2 (Timestamp CSV)
        Issue: Domain - TimestampSeries length validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            TimestampSeries(
                frame_index=[0, 1, 2],
                timestamp_sec=[0.0, 0.0333],
            )
        assert "equal length" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_Empty_Issue_Domain_TimestampEmptyValidation(self):
        """THE SYSTEM SHALL reject empty TimestampSeries.

        Requirements: Design §3.2 (Timestamp CSV)
        Issue: Domain - TimestampSeries empty validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            TimestampSeries(frame_index=[], timestamp_sec=[])
        assert "empty" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_NonMonotonic_Issue_Domain_TimestampMonotonicValidation(self):
        """THE SYSTEM SHALL reject non-monotonic timestamps.

        Requirements: Design §3.2 (Timestamp CSV - strict monotonic increase)
        Issue: Domain - TimestampSeries monotonic validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            TimestampSeries(
                frame_index=[0, 1, 2, 3],
                timestamp_sec=[0.0, 0.0333, 0.0333, 0.1000],  # Duplicate at index 2
            )
        assert "monotonic" in str(exc_info.value).lower()

    def test_Should_ComputeDuration_When_ValidSeries_Issue_Domain_TimestampDuration(self):
        """THE SYSTEM SHALL compute duration correctly.

        Requirements: FR-2 (Timestamps in common session timebase)
        Issue: Domain - TimestampSeries duration property
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries

        ts = TimestampSeries(
            frame_index=[0, 1, 2],
            timestamp_sec=[10.0, 10.5, 11.0],
        )

        # Act
        duration = ts.duration

        # Assert
        assert duration == pytest.approx(1.0, abs=1e-6)


# ============================================================================
# SyncSummary Tests
# ============================================================================


class TestSyncSummary:
    """Test SyncSummary domain model (API §3.1)."""

    def test_Should_CreateSyncSummary_When_ValidInputs_Issue_Domain_SyncSummaryCreation(self):
        """THE SYSTEM SHALL create SyncSummary with camera stats and drift.

        Requirements: FR-3 (Detect drops/duplicates/drift)
        Design: §3.6 (QC Summary JSON)
        Issue: Domain - SyncSummary creation
        """
        # Arrange
        from w2t_bkin.domain import SyncSummary

        # Act
        summary = SyncSummary(
            per_camera_stats={"cam0": {"n_frames": 300}, "cam1": {"n_frames": 298}},
            drift_stats={"max": 1.5, "mean": 0.3, "std": 0.5},
            drop_counts={"cam0": 0, "cam1": 2},
        )

        # Assert
        assert len(summary.per_camera_stats) == 2
        assert summary.drift_stats["max"] == 1.5
        assert summary.drop_counts["cam1"] == 2

    def test_Should_RaiseValueError_When_EmptyCameraStats_Issue_Domain_SyncSummaryValidation(self):
        """THE SYSTEM SHALL reject empty per_camera_stats.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - SyncSummary validation
        """
        # Arrange
        from w2t_bkin.domain import SyncSummary

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            SyncSummary(
                per_camera_stats={},
                drift_stats={},
                drop_counts={},
            )
        assert "per_camera_stats" in str(exc_info.value).lower()

    def test_Should_AllowWarnings_When_Provided_Issue_Domain_SyncSummaryWarnings(self):
        """THE SYSTEM SHALL support optional warnings list.

        Requirements: FR-3 (Report drift/drops with summary)
        Issue: Domain - SyncSummary warnings
        """
        # Arrange
        from w2t_bkin.domain import SyncSummary

        # Act
        summary = SyncSummary(
            per_camera_stats={"cam0": {"n_frames": 300}},
            drift_stats={},
            drop_counts={},
            warnings=["Drift exceeded threshold on cam1"],
        )

        # Assert
        assert len(summary.warnings) == 1
        assert "Drift" in summary.warnings[0]


# ============================================================================
# PoseSample & PoseTable Tests
# ============================================================================


class TestPoseSample:
    """Test PoseSample domain model (API §3.1)."""

    def test_Should_CreatePoseSample_When_ValidInputs_Issue_Domain_PoseSampleCreation(self):
        """THE SYSTEM SHALL create PoseSample with confidence in [0,1].

        Requirements: FR-5 (Import pose with confidence scores)
        Design: §3.3 (Pose Harmonized Table)
        Issue: Domain - PoseSample creation
        """
        # Arrange
        from w2t_bkin.domain import PoseSample

        # Act
        sample = PoseSample(
            time=1.0,
            keypoint="nose",
            x_px=320.5,
            y_px=240.2,
            confidence=0.95,
        )

        # Assert
        assert sample.time == 1.0
        assert sample.keypoint == "nose"
        assert sample.confidence == 0.95

    def test_Should_RaiseValueError_When_ConfidenceOutOfRange_Issue_Domain_PoseSampleConfidenceValidation(self):
        """THE SYSTEM SHALL reject confidence outside [0,1].

        Requirements: Design §3.3 (Pose confidence in [0,1])
        Issue: Domain - PoseSample confidence validation
        """
        # Arrange
        from w2t_bkin.domain import PoseSample

        # Act & Assert - confidence > 1
        with pytest.raises(ValueError) as exc_info:
            PoseSample(time=1.0, keypoint="nose", x_px=320.0, y_px=240.0, confidence=1.5)
        assert "confidence" in str(exc_info.value).lower()

        # Act & Assert - confidence < 0
        with pytest.raises(ValueError):
            PoseSample(time=1.0, keypoint="nose", x_px=320.0, y_px=240.0, confidence=-0.1)

    def test_Should_RaiseValueError_When_EmptyKeypoint_Issue_Domain_PoseSampleKeypointValidation(self):
        """THE SYSTEM SHALL reject empty keypoint name.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - PoseSample keypoint validation
        """
        # Arrange
        from w2t_bkin.domain import PoseSample

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PoseSample(time=1.0, keypoint="", x_px=320.0, y_px=240.0, confidence=0.9)
        assert "keypoint" in str(exc_info.value).lower()


class TestPoseTable:
    """Test PoseTable domain model (API §3.1)."""

    def test_Should_CreatePoseTable_When_ValidRecords_Issue_Domain_PoseTableCreation(self):
        """THE SYSTEM SHALL create PoseTable from pose samples.

        Requirements: FR-5 (Harmonize pose outputs)
        Design: §3.3 (Pose Harmonized Table)
        Issue: Domain - PoseTable creation
        """
        # Arrange
        from w2t_bkin.domain import PoseSample, PoseTable

        records = [
            PoseSample(time=1.0, keypoint="nose", x_px=320.0, y_px=240.0, confidence=0.95),
            PoseSample(time=1.0, keypoint="left_ear", x_px=310.0, y_px=230.0, confidence=0.90),
        ]

        # Act
        table = PoseTable(records=records, skeleton_meta={"model": "dlc"})

        # Assert
        assert table.n_samples == 2
        assert table.keypoints == {"nose", "left_ear"}
        assert table.skeleton_meta["model"] == "dlc"

    def test_Should_RaiseValueError_When_EmptyRecords_Issue_Domain_PoseTableValidation(self):
        """THE SYSTEM SHALL reject empty pose records.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - PoseTable validation
        """
        # Arrange
        from w2t_bkin.domain import PoseTable

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PoseTable(records=[])
        assert "empty" in str(exc_info.value).lower()

    def test_Should_ComputeKeypoints_When_MultipleRecords_Issue_Domain_PoseTableKeypoints(self):
        """THE SYSTEM SHALL extract unique keypoint names.

        Requirements: FR-5 (Canonical skeleton mapping)
        Issue: Domain - PoseTable keypoints property
        """
        # Arrange
        from w2t_bkin.domain import PoseSample, PoseTable

        records = [
            PoseSample(time=1.0, keypoint="nose", x_px=320.0, y_px=240.0, confidence=0.95),
            PoseSample(time=1.5, keypoint="nose", x_px=321.0, y_px=241.0, confidence=0.93),
            PoseSample(time=1.0, keypoint="tail", x_px=400.0, y_px=300.0, confidence=0.85),
        ]

        # Act
        table = PoseTable(records=records)

        # Assert
        assert table.keypoints == {"nose", "tail"}
        assert table.n_samples == 3


# ============================================================================
# FacemapMetrics Tests
# ============================================================================


class TestFacemapMetrics:
    """Test FacemapMetrics domain model (API §3.1)."""

    def test_Should_CreateFacemapMetrics_When_ValidInputs_Issue_Domain_FacemapCreation(self):
        """THE SYSTEM SHALL create FacemapMetrics with aligned time series.

        Requirements: FR-6 (Import/compute facial metrics)
        Design: §3.4 (Facemap Metrics)
        Issue: Domain - FacemapMetrics creation
        """
        # Arrange
        from w2t_bkin.domain import FacemapMetrics

        # Act
        metrics = FacemapMetrics(
            time=[0.0, 0.033, 0.066],
            metric_columns={
                "pupil_area": [100.0, 105.0, 102.0],
                "motion_energy": [0.5, 0.6, 0.55],
            },
        )

        # Assert
        assert metrics.n_samples == 3
        assert metrics.metrics == ["pupil_area", "motion_energy"]

    def test_Should_RaiseValueError_When_EmptyTime_Issue_Domain_FacemapTimeValidation(self):
        """THE SYSTEM SHALL reject empty time series.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - FacemapMetrics time validation
        """
        # Arrange
        from w2t_bkin.domain import FacemapMetrics

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            FacemapMetrics(time=[], metric_columns={})
        assert "time" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_LengthMismatch_Issue_Domain_FacemapLengthValidation(self):
        """THE SYSTEM SHALL reject metric columns with mismatched lengths.

        Requirements: Design §3.4 (Facemap Metrics)
        Issue: Domain - FacemapMetrics length validation
        """
        # Arrange
        from w2t_bkin.domain import FacemapMetrics

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            FacemapMetrics(
                time=[0.0, 0.033, 0.066],
                metric_columns={
                    "pupil_area": [100.0, 105.0],  # Only 2 values
                },
            )
        assert "length" in str(exc_info.value).lower() or "metric" in str(exc_info.value).lower()


# ============================================================================
# Event & Trial Tests
# ============================================================================


class TestEvent:
    """Test Event domain model (API §3.1)."""

    def test_Should_CreateEvent_When_ValidInputs_Issue_Domain_EventCreation(self):
        """THE SYSTEM SHALL create Event with time and kind.

        Requirements: FR-11 (Import events as BehavioralEvents)
        Design: §3.5 (Events table)
        Issue: Domain - Event creation
        """
        # Arrange
        from w2t_bkin.domain import Event

        # Act
        event = Event(time=5.0, kind="reward", payload={"amount": 1})

        # Assert
        assert event.time == 5.0
        assert event.kind == "reward"
        assert event.payload["amount"] == 1

    def test_Should_RaiseValueError_When_EmptyKind_Issue_Domain_EventKindValidation(self):
        """THE SYSTEM SHALL reject empty event kind.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - Event kind validation
        """
        # Arrange
        from w2t_bkin.domain import Event

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Event(time=5.0, kind="")
        assert "kind" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_NegativeTime_Issue_Domain_EventTimeValidation(self):
        """THE SYSTEM SHALL reject negative event time.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - Event time validation
        """
        # Arrange
        from w2t_bkin.domain import Event

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Event(time=-1.0, kind="start")
        assert "time" in str(exc_info.value).lower()


class TestTrial:
    """Test Trial domain model (API §3.1)."""

    def test_Should_CreateTrial_When_ValidInputs_Issue_Domain_TrialCreation(self):
        """THE SYSTEM SHALL create Trial with valid time interval.

        Requirements: FR-11 (Import events as Trials TimeIntervals)
        Design: §3.5 (Trials Table)
        Issue: Domain - Trial creation
        """
        # Arrange
        from w2t_bkin.domain import Trial

        # Act
        trial = Trial(
            trial_id=1,
            start_time=10.0,
            stop_time=15.0,
            phase_first="baseline",
            phase_last="stimulus",
        )

        # Assert
        assert trial.trial_id == 1
        assert trial.duration == pytest.approx(5.0, abs=1e-6)

    def test_Should_RaiseValueError_When_StopBeforeStart_Issue_Domain_TrialTimeValidation(self):
        """THE SYSTEM SHALL reject stop_time <= start_time.

        Requirements: Design §3.5 (Trials non-overlapping)
        Issue: Domain - Trial time validation
        """
        # Arrange
        from w2t_bkin.domain import Trial

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Trial(trial_id=1, start_time=10.0, stop_time=9.0)
        assert "stop_time" in str(exc_info.value).lower()

    def test_Should_RaiseValueError_When_NegativeStartTime_Issue_Domain_TrialStartValidation(self):
        """THE SYSTEM SHALL reject negative start_time.

        Requirements: Design §4.3 (Error handling)
        Issue: Domain - Trial start_time validation
        """
        # Arrange
        from w2t_bkin.domain import Trial

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Trial(trial_id=1, start_time=-1.0, stop_time=5.0)
        assert "start_time" in str(exc_info.value).lower()

    def test_Should_ComputeDuration_When_ValidTimes_Issue_Domain_TrialDuration(self):
        """THE SYSTEM SHALL compute trial duration correctly.

        Requirements: Design §3.5 (Trials Table - observed_span)
        Issue: Domain - Trial duration property
        """
        # Arrange
        from w2t_bkin.domain import Trial

        trial = Trial(trial_id=1, start_time=2.5, stop_time=7.8)

        # Act
        duration = trial.duration

        # Assert
        assert duration == pytest.approx(5.3, abs=1e-6)


# ============================================================================
# NWBAssemblyOptions Tests
# ============================================================================


class TestNWBAssemblyOptions:
    """Test NWBAssemblyOptions domain model (API §3.1)."""

    def test_Should_CreateNWBOptions_When_Defaults_Issue_Domain_NWBOptionsCreation(self):
        """THE SYSTEM SHALL create NWBAssemblyOptions with defaults.

        Requirements: FR-7 (Export NWB), FR-10 (Configuration-driven)
        Issue: Domain - NWBAssemblyOptions creation
        """
        # Arrange
        from w2t_bkin.domain import NWBAssemblyOptions

        # Act
        options = NWBAssemblyOptions()

        # Assert
        assert options.link_external_video is True
        assert options.file_name == ""

    def test_Should_CreateNWBOptions_When_CustomValues_Issue_Domain_NWBOptionsCustom(self):
        """THE SYSTEM SHALL accept custom NWB assembly options.

        Requirements: FR-10 (Configuration-driven)
        Issue: Domain - NWBAssemblyOptions custom values
        """
        # Arrange
        from w2t_bkin.domain import NWBAssemblyOptions

        # Act
        options = NWBAssemblyOptions(
            link_external_video=False,
            file_name="custom_session.nwb",
            session_description="Custom session",
            lab="Test Lab",
            institution="Test University",
        )

        # Assert
        assert options.link_external_video is False
        assert options.file_name == "custom_session.nwb"
        assert options.lab == "Test Lab"


# ============================================================================
# QCReportSummary Tests
# ============================================================================


class TestQCReportSummary:
    """Test QCReportSummary domain model (API §3.1)."""

    def test_Should_CreateQCReportSummary_When_Defaults_Issue_Domain_QCReportCreation(self):
        """THE SYSTEM SHALL create QCReportSummary with optional sections.

        Requirements: FR-8 (Generate QC HTML report)
        Design: §3.6 (QC Summary JSON)
        Issue: Domain - QCReportSummary creation
        """
        # Arrange
        from w2t_bkin.domain import QCReportSummary

        # Act
        summary = QCReportSummary()

        # Assert
        assert summary.has_pose is False
        assert summary.has_facemap is False

    def test_Should_DetectPosePresence_When_PoseOverviewProvided_Issue_Domain_QCReportPoseDetection(self):
        """THE SYSTEM SHALL detect pose data presence.

        Requirements: NFR-7 (Optional stages)
        Issue: Domain - QCReportSummary pose detection
        """
        # Arrange
        from w2t_bkin.domain import QCReportSummary

        # Act
        summary = QCReportSummary(pose_overview={"n_keypoints": 10})

        # Assert
        assert summary.has_pose is True

    def test_Should_DetectFacemapPresence_When_FacemapOverviewProvided_Issue_Domain_QCReportFacemapDetection(self):
        """THE SYSTEM SHALL detect facemap data presence.

        Requirements: NFR-7 (Optional stages)
        Issue: Domain - QCReportSummary facemap detection
        """
        # Arrange
        from w2t_bkin.domain import QCReportSummary

        # Act
        summary = QCReportSummary(facemap_overview={"n_metrics": 2})

        # Assert
        assert summary.has_facemap is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestDomainIntegration:
    """Integration tests combining multiple domain models."""

    def test_Should_CreateCompleteManifest_When_AllComponents_Issue_Domain_Integration(self):
        """THE SYSTEM SHALL support complete manifest with all optional components.

        Requirements: FR-1 through FR-11 (Full pipeline)
        Issue: Domain - Integration workflow
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
        sync = [{"path": "/data/sync_ttl.csv", "type": "ttl"}]
        pose = [{"path": "/data/pose_dlc.h5", "format": "dlc"}]
        facemap = [{"path": "/data/facemap_metrics.npy"}]
        events = [{"path": "/data/events.ndjson", "kind": "ndjson"}]

        # Act
        manifest = Manifest(
            session_id="test_full_001",
            videos=videos,
            sync=sync,
            pose=pose,
            facemap=facemap,
            events=events,
            config_snapshot={"n_cameras": 5},
            provenance={"git_commit": "abc1234"},
        )

        # Assert
        assert len(manifest.videos) == 5
        assert len(manifest.pose) == 1
        assert len(manifest.facemap) == 1
        assert len(manifest.events) == 1
        assert manifest.provenance["git_commit"] == "abc1234"
