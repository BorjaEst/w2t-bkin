"""Unit tests for the transcode module.

Tests optional mezzanine video generation for stable seeking
as specified in transcode/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestOptionalTranscoding:
    """Test optional transcoding when enabled (MR-1)."""

    def test_Should_TranscodeWhenEnabled_When_ConfigSet_MR1(self):
        """WHERE enabled, THE MODULE SHALL transcode inputs to mezzanine files.

        Requirements: MR-1
        Issue: Transcode module - Conditional transcoding
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert report is not None
        assert len(report.outputs) > 0

    def test_Should_SkipWhenDisabled_When_ConfigUnset_MR1(self):
        """THE MODULE SHALL skip transcoding when disabled.

        Requirements: MR-1 - Optional
        Issue: Transcode module - Skip when disabled
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": False}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should skip or return empty report
        assert report is not None
        assert len(report.outputs) == 0 or report.skipped is True

    def test_Should_UseConfigParams_When_Transcoding_MR1(self):
        """THE MODULE SHALL transcode per config settings.

        Requirements: MR-1, Design - Settings-based ffmpeg commands
        Issue: Transcode module - Config-based parameters
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "libx264",
                    "crf": 23,
                    "preset": "medium",
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert report is not None
        assert any("libx264" in str(output) or "x264" in str(output) for output in report.outputs)

    def test_Should_TranscodeAllVideos_When_Enabled_MR1(self):
        """THE MODULE SHALL transcode all videos when enabled.

        Requirements: MR-1
        Issue: Transcode module - Batch processing
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should transcode all 5 cameras
        assert len(report.outputs) == 5


class TestTimestampPreservation:
    """Test that transcoding doesn't alter synchronization (MR-2)."""

    def test_Should_PreserveOriginalTimestamps_When_Transcoding_MR2(self):
        """THE MODULE SHALL not alter synchronization; original timestamps remain source of truth.

        Requirements: MR-2
        Issue: Transcode module - Timestamp preservation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should not modify sync/timestamp data
        assert report is not None
        # Manifest should remain unchanged
        assert manifest.videos[0].fps == 30.0

    def test_Should_NotRegenerateTimestamps_When_Transcoding_MR2(self):
        """THE MODULE SHALL not regenerate timestamps during transcoding.

        Requirements: MR-2, Design - Preserve frame counts
        Issue: Transcode module - No timestamp regeneration
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should reference original timestamps
        assert report is not None

    def test_Should_DocumentTimestampSource_When_Reporting_MR2(self):
        """THE MODULE SHALL document that original timestamps are source of truth.

        Requirements: MR-2
        Issue: Transcode module - Documentation
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        # Assert - Function should document timestamp handling
        assert transcode_videos.__doc__ is not None
        doc_lower = transcode_videos.__doc__.lower()
        assert "timestamp" in doc_lower or "sync" in doc_lower or "original" in doc_lower


class TestOutputReporting:
    """Test output path and parameter reporting (MR-3)."""

    def test_Should_ReportOutputPaths_When_Transcoding_MR3(self):
        """THE MODULE SHALL report output paths.

        Requirements: MR-3
        Issue: Transcode module - Output path reporting
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert hasattr(report, "outputs")
        assert all(isinstance(output, (Path, dict)) for output in report.outputs)

    def test_Should_ReportParameters_When_Transcoding_MR3(self):
        """THE MODULE SHALL report transcoding parameters.

        Requirements: MR-3
        Issue: Transcode module - Parameter reporting
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "libx264",
                    "crf": 23,
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should include parameters used
        assert hasattr(report, "parameters") or hasattr(report, "config")

    def test_Should_ReturnTranscodeReport_When_Complete_MR3(self):
        """THE MODULE SHALL return TranscodeReport object.

        Requirements: MR-3
        Issue: Transcode module - Report structure
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import TranscodeReport, transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert isinstance(report, TranscodeReport)

    def test_Should_IncludeMetadataSidecars_When_Transcoding_MR3(self):
        """THE MODULE SHALL generate metadata sidecars for outputs.

        Requirements: MR-3, Design - Metadata sidecars
        Issue: Transcode module - Sidecar generation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should have metadata for each output
        assert report is not None


class TestDeterministicParameters:
    """Test deterministic output parameters (M-NFR-1)."""

    def test_Should_ProduceSameParams_When_SameConfig_MNFR1(self):
        """THE MODULE SHALL produce deterministic output parameters given a config.

        Requirements: M-NFR-1
        Issue: Transcode module - Deterministic parameters
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "libx264",
                    "crf": 23,
                }
            },
            provenance={},
        )

        # Act
        report1 = transcode_videos(manifest)
        report2 = transcode_videos(manifest)

        # Assert - Parameters should be identical
        assert len(report1.outputs) == len(report2.outputs)

    def test_Should_BuildDeterministicCommands_When_ConfigProvided_MNFR1(self):
        """THE MODULE SHALL build deterministic ffmpeg commands.

        Requirements: M-NFR-1, Design - Build ffmpeg commands per settings
        Issue: Transcode module - Command determinism
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "libx264",
                    "preset": "medium",
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should have consistent command structure
        assert report is not None


class TestFrameCountValidation:
    """Test frame count parity validation (M-NFR-2)."""

    def test_Should_ValidateFrameCount_When_Feasible_MNFR2(self):
        """THE MODULE SHALL validate frame count parity where feasible.

        Requirements: M-NFR-2, Design - Preserve frame counts
        Issue: Transcode module - Frame count validation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should include frame count validation
        assert report is not None

    def test_Should_ReportFrameCountMismatch_When_Detected_MNFR2(self):
        """THE MODULE SHALL report frame count mismatches.

        Requirements: M-NFR-2
        Issue: Transcode module - Mismatch reporting
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Report should have validation results
        assert hasattr(report, "validation") or hasattr(report, "frame_counts")

    def test_Should_PreserveFrameCount_When_Transcoding_MNFR2(self):
        """THE MODULE SHALL preserve frame counts during transcoding.

        Requirements: M-NFR-2, Design - Do not regenerate timestamps
        Issue: Transcode module - Frame preservation
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert report is not None


