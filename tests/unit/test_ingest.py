"""Tests for ingest module (Phase 1 Red Phase).

Requirements: FR-1, FR-2, FR-3, FR-13, FR-15, FR-16
Acceptance: A6, A7

TDD Red Phase: Tests written before implementation.
All tests should fail initially with ImportError or AttributeError.
"""

from datetime import datetime
from pathlib import Path

import pytest


class TestManifestBuilding:
    """Test manifest discovery and building (FR-1)."""

    def test_Should_DiscoverAllCameraVideos_When_SessionProvided(self):
        """Should discover all camera video files matching session paths pattern (FR-1)."""
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_manifest

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        session_path = Path("tests/fixtures/sessions/valid_session.toml")

        config = load_config(config_path)
        session = load_session(session_path)

        manifest = build_manifest(config, session)

        # Should have discovered cameras
        assert len(manifest.cameras) > 0
        # Each camera should have video files
        for camera in manifest.cameras:
            assert len(camera.video_files) > 0

    def test_Should_DiscoverTTLFiles_When_DeclaredInSession(self):
        """Should discover TTL files matching paths pattern (FR-1)."""
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_manifest

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        session_path = Path("tests/fixtures/sessions/valid_session.toml")

        config = load_config(config_path)
        session = load_session(session_path)

        manifest = build_manifest(config, session)

        # Should have discovered TTLs
        assert len(manifest.ttls) > 0
        # Each TTL should have files
        for ttl in manifest.ttls:
            assert len(ttl.files) > 0

    def test_Should_DiscoverBpodFile_When_DeclaredInSession(self):
        """Should discover Bpod .mat file when present (FR-1)."""
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_manifest

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        session_path = Path("tests/fixtures/sessions/valid_session.toml")

        config = load_config(config_path)
        session = load_session(session_path)

        manifest = build_manifest(config, session)

        # Should have bpod file if present
        if session.bpod.path:
            assert manifest.bpod_files is not None
            assert len(manifest.bpod_files) > 0

    def test_Should_RaiseError_When_ExpectedFilesAreMissing(self):
        """Should raise descriptive error when expected files don't exist (FR-1)."""
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import IngestError, build_manifest

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        session_path = Path("tests/fixtures/sessions/missing_files.toml")

        config = load_config(config_path)
        session = load_session(session_path)

        with pytest.raises(IngestError) as exc_info:
            build_manifest(config, session)

        assert "missing" in str(exc_info.value).lower()

    def test_Should_IncludeAbsolutePaths_When_ManifestBuilt(self):
        """Should store absolute paths in manifest (FR-1)."""
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_manifest

        config_path = Path("tests/fixtures/configs/valid_config.toml")
        session_path = Path("tests/fixtures/sessions/valid_session.toml")

        config = load_config(config_path)
        session = load_session(session_path)

        manifest = build_manifest(config, session)

        # All paths should be absolute
        for camera in manifest.cameras:
            for video_file in camera.video_files:
                assert Path(video_file).is_absolute()


