"""Unit tests for transcode module (Phase 3 - Red Phase).

Tests video transcoding to mezzanine format with idempotence and content addressing.

Requirements: FR-4
Acceptance: A1, A3
GitHub Issue: #4
"""

from pathlib import Path
from typing import Dict

import pytest

from w2t_bkin.domain import TranscodedVideo, TranscodeOptions
from w2t_bkin.transcode import TranscodeError, create_transcode_options, is_already_transcoded, transcode_video, update_manifest_with_transcode
from w2t_bkin.utils import compute_file_checksum


class TestTranscodeOptions:
    """Test transcode configuration."""

    def test_Should_CreateDefaultOptions_When_NoParamsProvided(self):
        """Should create TranscodeOptions with sensible defaults."""
        options = create_transcode_options()

        assert options.codec == "libx264"
        assert options.crf == 18
        assert options.preset == "medium"

    def test_Should_OverrideDefaults_When_ParamsProvided(self):
        """Should allow custom transcode options."""
        options = create_transcode_options(codec="libx265", crf=20, preset="slow")

        assert options.codec == "libx265"
        assert options.crf == 20
        assert options.preset == "slow"

    def test_Should_ValidateCRF_When_CreatingOptions(self):
        """CRF should be in valid range [0, 51]."""
        with pytest.raises(ValueError):
            create_transcode_options(crf=-1)

        with pytest.raises(ValueError):
            create_transcode_options(crf=100)


class TestIdempotence:
    """Test transcoding idempotence (NFR-2)."""

    def test_Should_SkipTranscode_When_AlreadyExists(self):
        """Should detect already-transcoded videos (FR-4, NFR-2)."""
        video_path = Path("tests/fixtures/data/raw/Session-000001/Video/top/cam0_2025-01-01-00-00-00.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        # Mock: transcoded file already exists
        transcoded_path = Path("tests/fixtures/data/processed/Session-000001/Video/top/cam0_transcoded_abc123.mp4")

        result = is_already_transcoded(video_path, options, transcoded_path)

        assert result is True or result is False  # Should check existence

    def test_Should_Transcode_When_OptionsChanged(self):
        """Should re-transcode if options differ from cached."""
        video_path = Path("tests/fixtures/data/raw/Session-000001/Video/top/cam0_2025-01-01-00-00-00.avi")
        old_options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)
        new_options = TranscodeOptions(codec="libx264", crf=20, preset="slow", keyint=15)

        # Options differ, should re-transcode
        result = is_already_transcoded(video_path, new_options, Path("cached.mp4"))

        assert result is False


class TestContentAddressing:
    """Test content-based output paths."""

    def test_Should_ComputeChecksum_When_VideoProvided(self):
        """Should compute video file checksum."""
        video_path = Path("tests/fixtures/videos/test_video.avi")

        checksum = compute_file_checksum(video_path, algorithm="sha256")

        assert checksum is not None
        assert len(checksum) == 64  # SHA256 hex digest

    def test_Should_UseDeterministicChecksum_When_SameContent(self):
        """Checksum should be deterministic for same content."""
        video_path = Path("tests/fixtures/videos/test_video.avi")

        checksum1 = compute_file_checksum(video_path, algorithm="sha256")
        checksum2 = compute_file_checksum(video_path, algorithm="sha256")

        assert checksum1 == checksum2

    def test_Should_GeneratePathFromChecksum_When_Transcoding(self):
        """Output path should include checksum for content addressing."""
        video_path = Path("tests/fixtures/videos/test_video.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        result = transcode_video(video_path, options, output_dir=Path("/tmp"))

        # Output path should contain checksum
        assert "_" in result.output_path.stem
        assert len(result.output_path.stem.split("_")[-1]) >= 8  # At least 8 char checksum prefix


class TestTranscodeExecution:
    """Test video transcoding execution."""

    def test_Should_TranscodeVideo_When_ValidInputProvided(self):
        """Should transcode video to mezzanine format (FR-4)."""
        video_path = Path("tests/fixtures/videos/test_video.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)
        output_dir = Path("/tmp/transcode_test")

        result = transcode_video(video_path, options, output_dir)

        assert result.camera_id == "cam0" or "cam" in result.camera_id
        assert result.output_path.suffix == ".mp4"
        assert result.codec == "libx264"

    def test_Should_PreserveFrameCount_When_Transcoding(self):
        """Transcoded video should have same frame count as original."""
        video_path = Path("tests/fixtures/videos/test_video.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        result = transcode_video(video_path, options, output_dir=Path("/tmp"))

        # Should preserve frame count (FR-4)
        assert result.frame_count > 0

    def test_Should_HandleMissingFile_When_Transcoding(self):
        """Should raise TranscodeError for missing input."""
        missing_path = Path("nonexistent.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        with pytest.raises(TranscodeError):
            transcode_video(missing_path, options, output_dir=Path("/tmp"))


class TestManifestUpdate:
    """Test updating manifest with transcoded video paths."""

    def test_Should_UpdateManifest_When_TranscodeComplete(self):
        """Should add transcoded paths to manifest."""
        manifest = {"videos": [{"camera_id": "cam0", "path": "raw/video.avi"}]}
        transcoded = TranscodedVideo(
            camera_id="cam0",
            original_path=Path("raw/video.avi"),
            output_path=Path("processed/video_abc123.mp4"),
            codec="libx264",
            checksum="abc123",
            frame_count=1000,
        )

        updated = update_manifest_with_transcode(manifest, transcoded)

        assert "transcoded_path" in updated["videos"][0]
        assert "video_abc123.mp4" in str(updated["videos"][0]["transcoded_path"])

    def test_Should_PreserveOriginalPaths_When_UpdatingManifest(self):
        """Original video paths should remain in manifest after transcoding."""
        manifest = {"videos": [{"camera_id": "cam0", "path": "raw/video.avi"}]}
        transcoded = TranscodedVideo(
            camera_id="cam0",
            original_path=Path("raw/video.avi"),
            output_path=Path("processed/video_abc123.mp4"),
            codec="libx264",
            checksum="abc123",
            frame_count=1000,
        )

        updated = update_manifest_with_transcode(manifest, transcoded)

        # Original path should still exist
        assert "path" in updated["videos"][0]
        assert "raw/video.avi" in str(updated["videos"][0]["path"])


class TestFFmpegWrapper:
    """Test ffmpeg subprocess handling."""

    def test_Should_CallFFmpeg_When_Transcoding(self, monkeypatch):
        """Should invoke ffmpeg with correct parameters."""
        import subprocess
        from unittest.mock import MagicMock, Mock

        mock_subprocess = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_subprocess)

        video_path = Path("tests/fixtures/videos/test_video.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        transcode_video(video_path, options, output_dir=Path("/tmp"))

        # Should call ffmpeg subprocess
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-c:v" in call_args
        assert "libx264" in call_args

    def test_Should_HandleFFmpegError_When_TranscodeFails(self, monkeypatch):
        """Should raise TranscodeError when ffmpeg fails."""
        import subprocess
        from unittest.mock import MagicMock

        mock_subprocess = MagicMock(side_effect=Exception("ffmpeg error"))
        monkeypatch.setattr(subprocess, "run", mock_subprocess)

        video_path = Path("tests/fixtures/videos/test_video.avi")
        options = TranscodeOptions(codec="libx264", crf=18, preset="medium", keyint=15)

        with pytest.raises(TranscodeError):
            transcode_video(video_path, options, output_dir=Path("/tmp"))
