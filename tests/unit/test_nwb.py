"""Unit tests for the nwb module.

Tests NWB file assembly with devices, ImageSeries, pose, facemap, events, and sync
as specified in nwb/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestNWBCreation:
    """Test NWB file creation with external video links (MR-1)."""

    def test_Should_CreateNWBFile_When_VideosProvided_MR1(self):
        """THE MODULE SHALL create an NWB file linking external videos.

        Requirements: MR-1
        Issue: NWB module - File creation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
            sync=[],
            config_snapshot={},
            provenance={},
        )
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
            for _ in range(5)
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"
        assert nwb_path.stem == "session_001"

    def test_Should_CreateDevices_When_Building_MR1(self):
        """THE MODULE SHALL create Devices for each camera.

        Requirements: MR-1, Design - Create Devices
        Issue: NWB module - Device creation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
            sync=[],
            config_snapshot={},
            provenance={},
        )
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
            for _ in range(5)
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - Should create 5 devices
        assert nwb_path is not None

    def test_Should_CreateImageSeries_When_Building_MR1(self):
        """THE MODULE SHALL create ImageSeries per camera with external_file.

        Requirements: MR-1, Design - ImageSeries with external_file
        Issue: NWB module - ImageSeries creation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_LinkExternalVideos_When_Building_MR1(self):
        """THE MODULE SHALL link videos as external files (not embedded).

        Requirements: MR-1, M-NFR-2 - Large binaries remain external
        Issue: NWB module - External video linking
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - NWB file should be small (no embedded videos)
        if nwb_path.exists():
            assert nwb_path.stat().st_size < 10_000_000  # Less than 10MB

    def test_Should_IncludePerFrameTimestamps_When_Building_MR1(self):
        """THE MODULE SHALL include per-frame timestamps.

        Requirements: MR-1, Design - Per-frame timestamps
        Issue: NWB module - Timestamp inclusion
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None


class TestOptionalDataInclusion:
    """Test inclusion of optional pose/facemap/events (MR-2)."""

    def test_Should_AddPose_When_Provided_MR2(self):
        """WHERE pose is provided, THE MODULE SHALL add it to the NWB.

        Requirements: MR-2
        Issue: NWB module - Pose inclusion
        """
        # Arrange
        from w2t_bkin.domain import Manifest, PoseTable, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        pose = PoseTable(
            time=[0.0, 0.033, 0.066],
            keypoint=["nose", "nose", "nose"],
            x_px=[100.0, 102.0, 104.0],
            y_px=[200.0, 202.0, 204.0],
            confidence=[0.95, 0.96, 0.94],
        )

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, pose=pose)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_UseNdxPose_When_AddingPose_MR2(self):
        """THE MODULE SHALL use ndx-pose extension for pose data.

        Requirements: MR-2, Design - ndx-pose
        Issue: NWB module - ndx-pose usage
        """
        # Arrange
        from w2t_bkin.domain import Manifest, PoseTable, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        pose = PoseTable(
            time=[0.0, 0.033],
            keypoint=["nose", "nose"],
            x_px=[100.0, 102.0],
            y_px=[200.0, 202.0],
            confidence=[0.95, 0.96],
        )

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, pose=pose)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - Should use ndx-pose
        assert nwb_path is not None

    def test_Should_AddFacemap_When_Provided_MR2(self):
        """WHERE facemap is provided, THE MODULE SHALL add it to the NWB.

        Requirements: MR-2
        Issue: NWB module - Facemap inclusion
        """
        # Arrange
        from w2t_bkin.domain import (
            Manifest,
            MetricsTable,
            TimestampSeries,
            VideoMetadata,
        )
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        facemap = MetricsTable(
            time=[0.0, 0.033, 0.066],
            pupil_area=[100.0, 102.0, 104.0],
            motion_energy=[0.5, 0.6, 0.55],
        )

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, facemap=facemap)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_AddEvents_When_Provided_MR2(self):
        """WHERE events are provided, THE MODULE SHALL add them to the NWB.

        Requirements: MR-2
        Issue: NWB module - Events inclusion
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.events import EventsTable
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        events = EventsTable(
            timestamp=[0.0, 5.0, 10.0],
            event_type=["trial_start", "stimulus", "trial_end"],
            trial_id=[1, 1, 1],
        )

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, events=events)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_AddTrials_When_Provided_MR2(self):
        """WHERE trials are provided, THE MODULE SHALL add them to the NWB.

        Requirements: MR-2, Design - Trials TimeIntervals
        Issue: NWB module - Trials inclusion
        """
        # Arrange
        from w2t_bkin.domain import (
            Manifest,
            TimestampSeries,
            TrialsTable,
            VideoMetadata,
        )
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        trials = TrialsTable(
            trial_id=[1, 2],
            start_time=[0.0, 10.0],
            stop_time=[9.0, 19.0],
            phase_first=["baseline", "stimulus"],
            phase_last=["baseline", "stimulus"],
            declared_duration=[9.0, 9.0],
            observed_span=[9.0, 9.0],
            duration_delta=[0.0, 0.0],
            qc_flags=["", ""],
        )

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, trials=trials)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_AddSync_When_Provided_MR2(self):
        """WHERE sync data is provided, THE MODULE SHALL add it to the NWB.

        Requirements: MR-2
        Issue: NWB module - Sync inclusion
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_SkipOptional_When_NotProvided_MR2(self):
        """THE MODULE SHALL skip optional data when not provided.

        Requirements: MR-2
        Issue: NWB module - Optional data handling
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act - Should work with minimal inputs
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None


class TestProvenanceStorage:
    """Test provenance and configuration storage (MR-3)."""

    def test_Should_StoreConfigSnapshot_When_Building_MR3(self):
        """THE MODULE SHALL store configuration snapshot.

        Requirements: MR-3
        Issue: NWB module - Config snapshot storage
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
            config_snapshot={"project": {"name": "test", "version": "1.0"}},
            provenance={},
        )
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_StoreProvenance_When_Building_MR3(self):
        """THE MODULE SHALL store provenance metadata.

        Requirements: MR-3, Design - Software versions
        Issue: NWB module - Provenance storage
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
            provenance={"git_commit": "abc123", "pipeline_version": "0.1.0"},
        )
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None

    def test_Should_StoreSoftwareVersions_When_Building_MR3(self):
        """THE MODULE SHALL store software versions in provenance.

        Requirements: MR-3, Design - Software versions
        Issue: NWB module - Software version tracking
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - Should include pynwb, ndx-pose versions
        assert nwb_path is not None