class TestFrameCountVerification:
    """Test frame counting and verification (FR-2, FR-3)."""

    def test_Should_CountVideoFrames_When_VideoFilesProvided(self):
        """Should handle video files appropriately based on their content (FR-2).

        Note: This test uses fixture files. Empty videos return 0 frames.
        Real video frame counting is tested in integration tests with actual video files.
        """
        from w2t_bkin.ingest import count_video_frames

        # Test with empty video fixture
        video_path = Path("tests/fixtures/videos/empty_video.avi")
        frame_count = count_video_frames(video_path)
        assert frame_count == 0, "Empty video should return 0 frames"
        assert isinstance(frame_count, int)

    def test_Should_ReturnZero_When_VideoFileNotFound(self):
        """Should return 0 when video file doesn't exist (FR-2)."""
        from w2t_bkin.ingest import count_video_frames

        video_path = Path("tests/fixtures/videos/nonexistent.avi")
        frame_count = count_video_frames(video_path)
        assert frame_count == 0
        assert isinstance(frame_count, int)

    def test_Should_CountTTLPulses_When_TTLFileProvided(self):
        """Should accurately count TTL pulses from log file (FR-2)."""
        from w2t_bkin.ingest import count_ttl_pulses

        ttl_path = Path("tests/fixtures/ttls/test_ttl.txt")

        pulse_count = count_ttl_pulses(ttl_path)

        assert pulse_count > 0
        assert isinstance(pulse_count, int)

    def test_Should_ComputeMismatch_When_CountsDiffer(self):
        """Should compute mismatch as |frame_count - ttl_pulse_count| (FR-2)."""
        from w2t_bkin.ingest import compute_mismatch

        frame_count = 1000
        ttl_pulse_count = 998

        mismatch = compute_mismatch(frame_count, ttl_pulse_count)

        assert mismatch == 2

    def test_Should_AbortWithDiagnostic_When_MismatchExceedsTolerance(self):
        """Should abort with detailed diagnostic when mismatch > tolerance (FR-3, A6)."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import VerificationError, verify_manifest

        # Create manifest with large mismatch
        manifest = Manifest(
            session_id="test",
            cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=950, video_files=["test.avi"])],  # mismatch = 50
        )

        config_tolerance = 10  # tolerance = 10 frames

        with pytest.raises(VerificationError) as exc_info:
            verify_manifest(manifest, tolerance=config_tolerance)

        error = str(exc_info.value)
        # Should include diagnostic details (A6)
        assert "cam0" in error
        assert "ttl_camera" in error
        assert "1000" in error  # frame_count
        assert "950" in error  # ttl_pulse_count
        assert "50" in error or "mismatch" in error.lower()

    def test_Should_Proceed_When_MismatchWithinTolerance(self):
        """Should proceed when mismatch <= tolerance (FR-16, A7)."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import verify_manifest

        # Create manifest with small mismatch
        manifest = Manifest(
            session_id="test",
            cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=998, video_files=["test.avi"])],  # mismatch = 2
        )

        config_tolerance = 10  # tolerance = 10 frames

        # Should not raise
        result = verify_manifest(manifest, tolerance=config_tolerance)

        assert result.status == "verified"

    def test_Should_WarnOnMismatch_When_ConfigEnabled(self, caplog):
        """Should emit warning when mismatch within tolerance and warn_on_mismatch=True (FR-16, A7)."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import verify_manifest

        manifest = Manifest(
            session_id="test", cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=998, video_files=["test.avi"])]
        )

        verify_manifest(manifest, tolerance=10, warn_on_mismatch=True)

        # Should have warning in logs
        assert any("mismatch" in record.message.lower() for record in caplog.records)

    def test_Should_NotWarnOnMismatch_When_ConfigDisabled(self, caplog):
        """Should remain silent when mismatch within tolerance and warn_on_mismatch=False (FR-16, A7)."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import verify_manifest

        manifest = Manifest(
            session_id="test", cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=998, video_files=["test.avi"])]
        )

        verify_manifest(manifest, tolerance=10, warn_on_mismatch=False)

        # Should have no mismatch warnings
        assert not any("mismatch" in record.message.lower() for record in caplog.records)


class TestTTLReferenceValidation:
    """Test camera TTL reference validation (FR-15)."""

    def test_Should_ValidateTTLReferences_When_BuildingManifest(self):
        """Should validate that camera ttl_id exists in session TTLs (FR-15)."""
        from w2t_bkin.config import load_session
        from w2t_bkin.ingest import validate_ttl_references

        session_path = Path("tests/fixtures/sessions/valid_session.toml")
        session = load_session(session_path)

        # Should not raise for valid references
        validate_ttl_references(session)

    def test_Should_WarnOnInvalidTTLReference_When_TTLNotFound(self, caplog):
        """Should emit warning when camera references non-existent ttl_id (FR-15)."""
        from w2t_bkin.domain import TTL, BpodSession, Camera, Session, SessionMetadata
        from w2t_bkin.ingest import validate_ttl_references

        # Create session with invalid reference
        session = Session(
            session=SessionMetadata(id="test", subject_id="m1", date="2025-01-01", experimenter="test", description="test", sex="M", age="P60", genotype="WT"),
            bpod=BpodSession(path="", order="name_asc"),
            TTLs=[TTL(id="ttl1", description="test", paths="*.txt")],
            cameras=[Camera(id="cam0", description="test", paths="*.avi", order="name_asc", ttl_id="ttl_nonexistent")],  # Invalid reference
        )

        validate_ttl_references(session)

        # Should have warning about unverifiable camera
        assert any("unverifiable" in record.message.lower() for record in caplog.records)

    def test_Should_FlagCameraAsUnverifiable_When_NoTTLReference(self):
        """Should mark camera as unverifiable when no ttl_id provided (FR-15)."""
        from w2t_bkin.domain import Camera
        from w2t_bkin.ingest import check_camera_verifiable

        camera = Camera(id="cam0", description="test", paths="*.avi", order="name_asc", ttl_id="")  # No TTL reference

        ttl_ids = {"ttl1", "ttl2"}

        is_verifiable = check_camera_verifiable(camera, ttl_ids)

        assert is_verifiable is False


