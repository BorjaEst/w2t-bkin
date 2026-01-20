"""Unit tests for operations.discovery module.

Tests the pure discovery functions for cameras, TTLs, Bpod, and models.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.metadata import BpodMeta, CameraMeta, PoseModelMeta, PoseMeta, TTLsMeta
from w2t_bkin.models import DiscoveryResult, SessionInfo
from w2t_bkin.operations.discovery import (
    discover_bpod_files,
    discover_camera_files,
    discover_pose_files,
    discover_pose_models,
    discover_ttl_files,
)


class TestDiscoverCameraFiles:
    """Tests for discover_camera_files pure function."""

    def test_Should_DiscoverAndSortFiles_When_CameraFilesExist(self, tmp_path):
        """Should discover and sort camera files using configured order."""
        # Arrange
        session_dir = tmp_path / "session"
        video_dir = session_dir / "Video" / "top"
        video_dir.mkdir(parents=True)

        # Create test video files
        (video_dir / "cam0_001.avi").touch()
        (video_dir / "cam0_003.avi").touch()
        (video_dir / "cam0_002.avi").touch()

        cameras = [
            CameraMeta(
                id="camera_0",
                paths="Video/top/*.avi",
                order="name_asc",
            )
        ]

        # Act
        result = discover_camera_files(session_dir, cameras)

        # Assert
        assert "camera_0" in result
        assert len(result["camera_0"]) == 3
        # Check sorted order
        assert result["camera_0"][0].name == "cam0_001.avi"
        assert result["camera_0"][1].name == "cam0_002.avi"
        assert result["camera_0"][2].name == "cam0_003.avi"

    def test_Should_ReturnEmptyList_When_OptionalCameraHasNoFiles(self, tmp_path):
        """Should return empty list for optional camera with no files."""
        # Arrange
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        cameras = [
            CameraMeta(
                id="camera_optional",
                paths="Video/missing/*.avi",
                optional=True,
            )
        ]

        # Act
        result = discover_camera_files(session_dir, cameras)

        # Assert
        assert "camera_optional" in result
        assert result["camera_optional"] == []

    def test_Should_RaiseIngestError_When_RequiredCameraHasNoFiles(self, tmp_path):
        """Should raise IngestError when required camera has no files."""
        # Arrange
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        cameras = [
            CameraMeta(
                id="camera_required",
                paths="Video/missing/*.avi",
                optional=False,
            )
        ]

        # Act & Assert
        with pytest.raises(IngestError, match="No video files found for required camera"):
            discover_camera_files(session_dir, cameras)

    def test_Should_HandleMultipleCameras_When_Called(self, tmp_path):
        """Should handle multiple cameras with different configurations."""
        # Arrange
        session_dir = tmp_path / "session"
        
        # Camera 0 exists
        cam0_dir = session_dir / "Video" / "top"
        cam0_dir.mkdir(parents=True)
        (cam0_dir / "vid.avi").touch()

        # Camera 1 is optional and missing
        cameras = [
            CameraMeta(id="camera_0", paths="Video/top/*.avi"),
            CameraMeta(id="camera_1", paths="Video/side/*.avi", optional=True),
        ]

        # Act
        result = discover_camera_files(session_dir, cameras)

        # Assert
        assert len(result) == 2
        assert len(result["camera_0"]) == 1
        assert len(result["camera_1"]) == 0


class TestDiscoverTTLFiles:
    """Tests for discover_ttl_files pure function."""

    def test_Should_DiscoverTTLFiles_When_FilesExist(self, tmp_path):
        """Should discover and sort TTL files."""
        # Arrange
        session_dir = tmp_path / "session"
        ttl_dir = session_dir / "TTLs"
        ttl_dir.mkdir(parents=True)

        (ttl_dir / "cam_frame_001.txt").touch()
        (ttl_dir / "cam_frame_002.txt").touch()

        ttls = [
            TTLsMeta(
                id="ttl_camera",
                paths="TTLs/*_frame*.txt",
            )
        ]

        # Act
        result = discover_ttl_files(session_dir, ttls)

        # Assert
        assert "ttl_camera" in result
        assert len(result["ttl_camera"]) == 2

    def test_Should_ReturnEmptyList_When_TTLFilesNotFound(self, tmp_path, caplog):
        """Should return empty list and log warning when TTL files not found."""
        # Arrange
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        ttls = [
            TTLsMeta(
                id="ttl_missing",
                paths="TTLs/*.txt",
            )
        ]

        # Act
        with caplog.at_level(logging.WARNING):
            result = discover_ttl_files(session_dir, ttls)

        # Assert
        assert "ttl_missing" in result
        assert result["ttl_missing"] == []
        assert "No TTL files found" in caplog.text

    def test_Should_HandleMultipleTTLChannels_When_Called(self, tmp_path):
        """Should handle multiple TTL channels independently."""
        # Arrange
        session_dir = tmp_path / "session"
        ttl_dir = session_dir / "TTLs"
        ttl_dir.mkdir(parents=True)

        (ttl_dir / "camera.txt").touch()
        (ttl_dir / "cue.txt").touch()

        ttls = [
            TTLsMeta(id="ttl_camera", paths="TTLs/camera.txt"),
            TTLsMeta(id="ttl_cue", paths="TTLs/cue.txt"),
            TTLsMeta(id="ttl_missing", paths="TTLs/missing.txt"),
        ]

        # Act
        result = discover_ttl_files(session_dir, ttls)

        # Assert
        assert len(result) == 3
        assert len(result["ttl_camera"]) == 1
        assert len(result["ttl_cue"]) == 1
        assert len(result["ttl_missing"]) == 0


class TestDiscoverBpodFiles:
    """Tests for discover_bpod_files pure function."""

    def test_Should_DiscoverBpodFiles_When_FilesExist(self, tmp_path):
        """Should discover Bpod files using configured pattern."""
        # Arrange
        session_dir = tmp_path / "session"
        bpod_dir = session_dir / "Bpod"
        bpod_dir.mkdir(parents=True)

        (bpod_dir / "session_001.mat").touch()
        (bpod_dir / "session_002.mat").touch()

        bpod = BpodMeta(
            path="Bpod/*.mat",
            order="name_asc",
        )

        # Act
        result = discover_bpod_files(session_dir, bpod)

        # Assert
        assert "bpod" in result
        assert len(result["bpod"]) == 2

    def test_Should_ReturnEmptyDict_When_BpodNotConfigured(self, tmp_path):
        """Should return empty dict when bpod is None."""
        # Arrange
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Act
        result = discover_bpod_files(session_dir, None)

        # Assert
        assert result == {}

    def test_Should_RaiseIngestError_When_BpodConfiguredButNoFiles(self, tmp_path):
        """Should raise IngestError when bpod is configured but no files found."""
        # Arrange
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        bpod = BpodMeta(
            path="Bpod/*.mat",
            order="name_asc",
        )

        # Act & Assert
        with pytest.raises(IngestError, match="Failed to discover Bpod files"):
            discover_bpod_files(session_dir, bpod)


class TestDiscoverPoseFiles:
    """Tests for discover_pose_files pure function."""

    def test_Should_ReturnEmptyDict_When_Called(self, tmp_path):
        """Should return empty dict (stubbed for Phase 2 artifacts)."""
        # Arrange
        session_dir = tmp_path / "session"
        pose = PoseMeta()

        # Act
        result = discover_pose_files(session_dir, pose)

        # Assert
        assert result == {}


class TestDiscoverPoseModels:
    """Tests for discover_pose_models pure function."""

    def test_Should_DiscoverModels_When_ModelsExist(self, tmp_path):
        """Should discover model config files that exist."""
        # Arrange
        models_root = tmp_path / "models"
        model_dir = models_root / "dlc"
        model_dir.mkdir(parents=True)

        config_path = model_dir / "config.yaml"
        config_path.touch()

        models = {
            "dlc_cam0": PoseModelMeta(
                source="dlc",
                path="dlc/config.yaml",
            )
        }

        # Act
        result = discover_pose_models(models_root, models)

        # Assert
        assert "dlc_cam0" in result
        assert result["dlc_cam0"] == config_path

    def test_Should_WarnAndSkip_When_ModelsMissing(self, tmp_path, caplog):
        """Should warn and skip models that don't exist."""
        # Arrange
        models_root = tmp_path / "models"
        models_root.mkdir()

        models = {
            "dlc_missing": PoseModelMeta(
                source="dlc",
                path="missing/config.yaml",
            )
        }

        # Act
        with caplog.at_level(logging.WARNING):
            result = discover_pose_models(models_root, models)

        # Assert
        assert result == {}
        assert "not found" in caplog.text

    def test_Should_HandleMultipleModels_When_Called(self, tmp_path):
        """Should handle multiple models, including missing ones."""
        # Arrange
        models_root = tmp_path / "models"
        
        # Model 0 exists
        model0_dir = models_root / "dlc0"
        model0_dir.mkdir(parents=True)
        (model0_dir / "config.yaml").touch()

        # Model 1 missing
        models = {
            "dlc_cam0": PoseModelMeta(source="dlc", path="dlc0/config.yaml"),
            "dlc_cam1": PoseModelMeta(source="dlc", path="dlc1/config.yaml"),
        }

        # Act
        result = discover_pose_models(models_root, models)

        # Assert
        assert len(result) == 1
        assert "dlc_cam0" in result
        assert "dlc_cam1" not in result
