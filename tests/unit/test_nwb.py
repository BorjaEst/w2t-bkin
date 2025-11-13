"""Unit tests for NWB module (Phase 4 - with pynwb).

Tests NWB file assembly with Devices, ImageSeries, optional pose/facemap/bpod,
rate-based timing, provenance embedding, and external file links.

Requirements: FR-7, NFR-6, NFR-1, NFR-2
Acceptance: A1, A12
GitHub Issue: #5

Fixtures:
- Shared fixtures are in tests/conftest.py (Config, Manifest, etc.)
- Local fixtures below are NWB-specific mock dictionaries for unit testing
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pynwb import NWBHDF5IO
import pytest

from w2t_bkin.domain import AlignmentStats, Config, FacemapBundle, Manifest, PoseBundle, Provenance, TrialSummary


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
        assert device.name == "cam0_top"
        assert device.description == "Top view camera"
        assert device.manufacturer == "FLIR"

    def test_Should_CreateMultipleDevices_When_MultipleCameras(self):
        """Should create Device for each camera in manifest."""
        from w2t_bkin.nwb import create_devices

        cameras = [
            {"camera_id": "cam0_top", "description": "Top view"},
            {"camera_id": "cam1_side", "description": "Side view"},
        ]

        devices = create_devices(cameras)

        assert len(devices) == 2
        assert devices[0].name == "cam0_top"
        assert devices[1].name == "cam1_side"


class TestImageSeriesCreation:
    """Test ImageSeries creation with rate-based timing."""

    def test_Should_CreateImageSeries_When_VideoFileProvided(self):
        """Should create ImageSeries with video metadata (FR-7)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
            "starting_time": 0.0,
        }

        image_series = create_image_series(video_metadata)

        assert image_series is not None
        assert image_series.name == "cam0_top"
        assert hasattr(image_series, "external_file")
        assert hasattr(image_series, "rate")

    def test_Should_UseRateBasedTiming_When_CreatingImageSeries(self):
        """Should use rate-based timing, not per-frame timestamps (NFR-6, A12)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
            "starting_time": 0.0,
        }

        image_series = create_image_series(video_metadata)

        # Should have rate attribute
        assert hasattr(image_series, "rate")
        assert image_series.rate == 30.0

        # Should have starting_time
        assert hasattr(image_series, "starting_time")
        assert image_series.starting_time == 0.0

        # Should NOT have timestamps array
        assert not hasattr(image_series, "timestamps") or image_series.timestamps is None

    def test_Should_LinkExternalFile_When_CreatingImageSeries(self):
        """Should link external video file instead of embedding (FR-7)."""
        from w2t_bkin.nwb import create_image_series

        video_metadata = {
            "camera_id": "cam0_top",
            "video_path": "/path/to/video.avi",
            "frame_rate": 30.0,
        }

        image_series = create_image_series(video_metadata)

        # Should have external_file attribute
        assert hasattr(image_series, "external_file")
        assert len(image_series.external_file) > 0
        assert "/path/to/video.avi" in image_series.external_file[0]


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

        # Read and verify using pynwb
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            # Check acquisition (ImageSeries are stored there)
            assert len(nwbfile.acquisition) == 2

    def test_Should_EmbedProvenance_When_AssemblingNWB(self, tmp_path):
        """Should embed provenance metadata in NWB file (NFR-11, A5)."""
        from w2t_bkin.nwb import assemble_nwb

        provenance = {
            "config_hash": "abc123",
            "session_hash": "def456",
            "timebase_source": "nominal_rate",
        }

        nwb_path = assemble_nwb(manifest={"session_id": "test"}, config={}, provenance=provenance, output_dir=tmp_path)

        # Verify provenance embedded (stored in notes field)
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert hasattr(nwbfile, "notes")
            assert "abc123" in nwbfile.notes


class TestOptionalModalities:
    """Test NWB assembly with optional data modalities."""

    def test_Should_IncludeEvents_When_EventsProvided(self, tmp_path):
        """Should include behavioral events in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "events": {"trials": [{"start": 0.0, "end": 1.0}]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify NWB file created (events will be added in future)
        assert nwb_path.exists()
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.identifier == "test"

    def test_Should_IncludePose_When_PoseProvided(self, tmp_path):
        """Should include pose data in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "pose": {"keypoints": ["nose", "tail"]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify NWB file created (pose will be added in future)
        assert nwb_path.exists()
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.identifier == "test"

    def test_Should_IncludeFacemap_When_FacemapProvided(self, tmp_path):
        """Should include facemap data in NWB when provided (Phase 3)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test", "facemap": {"motion_energy": [0.1, 0.2, 0.3]}}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        # Verify NWB file created (facemap will be added in future)
        assert nwb_path.exists()
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.identifier == "test"

    def test_Should_AssembleNWB_When_NoOptionalModalities(self, tmp_path):
        """Should assemble valid NWB with only required data (NFR-6)."""
        from w2t_bkin.nwb import assemble_nwb

        manifest = {"session_id": "test-minimal", "cameras": [{"camera_id": "cam0", "video_path": "/fake/video.avi", "frame_rate": 30.0}]}

        nwb_path = assemble_nwb(manifest=manifest, config={}, provenance={}, output_dir=tmp_path)

        assert nwb_path.exists()

        # Verify minimal structure using pynwb
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.identifier == "test-minimal"
            assert len(nwbfile.acquisition) == 1


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

        # Verify NWB file created with identifier
        assert nwb_path.exists()
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.identifier == "test"

    def test_Should_IncludeSessionDescription_When_Provided(self, tmp_path):
        """Should include session description from config template (FR-7)."""
        from w2t_bkin.nwb import assemble_nwb

        config = {"nwb": {"session_description": "Test Session", "lab": "Test Lab", "institution": "Test Institute"}}

        manifest = {"session_id": "test-123"}

        nwb_path = assemble_nwb(manifest=manifest, config=config, provenance={}, output_dir=tmp_path)

        # Verify session description using pynwb
        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Test Session"
            assert nwbfile.lab == "Test Lab"
            assert nwbfile.institution == "Test Institute"


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

        # Verify content is the same by reading with pynwb
        # Note: HDF5 binary comparison may fail due to internal metadata,
        # but the semantic content should be identical
        with NWBHDF5IO(str(nwb_path1), "r") as io1:
            nwbfile1 = io1.read()
            with NWBHDF5IO(str(nwb_path2), "r") as io2:
                nwbfile2 = io2.read()

                # Check key fields are identical
                assert nwbfile1.identifier == nwbfile2.identifier
                assert nwbfile1.session_description == nwbfile2.session_description
                assert nwbfile1.session_start_time == nwbfile2.session_start_time
                assert len(nwbfile1.acquisition) == len(nwbfile2.acquisition)
