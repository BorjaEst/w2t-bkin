"""Unit tests for NWB module (Phase 4 - Red Phase).

Tests NWB file assembly with Devices, ImageSeries, optional pose/facemap/bpod,
rate-based timing, provenance embedding, and external file links.

Requirements: FR-7, NFR-6, NFR-1, NFR-2
Acceptance: A1, A12
GitHub Issue: #5
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from w2t_bkin.domain import (
    AlignmentStats,
    BpodSummary,
    Config,
    FacemapBundle,
    Manifest,
    PoseBundle,
    Provenance,
)


class TestDeviceCreation:
    """Test Device creation from manifest cameras."""

    def test_Should_CreateDevice_When_CameraInManifest(self):
        """Should create NWB Device for each camera in manifest (FR-7)."""
        from w2t_bkin.nwb import create_device

        camera_metadata = {
            "camera_id": "cam0_top",
            "description": "Top view camera",
            "manufacturer": "FLIR",
        }

        device = create_device(camera_metadata)

        assert device is not None
        assert device["name"] == "cam0_top"
        assert device["description"] == "Top view camera"
        assert device["manufacturer"] == "FLIR"

    def test_Should_CreateMultipleDevices_When_MultipleCameras(self):
        """Should create Device for each camera in manifest."""
        from w2t_bkin.nwb import create_devices

        cameras = [
            {"camera_id": "cam0_top", "description": "Top view"},
            {"camera_id": "cam1_side", "description": "Side view"},
        ]

        devices = create_devices(cameras)

        assert len(devices) == 2
        assert devices[0]["name"] == "cam0_top"
        assert devices[1]["name"] == "cam1_side"


class TestImageSeriesCreation:
    """Test ImageSeries creation with external links and rate-based timing."""

    def test_Should_CreateImageSeries_When_VideoFileProvided(self):
        """Should create ImageSeries with external_file link (FR-7, A1)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
            "frame_count": 1000,
            "starting_time": 0.0,
        }

        image_series = create_image_series(video_metadata, device=None)

        assert image_series is not None
        assert image_series["name"] == "cam0_top"
        assert "/path/to/video.avi" in image_series["external_file"]

    def test_Should_UseRateBasedTiming_When_CreatingImageSeries(self):
        """Should use rate-based timing without per-frame timestamps (FR-7, NFR-6, A12)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
            "frame_count": 1000,
            "starting_time": 0.0,
        }

        image_series = create_image_series(video_metadata, device=None)

        # Verify rate-based timing (not per-frame timestamps)
        assert "rate" in image_series
        assert image_series["rate"] == 30.0
        assert "starting_time" in image_series
        assert image_series["starting_time"] == 0.0

    def test_Should_LinkExternalFile_When_CreatingImageSeries(self):
        """Should create external_file link instead of embedding video (FR-7)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
            "frame_count": 1000,
            "starting_time": 0.0,
        }

        image_series = create_image_series(video_metadata, device=None)

        # Verify external file link
        assert "external_file" in image_series
        assert isinstance(image_series["external_file"], list)
        assert len(image_series["external_file"]) > 0


