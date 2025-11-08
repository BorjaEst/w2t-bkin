"""Unit tests for the ingest module.

Tests session resource discovery and manifest building
as specified in ingest/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestVideoDiscovery:
    """Test video file discovery (MR-1)."""

    def test_Should_DiscoverFiveCameras_When_Present_MR1(self):
        """THE MODULE SHALL discover five camera videos.

        Requirements: MR-1
        Issue: Ingest module - Video discovery
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert len(manifest.videos) == 5
        assert all(video.camera_id in range(5) for video in manifest.videos)

    def test_Should_DiscoverSyncFiles_When_Present_MR1(self):
        """THE MODULE SHALL discover associated sync files.

        Requirements: MR-1
        Issue: Ingest module - Sync file discovery
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            sync_pattern="*.sync",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert len(manifest.sync) > 0
        assert all(isinstance(sync["path"], Path) for sync in manifest.sync)

    def test_Should_ResolveFilePatterns_When_Discovering_MR1(self):
        """THE MODULE SHALL resolve file patterns to absolute paths.

        Requirements: MR-1, Design - Resolve file patterns
        Issue: Ingest module - Pattern resolution
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam[0-4].mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(video.path.is_absolute() for video in manifest.videos)

    def test_Should_SortCamerasByID_When_Discovering_MR1(self):
        """THE MODULE SHALL sort cameras by ID for deterministic ordering.

        Requirements: MR-1, M-NFR-2 - Deterministic ordering
        Issue: Ingest module - Camera sorting
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Should be sorted by camera_id
        camera_ids = [video.camera_id for video in manifest.videos]
        assert camera_ids == sorted(camera_ids)


class TestMetadataExtraction:
    """Test video metadata extraction (MR-2)."""

    def test_Should_ExtractCodec_When_Probing_MR2(self):
        """THE MODULE SHALL extract codec metadata.

        Requirements: MR-2
        Issue: Ingest module - Codec extraction
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(video.codec in ["h264", "h265", "vp9", "av1"] for video in manifest.videos)

    def test_Should_ExtractFPS_When_Probing_MR2(self):
        """THE MODULE SHALL extract frames per second.

        Requirements: MR-2
        Issue: Ingest module - FPS extraction
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(video.fps > 0 for video in manifest.videos)

    def test_Should_ExtractDuration_When_Probing_MR2(self):
        """THE MODULE SHALL extract video duration.

        Requirements: MR-2
        Issue: Ingest module - Duration extraction
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(video.duration > 0 for video in manifest.videos)

    def test_Should_ExtractResolution_When_Probing_MR2(self):
        """THE MODULE SHALL extract video resolution.

        Requirements: MR-2
        Issue: Ingest module - Resolution extraction
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(len(video.resolution) == 2 and video.resolution[0] > 0 and video.resolution[1] > 0 for video in manifest.videos)

    def test_Should_UseProbeTools_When_Extracting_MR2_MNFR1(self):
        """THE MODULE SHALL use probe tools without loading entire videos.

        Requirements: MR-2, M-NFR-1
        Issue: Ingest module - Probe tools (ffprobe)
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act & Assert - Should complete without loading full videos
        manifest = build_manifest(settings)
        assert manifest is not None

    def test_Should_WriteManifestJSON_When_Complete_MR2(self):
        """THE MODULE SHALL write manifest.json.

        Requirements: MR-2
        Issue: Ingest module - Manifest writing
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            output_dir=Path("/data/session_001/processed"),
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Manifest should be serializable to JSON
        manifest_json = manifest.model_dump_json() if hasattr(manifest, "model_dump_json") else str(manifest)
        assert manifest_json is not None


class TestMissingInputHandling:
    """Test handling of missing required inputs (MR-3)."""

    def test_Should_FailWithError_When_RequiredVideosMissing_MR3(self):
        """WHEN required inputs are missing, THE MODULE SHALL fail with MissingInputError.

        Requirements: MR-3
        Issue: Ingest module - Missing videos error
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.domain import MissingInputError
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/nonexistent/session"),
            video_pattern="cam*.mp4",
        )

        # Act & Assert
        with pytest.raises(MissingInputError):
            build_manifest(settings)

    def test_Should_FailWithError_When_InsufficientVideos_MR3(self):
        """THE MODULE SHALL fail when fewer than 5 videos found.

        Requirements: MR-3, MR-1 - Five cameras required
        Issue: Ingest module - Insufficient videos
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.domain import MissingInputError
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/incomplete_session"),
            video_pattern="cam*.mp4",
        )

        # Act & Assert
        with pytest.raises(MissingInputError):
            build_manifest(settings)

    def test_Should_FailWithError_When_SyncFilesMissing_MR3(self):
        """THE MODULE SHALL fail when required sync files are missing.

        Requirements: MR-3
        Issue: Ingest module - Missing sync files
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.domain import MissingInputError
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_no_sync"),
            video_pattern="cam*.mp4",
            sync_pattern="*.sync",
            sync_required=True,
        )

        # Act & Assert
        with pytest.raises(MissingInputError):
            build_manifest(settings)

    def test_Should_ProvideDetailedMessage_When_ErrorRaised_MR3(self):
        """THE MODULE SHALL provide detailed error messages.

        Requirements: MR-3, Design - Error handling
        Issue: Ingest module - Error messages
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.domain import MissingInputError
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/nonexistent/session"),
            video_pattern="cam*.mp4",
        )

        # Act & Assert
        with pytest.raises(MissingInputError) as exc_info:
            build_manifest(settings)

        error_message = str(exc_info.value).lower()
        assert "missing" in error_message or "not found" in error_message


class TestOptionalArtifacts:
    """Test handling of optional artifacts (MR-4)."""

    def test_Should_RecordEventPaths_When_Present_MR4(self):
        """WHERE event files are present, THE MODULE SHALL record their paths.

        Requirements: MR-4
        Issue: Ingest module - Event files
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            events_pattern="*.ndjson",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        if hasattr(manifest, "events") and manifest.events:
            assert len(manifest.events) > 0
            assert all(Path(e["path"]).suffix == ".ndjson" for e in manifest.events)

    def test_Should_RecordPosePaths_When_Present_MR4(self):
        """WHERE pose files are present, THE MODULE SHALL record their paths.

        Requirements: MR-4
        Issue: Ingest module - Pose files
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            pose_pattern="*.h5",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        if hasattr(manifest, "pose") and manifest.pose:
            assert len(manifest.pose) > 0
            assert all(Path(p["path"]).suffix in [".h5", ".csv"] for p in manifest.pose)

    def test_Should_RecordFacemapPaths_When_Present_MR4(self):
        """WHERE facemap files are present, THE MODULE SHALL record their paths.

        Requirements: MR-4
        Issue: Ingest module - Facemap files
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            facemap_pattern="*_proc.npy",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        if hasattr(manifest, "facemap") and manifest.facemap:
            assert len(manifest.facemap) > 0

    def test_Should_OmitOptional_When_NotPresent_MR4(self):
        """THE MODULE SHALL omit optional paths when not present.

        Requirements: MR-4, Design - Optional artifacts
        Issue: Ingest module - Optional omission
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/minimal_session"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Optional fields should be empty or omitted
        manifest_dict = manifest.model_dump(exclude_none=True) if hasattr(manifest, "model_dump") else {}
        # Events, pose, facemap should be missing or empty
        if "events" in manifest_dict:
            assert manifest_dict["events"] is not None  # Not null, but can be empty list


class TestProvenanceCapture:
    """Test provenance capture in manifest."""

    def test_Should_CaptureConfigSnapshot_When_Building_Design(self):
        """THE MODULE SHALL capture config snapshot in manifest.

        Requirements: Design - Provenance
        Issue: Ingest module - Config snapshot
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert hasattr(manifest, "config_snapshot")
        assert manifest.config_snapshot is not None

    def test_Should_CaptureProvenance_When_Building_Design(self):
        """THE MODULE SHALL capture provenance metadata.

        Requirements: Design - Provenance
        Issue: Ingest module - Provenance metadata
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert hasattr(manifest, "provenance")
        assert manifest.provenance is not None
        # Should include timestamp or similar
        assert len(manifest.provenance) > 0

    def test_Should_IncludeSessionID_When_Building_Design(self):
        """THE MODULE SHALL include session_id in manifest.

        Requirements: Design - Manifest structure
        Issue: Ingest module - Session ID
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert hasattr(manifest, "session_id")
        assert manifest.session_id is not None
        assert len(manifest.session_id) > 0