class TestVerificationSummary:
    """Test verification summary sidecar (FR-13)."""

    def test_Should_PersistVerificationSummary_When_VerificationCompletes(self):
        """Should write verification_summary.json with per-camera results (FR-13)."""
        import json

        from w2t_bkin.domain import VerificationSummary
        from w2t_bkin.ingest import write_verification_summary

        summary = VerificationSummary(
            session_id="test_session",
            cameras=[
                {
                    "camera_id": "cam0",
                    "ttl_id": "ttl_camera",
                    "frame_count": 1000,
                    "ttl_pulse_count": 1000,
                    "mismatch": 0,
                    "verifiable": True,
                    "status": "verified",
                }
            ],
            generated_at=datetime.utcnow().isoformat(),
        )

        output_path = Path("tests/temp/verification_summary.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        write_verification_summary(summary, output_path)

        # Should exist and be valid JSON
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["session_id"] == "test_session"
        assert len(data["cameras"]) == 1

    def test_Should_IncludeCameraDetails_When_SummaryWritten(self):
        """Should include camera_id, ttl_id, counts, mismatch, status in summary (FR-13, A6)."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import create_verification_summary

        manifest = Manifest(
            session_id="test", cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=998, video_files=["test.avi"])]
        )

        summary = create_verification_summary(manifest)

        camera_result = summary["cameras"][0]
        assert camera_result["camera_id"] == "cam0"
        assert camera_result["ttl_id"] == "ttl_camera"
        assert camera_result["frame_count"] == 1000
        assert camera_result["ttl_pulse_count"] == 998
        assert camera_result["mismatch"] == 2
        assert "status" in camera_result

    def test_Should_IncludeGeneratedTimestamp_When_SummaryCreated(self):
        """Should include ISO-format timestamp in verification summary (FR-13)."""
        from datetime import datetime

        from w2t_bkin.domain import Manifest
        from w2t_bkin.ingest import create_verification_summary

        manifest = Manifest(session_id="test", cameras=[])

        summary = create_verification_summary(manifest)

        assert "generated_at" in summary
        # Should be valid ISO format
        datetime.fromisoformat(summary["generated_at"])


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_Should_HandleZeroFrameVideo_When_Verifying(self):
        """Should handle video with zero frames gracefully."""
        from w2t_bkin.ingest import count_video_frames

        video_path = Path("tests/fixtures/videos/empty_video.avi")

        frame_count = count_video_frames(video_path)

        assert frame_count == 0

    def test_Should_HandleEmptyTTLFile_When_Counting(self):
        """Should handle TTL file with no pulses."""
        from w2t_bkin.ingest import count_ttl_pulses

        ttl_path = Path("tests/fixtures/ttls/empty_ttl.txt")

        pulse_count = count_ttl_pulses(ttl_path)

        assert pulse_count == 0

    def test_Should_HandleMismatchAtToleranceBoundary_When_Verifying(self):
        """Should correctly handle mismatch exactly at tolerance boundary."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import verify_manifest

        manifest = Manifest(
            session_id="test",
            cameras=[ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=990, video_files=["test.avi"])],  # mismatch = 10
        )

        # Should proceed when mismatch == tolerance
        result = verify_manifest(manifest, tolerance=10)
        assert result.status == "verified"

    def test_Should_HandleMultipleCameras_When_Verifying(self):
        """Should verify all cameras in manifest."""
        from w2t_bkin.domain import Manifest, ManifestCamera
        from w2t_bkin.ingest import verify_manifest

        manifest = Manifest(
            session_id="test",
            cameras=[
                ManifestCamera(camera_id="cam0", ttl_id="ttl_camera", frame_count=1000, ttl_pulse_count=1000, video_files=["test0.avi"]),
                ManifestCamera(camera_id="cam1", ttl_id="ttl_camera", frame_count=500, ttl_pulse_count=500, video_files=["test1.avi"]),
            ],
        )

        result = verify_manifest(manifest, tolerance=0)

        assert result.status == "verified"
        assert len(result.camera_results) == 2
