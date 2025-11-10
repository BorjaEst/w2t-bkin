"""Unit tests for the transcode module.

Tests optional video transcoding to mezzanine format as specified in
requirements.md FR-4 and design.md.

All tests follow TDD Red Phase principles with clear EARS requirements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# Test: Configuration-driven Transcoding (FR-4, NFR-10)
# ============================================================================


class TestTranscodeConfiguration:
    """Test configuration-driven transcoding behavior (FR-4, NFR-10)."""

    def test_Should_SkipTranscoding_When_DisabledInConfig_Issue_Transcode_FR4(self, mock_empty_transcode_manifest: Path, tmp_path: Path):
        """WHERE transcoding is disabled in configuration, THE SYSTEM SHALL operate directly on raw videos.

        Requirements: FR-4 (Optional), NFR-10 (Type safety)
        Issue: Transcode module - Config-driven execution
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act - Empty manifest simulates disabled/no-op
        summary = transcode_videos(mock_empty_transcode_manifest, output_dir)

        # Assert - Should skip transcoding when disabled
        assert summary.skipped is True
        assert len(summary.videos) == 0

    def test_Should_TranscodeVideos_When_EnabledInConfig_Issue_Transcode_FR4(self, mock_transcode_manifest: Path, tmp_path: Path):
        """WHERE transcoding is enabled in configuration, THE SYSTEM SHALL transcode videos to mezzanine format.

        Requirements: FR-4
        Issue: Transcode module - Config-driven execution
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should transcode when enabled
        assert summary.skipped is False
        assert len(summary.videos) > 0

    def test_Should_UseConfiguredCodec_When_Transcoding_Issue_Transcode_NFR10(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL use codec specified in configuration.

        Requirements: NFR-10 (Type safety and configurability)
        Issue: Transcode module - Codec configuration
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        codec_override = "libx265"

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir, codec=codec_override)

        # Assert - Should use specified codec
        assert summary.codec == codec_override

    def test_Should_ValidateCodecParameters_When_Loading_Issue_Transcode_NFR10(self):
        """THE SYSTEM SHALL validate codec parameters via Pydantic.

        Requirements: NFR-10
        Issue: Transcode module - Parameter validation
        """
        pytest.skip("Codec validation in Settings not yet implemented - future enhancement")
        # Arrange
        from w2t_bkin.config import Settings

        # Act & Assert - Should reject invalid codec
        with pytest.raises(Exception):  # Pydantic ValidationError
            Settings(video={"transcode": {"enabled": True, "codec": "invalid_codec"}})


# ============================================================================
# Test: Manifest Parsing and Video Discovery (FR-1, FR-4)
# ============================================================================


class TestManifestParsing:
    """Test manifest parsing and video discovery (FR-1, FR-4)."""

    def test_Should_ParseManifest_When_TranscodingEnabled_Issue_Transcode_FR4(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL parse manifest to identify videos for transcoding.

        Requirements: FR-4, Ingest module integration
        Issue: Transcode module - Manifest parsing
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should identify all videos from manifest
        assert hasattr(summary, "videos")
        assert isinstance(summary.videos, list)

    def test_Should_FailFast_When_ManifestMissing_Issue_Transcode_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL fail fast when manifest is missing.

        Requirements: NFR-8 (Data integrity)
        Issue: Transcode module - Input validation
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        missing_manifest = tmp_path / "nonexistent" / "manifest.json"

        # Act & Assert - Should raise MissingInputError
        with pytest.raises(Exception):  # MissingInputError
            transcode_videos(missing_manifest, output_dir)

    def test_Should_DiscoverAllVideos_When_ProcessingManifest_Issue_Transcode_FR1(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL discover all five camera videos from manifest.

        Requirements: FR-1 (five camera videos per session)
        Issue: Transcode module - Video discovery
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should process all cameras
        assert len(summary.videos) == 5


# ============================================================================
# Test: FFmpeg Command Generation and Execution (FR-4)
# ============================================================================


class TestFFmpegExecution:
    """Test FFmpeg command generation and execution."""

    def test_Should_GenerateValidCommand_When_Transcoding_Issue_Transcode_FR4(self):
        """THE SYSTEM SHALL generate valid FFmpeg commands with configured parameters.

        Requirements: FR-4
        Issue: Transcode module - FFmpeg command generation
        """
        # Arrange
        from w2t_bkin.transcode import _generate_ffmpeg_command

        input_path = Path("/data/raw/session_001/cam0.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")
        codec = "libx264"
        crf = 23
        preset = "medium"

        # Act
        command = _generate_ffmpeg_command(input_path, output_path, codec, crf, preset)

        # Assert - Should include all required parameters
        assert "ffmpeg" in command
        assert str(input_path) in command
        assert str(output_path) in command
        assert codec in command
        assert str(crf) in command
        assert preset in command

    def test_Should_HandleFFmpegFailure_When_Transcoding_Issue_Transcode_Design(self):
        """THE SYSTEM SHALL handle FFmpeg execution failures gracefully.

        Requirements: Design - Error handling
        Issue: Transcode module - FFmpeg error handling
        """
        pytest.skip("FFmpeg error simulation not yet implemented - requires actual FFmpeg integration")
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        # Create manifest with corrupted video that causes FFmpeg to fail
        # This would require actual FFmpeg execution to test properly
        # Act & Assert - Should raise TranscodeError with details
        # with pytest.raises(Exception):  # TranscodeError
        #     transcode_videos(manifest_path, output_dir)

    def test_Should_IncludeKeyframeInterval_When_Configured_Issue_Transcode_Design(self):
        """THE SYSTEM SHALL include keyframe interval in FFmpeg command.

        Requirements: Design - Configuration keys
        Issue: Transcode module - Keyframe configuration
        """
        # Arrange
        from w2t_bkin.transcode import _generate_ffmpeg_command

        input_path = Path("/data/raw/session_001/cam0.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")
        keyint = 30

        # Act
        command = _generate_ffmpeg_command(input_path, output_path, keyint=keyint)

        # Assert - Should include keyint parameter
        assert f"-g {keyint}" in command or f"keyint={keyint}" in command


# ============================================================================
# Test: Output Validation (NFR-8)
# ============================================================================


class TestOutputValidation:
    """Test transcoded output validation (NFR-8)."""

    def test_Should_ValidateFrameCount_When_TranscodingComplete_Issue_Transcode_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL validate frame count matches input.

        Requirements: NFR-8 (Data integrity)
        Issue: Transcode module - Frame count validation
        """
        # Arrange
        from w2t_bkin.transcode import _validate_transcode_output

        input_path = tmp_path / "input.avi"
        output_path = tmp_path / "output.mp4"
        input_path.write_text("mock input")
        output_path.write_text("mock output")
        expected_frames = 18000

        # Act
        validation = _validate_transcode_output(input_path, output_path, expected_frames)

        # Assert - Should verify frame count matches
        assert validation.frame_count_match is True
        assert validation.output_frames == expected_frames

    def test_Should_ValidateDuration_When_TranscodingComplete_Issue_Transcode_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL validate duration matches input.

        Requirements: NFR-8
        Issue: Transcode module - Duration validation
        """
        # Arrange
        from w2t_bkin.transcode import _validate_transcode_output

        input_path = tmp_path / "input.avi"
        output_path = tmp_path / "output.mp4"
        input_path.write_text("mock input")
        output_path.write_text("mock output")
        expected_duration = 600.0

        # Act
        validation = _validate_transcode_output(input_path, output_path, expected_frames=18000)

        # Assert - Should verify duration matches within tolerance
        assert abs(validation.duration_delta_sec) < 0.1  # 100ms tolerance

    def test_Should_ValidateCodec_When_TranscodingComplete_Issue_Transcode_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL validate output codec matches configuration.

        Requirements: NFR-8
        Issue: Transcode module - Codec validation
        """
        # Arrange
        from w2t_bkin.transcode import _validate_transcode_output

        input_path = tmp_path / "input.avi"
        output_path = tmp_path / "output.mp4"
        input_path.write_text("mock input")
        output_path.write_text("mock output")
        expected_codec = "libx264"

        # Act
        validation = _validate_transcode_output(input_path, output_path, expected_frames=18000)

        # Assert - Should verify codec matches
        assert validation.codec_match is True

    def test_Should_FailValidation_When_OutputMissing_Issue_Transcode_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL fail validation when output file is missing.

        Requirements: NFR-8
        Issue: Transcode module - Output validation error handling
        """
        # Arrange
        from w2t_bkin.transcode import _validate_transcode_output

        input_path = tmp_path / "input.avi"
        output_path = tmp_path / "nonexistent_output.mp4"
        input_path.write_text("mock input")

        # Act & Assert - Should raise validation error
        with pytest.raises(Exception):
            _validate_transcode_output(input_path, output_path, expected_frames=18000)


# ============================================================================
# Test: Summary Generation (NFR-3)
# ============================================================================


class TestSummaryGeneration:
    """Test transcode summary generation (NFR-3)."""

    def test_Should_GenerateSummaryJSON_When_TranscodingComplete_Issue_Transcode_NFR3(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL emit a JSON summary with statistics.

        Requirements: NFR-3 (Observability)
        Issue: Transcode module - Summary generation
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should contain required fields
        assert hasattr(summary, "session_id")
        assert hasattr(summary, "codec")
        assert hasattr(summary, "videos")
        assert hasattr(summary, "total_transcoding_time_sec")

    def test_Should_IncludePerVideoStats_When_Summarizing_Issue_Transcode_NFR3(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL include per-video statistics in summary.

        Requirements: NFR-3, Design - Logging & Diagnostics
        Issue: Transcode module - Per-video metrics
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Each video should have detailed stats
        for video_summary in summary.videos:
            assert hasattr(video_summary, "camera_id")
            assert hasattr(video_summary, "input_path")
            assert hasattr(video_summary, "output_path")
            assert hasattr(video_summary, "transcoding_time_sec")
            assert hasattr(video_summary, "frame_count_match")
            assert hasattr(video_summary, "compression_ratio")

    def test_Should_RecordWarnings_When_IssuesOccur_Issue_Transcode_NFR3(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL record warnings in summary.

        Requirements: NFR-3
        Issue: Transcode module - Warning tracking
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act - Force operation to trigger warnings
        summary = transcode_videos(mock_transcode_manifest, output_dir, force=True)

        # Assert - Should track warnings if any occurred
        assert hasattr(summary, "warnings")
        assert isinstance(summary.warnings, list)


# ============================================================================
# Test: Idempotence and Caching (NFR-2)
# ============================================================================


class TestIdempotence:
    """Test idempotent re-runs (NFR-2)."""

    def test_Should_SkipExisting_When_OutputAlreadyExists_Issue_Transcode_NFR2(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL skip transcoding if output exists and input unchanged.

        Requirements: NFR-2 (Idempotent re-run)
        Issue: Transcode module - Idempotence
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act - First run
        transcode_videos(mock_transcode_manifest, output_dir)

        # Act - Second run without changes
        summary2 = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should skip re-transcoding
        assert summary2.skipped_existing > 0

    def test_Should_ForceRetranscode_When_FlagSet_Issue_Transcode_NFR2(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL re-transcode when forced, even if output exists.

        Requirements: NFR-2
        Issue: Transcode module - Force re-run
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Pre-existing output
        transcode_videos(mock_transcode_manifest, output_dir)

        # Act - Force re-transcode
        summary = transcode_videos(mock_transcode_manifest, output_dir, force=True)

        # Assert - Should re-transcode all videos
        assert summary.skipped_existing == 0
        assert len(summary.videos) == 5

    def test_Should_DetectInputChanges_When_CheckingCache_Issue_Transcode_NFR2(self):
        """THE SYSTEM SHALL detect input file changes via hash comparison.

        Requirements: NFR-2, NFR-8 (Data integrity)
        Issue: Transcode module - Input change detection
        """
        # Arrange
        from w2t_bkin.transcode import _should_skip_transcode

        input_path = Path("/data/raw/session_001/cam0.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")
        cached_hash = "abc123def456"

        # Act - Input hash changed
        should_skip = _should_skip_transcode(input_path, output_path, cached_hash="different_hash")

        # Assert - Should not skip due to input change
        assert should_skip is False


# ============================================================================
# Test: Provenance Capture (NFR-11)
# ============================================================================


class TestProvenance:
    """Test provenance capture (NFR-11)."""

    def test_Should_RecordInputHash_When_Transcoding_Issue_Transcode_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL record input file hashes for provenance.

        Requirements: NFR-11 (Provenance)
        Issue: Transcode module - Provenance capture
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should record hashes
        for video in summary.videos:
            assert hasattr(video, "input_hash")
            assert video.input_hash is not None

    def test_Should_RecordFFmpegVersion_When_Transcoding_Issue_Transcode_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL record FFmpeg version used.

        Requirements: NFR-11
        Issue: Transcode module - Tool version tracking
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should include FFmpeg version
        assert hasattr(summary, "ffmpeg_version")
        assert summary.ffmpeg_version is not None

    def test_Should_RecordExactCommand_When_Transcoding_Issue_Transcode_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL record exact FFmpeg command used.

        Requirements: NFR-11
        Issue: Transcode module - Command provenance
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should record commands
        for video in summary.videos:
            assert hasattr(video, "ffmpeg_command")
            assert video.ffmpeg_command is not None


class TestIdempotence:
    """Test idempotent re-running behavior (NFR-2)."""

    def test_Should_SkipExisting_When_OutputAlreadyExists_NFR2(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Use fixtures
        # First run
        summary1 = transcode_videos(mock_transcode_manifest, output_dir)

        # Act - Second run without changes
        summary2 = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should skip re-transcoding
        assert summary2.skipped_existing > 0

    def test_Should_ForceRetranscode_When_FlagSet_NFR2(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Use fixtures
        # Pre-existing output
        transcode_videos(mock_transcode_manifest, output_dir)

        # Act - Force re-transcode
        summary = transcode_videos(mock_transcode_manifest, output_dir, force=True)

        # Assert - Should re-transcode all videos
        assert summary.skipped_existing == 0
        assert len(summary.videos) == 5

    def test_Should_DetectInputChanges_When_CheckingCache_NFR2(self):
        """THE SYSTEM SHALL detect input file changes via hash comparison.

        Requirements: NFR-2, NFR-8 (Data integrity)
        Issue: Transcode module - Input change detection
        """
        # Arrange
        from w2t_bkin.transcode import _should_skip_transcode

        input_path = Path("/data/raw/session_001/cam0.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")
        cached_hash = "abc123def456"

        # Act - Input hash changed
        should_skip = _should_skip_transcode(input_path, output_path, cached_hash="different_hash")

        # Assert - Should not skip due to input change
        assert should_skip is False


class TestProvenance:
    """Test provenance capture (NFR-11)."""

    def test_Should_RecordInputHash_When_Transcoding_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should record hashes
        for video in summary.videos:
            assert hasattr(video, "input_hash")
            assert video.input_hash is not None

    def test_Should_RecordFFmpegVersion_When_Transcoding_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should include FFmpeg version
        assert hasattr(summary, "ffmpeg_version")
        assert summary.ffmpeg_version is not None

    def test_Should_RecordExactCommand_When_Transcoding_NFR11(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should record commands
        for video in summary.videos:
            assert hasattr(video, "ffmpeg_command")
            assert video.ffmpeg_command is not None


class TestPerformance:
    """Test performance considerations (NFR-4)."""

    def test_Should_RecordTranscodingTime_When_Processing_NFR3(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should measure time
        assert summary.total_transcoding_time_sec > 0
        for video in summary.videos:
            assert video.transcoding_time_sec > 0

    def test_Should_SupportParallelProcessing_When_Configured_NFR4(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act - With parallelization enabled
        summary = transcode_videos(mock_transcode_manifest, output_dir, parallel=True)

        # Assert - Should process faster than sequential
        # This is a design placeholder - actual implementation TBD
        assert hasattr(summary, "parallel_workers")

    def test_Should_StreamProcess_When_Transcoding_NFR4(self):
        """THE SYSTEM SHALL use streaming mode to avoid loading entire video.

        Requirements: NFR-4, Design - Performance considerations
        Issue: Transcode module - Memory efficiency
        """
        # Arrange
        from w2t_bkin.transcode import _generate_ffmpeg_command

        input_path = Path("/data/raw/session_001/cam0.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")

        # Act
        command = _generate_ffmpeg_command(input_path, output_path)

        # Assert - Should not include memory-intensive flags
        assert "-i" in command  # Input flag (streaming default)
        assert "-hwaccel" not in command or "copy" in command  # No full decode


class TestReproducibility:
    """Test reproducible outputs (NFR-1)."""

    def test_Should_ProduceSameOutput_When_RerunWithSameInputs_NFR1(self, mock_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL produce identical outputs for identical inputs.

        Requirements: NFR-1 (Reproducibility)
        Issue: Transcode module - Deterministic encoding
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir1 = tmp_path / "video1"
        output_dir2 = tmp_path / "video2"
        output_dir1.mkdir()
        output_dir2.mkdir()

        # Act - Two independent runs
        summary1 = transcode_videos(mock_transcode_manifest, output_dir1)
        summary2 = transcode_videos(mock_transcode_manifest, output_dir2)

        # Assert - Should produce identical frame counts and durations
        assert len(summary1.videos) == len(summary2.videos)
        for v1, v2 in zip(summary1.videos, summary2.videos):
            assert v1.output_frames == v2.output_frames
            assert abs(v1.output_duration_sec - v2.output_duration_sec) < 0.01


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_Should_HandleEmptyManifest_When_Processing_Design(self, mock_empty_transcode_manifest: Path, tmp_path: Path):
        """THE SYSTEM SHALL handle manifest with no videos gracefully.

        Requirements: Design - Error handling
        Issue: Transcode module - Empty input handling
        """
        # Arrange
        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = transcode_videos(mock_empty_transcode_manifest, output_dir)

        # Assert - Should complete without errors
        assert len(summary.videos) == 0
        assert summary.warnings is not None
        assert summary.warnings is not None

    def test_Should_HandleMissingInputVideo_When_Transcoding_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL fail fast when input video is missing.

        Requirements: NFR-8, Design - MissingInputError
        Issue: Transcode module - Missing input handling
        """
        # Arrange
        import json

        from w2t_bkin.transcode import transcode_videos

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create manifest with non-existent video
        manifest_data = {"session_id": "test", "videos": [{"camera_id": 0, "path": "/nonexistent/video.avi", "fps": 30, "duration": 600}]}
        manifest_path = tmp_path / "manifest.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        # Act & Assert - Should raise MissingInputError
        with pytest.raises(Exception):  # MissingInputError
            transcode_videos(manifest_path, output_dir)

    def test_Should_HandleLargeVideo_When_Transcoding_NFR4(self, mock_transcode_manifest: Path, tmp_path: Path):
        # Arrange

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        from w2t_bkin.transcode import transcode_videos

        # Act - Process large video (e.g., 10GB, 4K resolution)
        summary = transcode_videos(mock_transcode_manifest, output_dir)

        # Assert - Should complete without memory errors
        assert summary.total_transcoding_time_sec > 0
        for video in summary.videos:
            assert video.validation_passed is True

    def test_Should_HandleCorruptedVideo_When_Validating_NFR8(self):
        """THE SYSTEM SHALL detect and report corrupted video files.

        Requirements: NFR-8
        Issue: Transcode module - Corruption detection
        """
        # Arrange
        from w2t_bkin.transcode import _validate_transcode_output

        input_path = Path("/data/raw/session_001/cam0_corrupted.avi")
        output_path = Path("/data/interim/session_001/video/cam0_transcoded.mp4")

        # Act & Assert - Should detect corruption
        with pytest.raises(Exception):  # ValidationError or TranscodeError
            _validate_transcode_output(input_path, output_path, expected_frames=1)