class TestNWBFileAssembly:
    """Test complete NWB file assembly from manifest and bundles."""

    def test_Should_AssembleNWB_When_ManifestProvided(self, tmp_path):
        """Should assemble basic NWB file from manifest (FR-7, A1)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test-session"}
        config = {}
        provenance = {}

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance=provenance, output_dir=tmp_path)

        assert nwb_path is not None
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"

    def test_Should_IncludeAllCameras_When_AssemblingNWB(self, tmp_path):
        """Should include ImageSeries for all cameras in manifest (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {
            "session_id": "test-session",
            "cameras": [
                {"camera_id": "cam0_top", "video_path": "/fake/video1.avi", "frame_rate": 30.0},
                {"camera_id": "cam1_side", "video_path": "/fake/video2.avi", "frame_rate": 30.0},
            ],
        }

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Read and verify (using JSON stub for now)
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert len(data["image_series"]) == 2

    def test_Should_EmbedProvenance_When_AssemblingNWB(self, tmp_path):
        """Should embed provenance metadata in NWB file (NFR-11, A5)."""
        from w2t_bkin.nwb import assemble_nwb

        provenance = {
            "config_hash": "abc123",
            "session_hash": "def456",
            "timebase_source": "nominal_rate",
        }

        nwb_path = assemble_nwb(manifest={"session_id": "test"}, config={}, provenance=provenance, output_dir=tmp_path)

        # Verify provenance embedded
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "provenance" in data
        assert data["provenance"]["config_hash"] == "abc123"


class TestOptionalModalities:
    """Test NWB assembly with optional data modalities."""

    def test_Should_IncludeEvents_When_EventsProvided(self, tmp_path):
        """Should include behavioral events in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "events": {"trials": [{"start": 0.0, "end": 1.0}]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify events included
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "events" in data

    def test_Should_IncludePose_When_PoseProvided(self, tmp_path):
        """Should include pose data in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "pose": {"keypoints": ["nose", "tail"]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify pose included
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "pose" in data

    def test_Should_IncludeFacemap_When_FacemapProvided(self, tmp_path):
        """Should include facemap data in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "facemap": {"motion_energy": [0.1, 0.2, 0.3]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify facemap included
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "facemap" in data

    def test_Should_AssembleNWB_When_NoOptionalModalities(self, tmp_path):
        """Should assemble valid NWB with only required data (NFR-6)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test-minimal", "cameras": [{"camera_id": "cam0", "video_path": "/fake/video.avi", "frame_rate": 30.0}]}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        assert nwb_path.exists()

        # Verify minimal structure
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "session_id" in data
        assert len(data["image_series"]) == 1


class TestSessionMetadata:
    """Test session metadata integration into NWB."""

    def test_Should_IncludeSubjectInfo_When_Provided(self, tmp_path):
        """Should include subject metadata in NWB (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        session_metadata = {
            "subject_id": "mouse001",
            "sex": "M",
            "age": "P90",
            "genotype": "WT",
        }

        manifest = {"session_id": "test", "session_metadata": session_metadata}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify subject info included
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "session_metadata" in data
        assert data["session_metadata"]["subject_id"] == "mouse001"

    def test_Should_IncludeSessionDescription_When_Provided(self, tmp_path):
        """Should include session description from config template (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        config = {"nwb": {"session_description_template": "Session {session_id}", "lab": "Test Lab", "institution": "Test Institute"}}

        manifest = {"session_id": "test-123"}

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance={}, output_dir=tmp_path)

        # Verify session description
        import json

        with open(nwb_path, "r") as f:
            data = json.load(f)

        assert "config" in data
        assert data["config"]["nwb"]["lab"] == "Test Lab"


class TestErrorHandling:
    """Test error handling and validation."""

    def test_Should_RaiseError_When_MissingRequiredFields(self):
        """Should raise error when required fields missing in manifest."""
        from w2t_bkin.nwb import NWBError, assemble_nwb

        with pytest.raises(NWBError, match="required"):
            assemble_nwb(manifest=None, config={}, provenance={}, output_dir=Path("/tmp"))  # Missing manifest

    def test_Should_RaiseError_When_InvalidVideoPath(self):
        """Should raise error when video file doesn't exist."""
        from w2t_bkin.nwb import NWBError, assemble_nwb

        manifest = {"cameras": [{"camera_id": "cam0", "video_path": "/nonexistent/video.avi"}]}

        with pytest.raises(NWBError, match="not found|does not exist"):
            assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=Path("/tmp"))

    def test_Should_RaiseError_When_OutputDirNotWritable(self, tmp_path):
        """Should raise error when output directory not writable."""
        import os

        from w2t_bkin.nwb import NWBError, assemble_nwb

        # Create a non-writable directory within tmp_path
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        try:
            with pytest.raises((NWBError, PermissionError)):
                assemble_nwb(manifest={"session_id": "test"}, config={}, provenance={}, output_dir=readonly_dir)
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestDeterminism:
    """Test deterministic output for reproducibility (NFR-1)."""

    def test_Should_ProduceSameOutput_When_SameInputs(self, tmp_path):
        """Should produce identical NWB when inputs unchanged (NFR-1)."""
        import hashlib

        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "Session-000001"}
        config = {}
        provenance = {"config_hash": "abc123"}

        # Assemble twice
        nwb_path1 = assemble_nwb(manifest, config, provenance, tmp_path / "out1")
        nwb_path2 = assemble_nwb(manifest, config, provenance, tmp_path / "out2")

        # Should produce same output (deterministic container order)
        with open(nwb_path1, "rb") as f1:
            hash1 = hashlib.md5(f1.read()).hexdigest()

        with open(nwb_path2, "rb") as f2:
            hash2 = hashlib.md5(f2.read()).hexdigest()

        assert hash1 == hash2, "NWB output should be deterministic"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_manifest():
    """Mock manifest with basic camera data."""
    return {
        "session_id": "Session-000001",
        "cameras": [
            {
                "camera_id": "cam0_top",
                "description": "Top view camera",
                "video_path": "/path/to/video.avi",
                "frame_rate": 30.0,
                "frame_count": 1000,
            }
        ],
        "ttls": [],
    }


@pytest.fixture
def mock_config():
    """Mock config with NWB settings."""
    return {
        "nwb": {
            "link_external_video": True,
            "lab": "Test Lab",
            "institution": "Test Institution",
            "file_name_template": "{session_id}.nwb",
            "session_description_template": "Session {session_id}",
        }
    }


@pytest.fixture
def mock_provenance():
    """Mock provenance metadata."""
    return {
        "config_hash": "abc123def456",
        "session_hash": "789ghi012jkl",
        "software": {
            "name": "w2t_bkin",
            "version": "0.1.0",
            "python_version": "3.10.0",
        },
        "timebase": {
            "source": "nominal_rate",
            "mapping": "nearest",
            "offset_s": 0.0,
        },
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def mock_pose_bundle():
    """Mock pose bundle for testing."""
    return None  # Will be implemented with pose domain model


@pytest.fixture
def mock_facemap_bundle():
    """Mock facemap bundle for testing."""
    return None  # Will be implemented with facemap domain model


@pytest.fixture
def mock_bpod_summary():
    """Mock Bpod summary for testing."""
    return None  # Will be implemented with events domain model
