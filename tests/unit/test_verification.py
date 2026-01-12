"""Unit tests for verification operations."""

import pytest

from w2t_bkin.exceptions import CameraUnverifiableError, MismatchExceedsToleranceError, VerificationError
from w2t_bkin.models import SessionConfig
from w2t_bkin.operations.verification import verify_camera_ttl_sync


class TestOptionalCameraVerification:
    """Test verification behavior for optional cameras."""

    def test_optional_camera_missing_videos_skips_verification(self):
        """Optional camera with no videos should skip verification even if TTL exists."""
        # Setup
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_right",
                        "ttl_id": "ttl_camera",
                        "optional": True,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"face_right": 0}  # No frames discovered
        ttl_counts = {"ttl_camera": 510392}  # TTL channel exists with pulses

        # Should not raise - optional camera with no videos is skipped
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )

    def test_optional_camera_not_in_frame_counts_skips_verification(self):
        """Optional camera not in frame_counts dict should skip verification."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_right",
                        "ttl_id": "ttl_camera",
                        "optional": True,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {}  # Camera not discovered
        ttl_counts = {"ttl_camera": 510392}

        # Should not raise
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )

    def test_optional_camera_with_videos_but_mismatch_raises(self):
        """Optional camera with videos present should still verify sync and fail on mismatch."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_right",
                        "ttl_id": "ttl_camera",
                        "optional": True,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"face_right": 100}  # Videos discovered
        ttl_counts = {"ttl_camera": 200}  # Mismatch

        # Should raise - optional but present means we verify
        with pytest.raises(MismatchExceedsToleranceError):
            verify_camera_ttl_sync(
                frame_counts=frame_counts,
                ttl_counts=ttl_counts,
                session_config=session_config,
                tolerance=0,
            )

    def test_required_camera_missing_videos_raises(self):
        """Non-optional camera with no videos should raise verification error."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_left",
                        "ttl_id": "ttl_camera",
                        "optional": False,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {}  # Camera not discovered
        ttl_counts = {"ttl_camera": 510392}

        # Should raise - required camera missing
        with pytest.raises(VerificationError, match="No frame count available"):
            verify_camera_ttl_sync(
                frame_counts=frame_counts,
                ttl_counts=ttl_counts,
                session_config=session_config,
                tolerance=0,
            )

    def test_optional_camera_missing_ttl_skips(self):
        """Optional camera with missing TTL channel should skip verification."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_right",
                        "ttl_id": "ttl_missing",
                        "optional": True,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"face_right": 100}
        ttl_counts = {}  # TTL channel missing

        # Should not raise - optional camera with missing TTL is skipped
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )

    def test_required_camera_missing_ttl_raises(self):
        """Non-optional camera with missing TTL should raise CameraUnverifiableError."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_left",
                        "ttl_id": "ttl_missing",
                        "optional": False,
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"face_left": 100}
        ttl_counts = {}  # TTL channel missing

        # Should raise - required camera with missing TTL
        with pytest.raises(CameraUnverifiableError):
            verify_camera_ttl_sync(
                frame_counts=frame_counts,
                ttl_counts=ttl_counts,
                session_config=session_config,
                tolerance=0,
            )

    def test_camera_without_ttl_id_skips_verification(self):
        """Camera without ttl_id configured should skip verification."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "overhead",
                        # No ttl_id
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"overhead": 1000}
        ttl_counts = {}

        # Should not raise - no TTL sync configured
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=0,
        )

    def test_tolerance_allows_small_mismatch(self):
        """Mismatch within tolerance should not raise."""
        session_config = SessionConfig(
            config={},
            metadata={
                "cameras": [
                    {
                        "id": "face_left",
                        "ttl_id": "ttl_camera",
                    }
                ]
            },
            config_path=None,
            session_dir=None,
            output_dir=None,
        )

        frame_counts = {"face_left": 1000}
        ttl_counts = {"ttl_camera": 1005}  # 5 frame mismatch

        # Should not raise with tolerance=10
        verify_camera_ttl_sync(
            frame_counts=frame_counts,
            ttl_counts=ttl_counts,
            session_config=session_config,
            tolerance=10,
        )

        # Should raise with tolerance=0
        with pytest.raises(MismatchExceedsToleranceError):
            verify_camera_ttl_sync(
                frame_counts=frame_counts,
                ttl_counts=ttl_counts,
                session_config=session_config,
                tolerance=0,
            )