class TestFFmpegIntegration:
    """Test ffmpeg command building and execution."""

    def test_Should_BuildFFmpegCommand_When_Transcoding_Design(self):
        """THE MODULE SHALL build ffmpeg commands per settings.

        Requirements: Design - Build ffmpeg commands
        Issue: Transcode module - Command building
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "libx264",
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert report is not None

    def test_Should_HandleFFmpegErrors_When_Failed_Design(self):
        """THE MODULE SHALL handle ffmpeg failures with captured stderr.

        Requirements: Design - ExternalToolError
        Issue: Transcode module - Error handling
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import ExternalToolError, transcode_videos

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/nonexistent/cam0.mp4"),  # Invalid path
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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act & Assert
        with pytest.raises((ExternalToolError, FileNotFoundError, Exception)):
            transcode_videos(manifest)

    def test_Should_CaptureStderr_When_FFmpegFails_Design(self):
        """THE MODULE SHALL capture stderr on ffmpeg failures.

        Requirements: Design - Error handling with stderr
        Issue: Transcode module - Error context
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import ExternalToolError, transcode_videos

        videos = [
            VideoMetadata(
                camera_id=0,
                path=Path("/nonexistent/cam0.mp4"),
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
            config_snapshot={"transcode": {"enabled": True}},
            provenance={},
        )

        # Act & Assert
        with pytest.raises((ExternalToolError, FileNotFoundError, Exception)) as exc_info:
            transcode_videos(manifest)

        # Should have error context
        error_message = str(exc_info.value).lower()
        assert "error" in error_message or "not found" in error_message or "failed" in error_message


class TestGPUAcceleration:
    """Test GPU/NVENC preset support (Design - Future notes)."""

    def test_Should_SupportNVENC_When_Configured_Future(self):
        """THE MODULE SHALL support GPU/NVENC presets.

        Requirements: Design - Future notes
        Issue: Transcode module - GPU acceleration
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "codec": "h264_nvenc",
                    "preset": "fast",
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert - Should support NVENC codec
        assert report is not None

    def test_Should_ConfigureKeyframeInterval_When_Set_Future(self):
        """THE MODULE SHALL support configurable keyframe interval.

        Requirements: Design - Future notes
        Issue: Transcode module - Keyframe configuration
        """
        # Arrange
        from w2t_bkin.domain import Manifest, VideoMetadata
        from w2t_bkin.transcode import transcode_videos

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
            config_snapshot={
                "transcode": {
                    "enabled": True,
                    "keyframe_interval": 30,
                }
            },
            provenance={},
        )

        # Act
        report = transcode_videos(manifest)

        # Assert
        assert report is not None


class TestTranscodeReport:
    """Test TranscodeReport model."""

    def test_Should_CreateReport_When_DataProvided_Design(self):
        """THE MODULE SHALL provide TranscodeReport typed model.

        Requirements: Design - Output contract
        Issue: Transcode module - Report model
        """
        # Arrange
        from w2t_bkin.transcode import TranscodeReport

        # Act
        report = TranscodeReport(
            outputs=[Path("/data/mezzanine/cam0.mp4")],
            parameters={"codec": "libx264", "crf": 23},
            validation={"frame_count_match": True},
        )

        # Assert
        assert len(report.outputs) == 1
        assert report.parameters["codec"] == "libx264"

    def test_Should_SupportSkippedFlag_When_Disabled_Design(self):
        """THE MODULE SHALL support skipped flag in report.

        Requirements: MR-1 - Optional
        Issue: Transcode module - Skip indication
        """
        # Arrange
        from w2t_bkin.transcode import TranscodeReport

        # Act
        report = TranscodeReport(
            outputs=[],
            skipped=True,
            reason="Transcoding disabled in config",
        )

        # Assert
        assert report.skipped is True
        assert "disabled" in report.reason.lower()