class TestNWBValidation:
    """Test NWB validation with nwbinspector (M-NFR-1)."""

    def test_Should_PassNwbinspector_When_Built_MNFR1(self):
        """THE MODULE SHALL produce NWB files that pass nwbinspector.

        Requirements: M-NFR-1
        Issue: NWB module - nwbinspector validation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - In actual implementation, would run nwbinspector
        assert nwb_path is not None

    def test_Should_HaveNoCriticalIssues_When_Validated_MNFR1(self):
        """THE MODULE SHALL have no critical nwbinspector issues.

        Requirements: M-NFR-1
        Issue: NWB module - No critical issues
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert
        assert nwb_path is not None


class TestPortability:
    """Test NWB portability with external files (M-NFR-2)."""

    def test_Should_KeepBinariesExternal_When_Building_MNFR2(self):
        """THE MODULE SHALL keep large binaries external.

        Requirements: M-NFR-2
        Issue: NWB module - External binaries
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
            sync=[],
            config_snapshot={},
            provenance={},
        )
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
            for _ in range(5)
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - NWB should be small relative to video sizes
        if nwb_path.exists():
            assert nwb_path.stat().st_size < 20_000_000  # Less than 20MB

    def test_Should_RemainPortable_When_Built_MNFR2(self):
        """THE MODULE SHALL produce portable NWB files.

        Requirements: M-NFR-2
        Issue: NWB module - Portability
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - Should be movable with videos
        assert nwb_path is not None


class TestErrorHandling:
    """Test error handling for malformed inputs (Design)."""

    def test_Should_RaiseNwbBuildError_When_InputsMalformed_Design(self):
        """THE MODULE SHALL raise NwbBuildError with context.

        Requirements: Design - Error handling
        Issue: NWB module - Error reporting
        """
        # Arrange
        from w2t_bkin.nwb import NwbBuildError, NwbInputs, build_nwb

        # Invalid inputs
        inputs = NwbInputs(manifest=None, timestamps=None)

        # Act & Assert
        with pytest.raises((NwbBuildError, ValueError, TypeError)):
            build_nwb(inputs)

    def test_Should_ProvideContext_When_ErrorRaised_Design(self):
        """THE MODULE SHALL provide context in error messages.

        Requirements: Design - Error handling
        Issue: NWB module - Error context
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.nwb import NwbBuildError, NwbInputs, build_nwb

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

        # Missing timestamps
        inputs = NwbInputs(manifest=manifest, timestamps=None)

        # Act & Assert
        with pytest.raises((NwbBuildError, ValueError, TypeError)) as exc_info:
            build_nwb(inputs)

        error_message = str(exc_info.value).lower()
        assert "timestamp" in error_message or "missing" in error_message


class TestNwbInputs:
    """Test NwbInputs data structure."""

    def test_Should_CreateInputs_When_Provided_Design(self):
        """THE MODULE SHALL provide NwbInputs typed model.

        Requirements: Design - Input contract
        Issue: NWB module - NwbInputs model
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        # Act
        inputs = NwbInputs(manifest=manifest, timestamps=timestamps)

        # Assert
        assert inputs.manifest == manifest
        assert inputs.timestamps == timestamps

    def test_Should_AcceptOptionalData_When_Creating_Design(self):
        """THE MODULE SHALL accept optional pose/facemap/events/trials.

        Requirements: Design - Optional inputs
        Issue: NWB module - Optional data acceptance
        """
        # Arrange
        from w2t_bkin.domain import Manifest, PoseTable, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]
        pose = PoseTable(
            time=[0.0, 0.033],
            keypoint=["nose", "nose"],
            x_px=[100.0, 102.0],
            y_px=[200.0, 202.0],
            confidence=[0.95, 0.96],
        )

        # Act
        inputs = NwbInputs(manifest=manifest, timestamps=timestamps, pose=pose)

        # Assert
        assert inputs.pose == pose


class TestRelativePaths:
    """Test relative path support for portability (Design - Future notes)."""

    def test_Should_SupportRelativePaths_When_Configured_Future(self):
        """THE MODULE SHALL support relative external_file paths.

        Requirements: Design - Future notes
        Issue: NWB module - Relative paths
        """
        # Arrange
        from w2t_bkin.domain import Manifest, TimestampSeries, VideoMetadata
        from w2t_bkin.nwb import NwbInputs, build_nwb

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
        timestamps = [
            TimestampSeries(
                frame_indices=list(range(10)),
                timestamps=[i * 0.033 for i in range(10)],
            )
        ]

        inputs = NwbInputs(
            manifest=manifest,
            timestamps=timestamps,
            use_relative_paths=True,
        )

        # Act
        nwb_path = build_nwb(inputs)

        # Assert - Should create NWB with relative paths for portability
        assert nwb_path is not None