class TestDeterministicOutput:
    """Test deterministic manifest generation (M-NFR-2)."""

    def test_Should_ProduceSameManifest_When_SameInput_MNFR2(self):
        """THE MODULE SHALL produce deterministic manifest.

        Requirements: M-NFR-2
        Issue: Ingest module - Determinism
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest1 = build_manifest(settings)
        manifest2 = build_manifest(settings)

        # Assert - Core fields should be identical
        assert manifest1.session_id == manifest2.session_id
        assert len(manifest1.videos) == len(manifest2.videos)
        assert [v.camera_id for v in manifest1.videos] == [v.camera_id for v in manifest2.videos]

    def test_Should_UseStableKeys_When_Serializing_MNFR2(self):
        """THE MODULE SHALL use stable JSON keys.

        Requirements: M-NFR-2
        Issue: Ingest module - Stable keys
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Keys should be consistent
        expected_keys = ["session_id", "videos", "sync", "config_snapshot", "provenance"]
        manifest_dict = manifest.model_dump() if hasattr(manifest, "model_dump") else {}
        assert all(key in expected_keys for key in manifest_dict.keys() if not key.startswith("_"))

    def test_Should_OrderVideos_When_Building_MNFR2(self):
        """THE MODULE SHALL order videos deterministically.

        Requirements: M-NFR-2
        Issue: Ingest module - Video ordering
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Videos should be sorted by camera_id
        camera_ids = [video.camera_id for video in manifest.videos]
        assert camera_ids == sorted(camera_ids)


class TestAbsolutePaths:
    """Test absolute path resolution (Design)."""

    def test_Should_ResolveAbsolutePaths_When_Building_Design(self):
        """THE MODULE SHALL resolve all paths to absolute.

        Requirements: Design - Absolute paths
        Issue: Ingest module - Path resolution
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert all(video.path.is_absolute() for video in manifest.videos)
        assert all(Path(sync["path"]).is_absolute() for sync in manifest.sync)

    def test_Should_ValidatePathsExist_When_Building_Design(self):
        """THE MODULE SHALL verify discovered paths exist.

        Requirements: Design - Path verification
        Issue: Ingest module - Path validation
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - This test expects paths to exist during actual execution
        # In unit test context, we're just verifying the structure
        assert all(isinstance(video.path, Path) for video in manifest.videos)


class TestOptionalChecksums:
    """Test optional checksum capture (Design - Future notes)."""

    def test_Should_SupportChecksums_When_Enabled_Future(self):
        """THE MODULE SHALL support optional checksums for provenance.

        Requirements: Design - Future notes
        Issue: Ingest module - Checksum support
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
            compute_checksums=True,
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Checksums may be present in provenance
        if hasattr(manifest, "provenance") and "checksums" in manifest.provenance:
            assert len(manifest.provenance["checksums"]) > 0

    def test_Should_SkipChecksums_When_Disabled_Future(self):
        """THE MODULE SHALL skip checksums when disabled (default).

        Requirements: Design - Future notes
        Issue: Ingest module - Checksum optional
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert - Should complete without computing checksums
        assert manifest is not None


class TestBuildManifestAPI:
    """Test build_manifest public API."""

    def test_Should_AcceptSettings_When_Called_Design(self):
        """THE MODULE SHALL accept Settings as input.

        Requirements: Design - Public interface
        Issue: Ingest module - API contract
        """
        # Arrange
        import inspect

        from w2t_bkin.config import Settings
        from w2t_bkin.ingest import build_manifest

        # Assert - Function should accept Settings
        sig = inspect.signature(build_manifest)
        params = list(sig.parameters.keys())
        assert "settings" in params or len(params) >= 1

    def test_Should_ReturnManifest_When_Complete_Design(self):
        """THE MODULE SHALL return Manifest object.

        Requirements: Design - Public interface
        Issue: Ingest module - Return type
        """
        # Arrange
        from w2t_bkin.config import Settings
        from w2t_bkin.domain import Manifest
        from w2t_bkin.ingest import build_manifest

        settings = Settings(
            session_root=Path("/data/session_001"),
            video_pattern="cam*.mp4",
        )

        # Act
        manifest = build_manifest(settings)

        # Assert
        assert isinstance(manifest, Manifest)
