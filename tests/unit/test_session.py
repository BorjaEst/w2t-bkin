"""Unit tests for session metadata loading and NWBFile creation."""

from datetime import datetime
from pathlib import Path

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.file import Subject
import pytest

from w2t_bkin.session import create_device, create_nwb_file, create_subject, load_metadata
from w2t_bkin.utils import parse_datetime


class TestParseDateTime:
    """Test datetime parsing functionality."""

    def test_parse_iso8601_with_t(self):
        """Test parsing ISO 8601 format with T separator."""
        dt = parse_datetime("2025-01-15T14:30:00")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30

    def test_parse_iso8601_with_space(self):
        """Test parsing ISO 8601 format with space separator."""
        dt = parse_datetime("2025-01-15 14:30:00")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_invalid_format(self):
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError, match="Invalid datetime format"):
            parse_datetime("invalid-date")


class TestCreateSubject:
    """Test Subject object creation."""

    def test_create_subject_minimal(self):
        """Test creating subject with minimal data."""
        data = {"subject_id": "M001"}
        subject = create_subject(data)

        assert isinstance(subject, Subject)
        assert subject.subject_id == "M001"

    def test_create_subject_full(self):
        """Test creating subject with full metadata."""
        data = {
            "subject_id": "M001",
            "species": "Mus musculus",
            "sex": "M",
            "age": "P84D",
            "age__reference": "birth",
            "genotype": "C57BL/6J wild-type",
            "strain": "C57BL/6J",
            "weight": "0.025 kg",
            "description": "Adult male mouse",
            "date_of_birth": "2024-10-23T00:00:00",
        }
        subject = create_subject(data)

        assert subject.subject_id == "M001"
        assert subject.species == "Mus musculus"
        assert subject.sex == "M"
        assert subject.age == "P84D"
        assert subject.strain == "C57BL/6J"
        assert subject.date_of_birth is not None


class TestCreateDevices:
    """Test Device creation."""

    def test_create_device_minimal(self):
        """Test creating device with minimal data."""
        device_data = {"name": "camera_0", "description": "Overhead camera"}
        device = create_device(device_data)

        assert isinstance(device, Device)
        assert device.name == "camera_0"

    def test_create_device_full(self):
        """Test creating device with full metadata."""
        device_data = {
            "name": "camera_0",
            "description": "High-speed camera",
            "manufacturer": "FLIR",
            "serial_number": "12345678",
            "model": {
                "model_name": "Blackfly S",
                "manufacturer": "FLIR",
                "model_number": "BFS-U3-04S2M",
            },
        }
        device = create_device(device_data)

        assert device.description == "High-speed camera"
        assert device.manufacturer == "FLIR"
        assert device.serial_number == "12345678"
        assert device.model is not None

    def test_create_multiple_devices(self):
        """Test creating multiple devices in NWBFile."""
        metadata = {
            "identifier": "TEST-001",
            "session_description": "Test session",
            "session_start_time": "2025-01-15T14:30:00",
            "devices": [
                {"name": "camera_0", "description": "Camera 0"},
                {"name": "camera_1", "description": "Camera 1"},
                {"name": "bpod", "description": "Behavioral control"},
            ],
        }
        nwbfile = create_nwb_file(metadata)

        assert len(nwbfile.devices) == 3
        assert "camera_0" in nwbfile.devices
        assert "camera_1" in nwbfile.devices
        assert "bpod" in nwbfile.devices


class TestLoadSessionMetadata:
    """Test session metadata loading from TOML."""

    def test_load_session_metadata(self):
        """Test loading valid metadata.toml file."""
        session_path = Path("data/raw/Session-000001/metadata.toml")

        if not session_path.exists():
            pytest.skip("Session file not found")

        metadata = load_metadata(session_path)

        assert isinstance(metadata, dict)
        assert "identifier" in metadata
        assert "session_description" in metadata
        assert "session_start_time" in metadata

    def test_load_nonexistent_file(self):
        """Test that loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_metadata("nonexistent/metadata.toml")


class TestCreateNWBFile:
    """Test NWBFile creation from session metadata."""

    def test_create_nwb_from_metadata_loaded_from_path(self):
        """Test creating NWBFile from metadata loaded from path."""
        session_path = Path("data/raw/Session-000001/metadata.toml")

        if not session_path.exists():
            pytest.skip("Session file not found")

        metadata = load_metadata(session_path)
        nwbfile = create_nwb_file(metadata)

        assert isinstance(nwbfile, NWBFile)
        assert nwbfile.identifier == "Session-000001"
        assert nwbfile.session_description
        assert nwbfile.session_start_time

    def test_create_nwb_from_dict(self):
        """Test creating NWBFile from metadata dict."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
        }

        nwbfile = create_nwb_file(metadata)

        assert isinstance(nwbfile, NWBFile)
        assert nwbfile.identifier == "TEST-001"
        assert nwbfile.session_description == "Test session"

    def test_create_nwb_with_subject(self):
        """Test NWBFile creation includes subject."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
            "subject": {
                "subject_id": "M001",
                "species": "Mus musculus",
                "sex": "M",
            },
        }

        nwbfile = create_nwb_file(metadata)

        assert nwbfile.subject is not None
        assert nwbfile.subject.subject_id == "M001"
        assert nwbfile.subject.species == "Mus musculus"

    def test_create_nwb_with_devices(self):
        """Test NWBFile creation includes devices."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
            "devices": [{"name": "camera_0", "description": "Test camera"}],
        }

        nwbfile = create_nwb_file(metadata)

        assert len(nwbfile.devices) == 1
        assert "camera_0" in nwbfile.devices

    def test_create_nwb_without_devices(self):
        """Test NWBFile creation when devices are not provided."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
            # No devices key
        }

        nwbfile = create_nwb_file(metadata)

        assert len(nwbfile.devices) == 0

    def test_create_nwb_with_optional_metadata(self):
        """Test NWBFile with optional metadata fields."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
            "session_id": "S001",
            "experimenter": ["Borja Esteban"],
            "institution": "Test University",
            "lab": "Test Lab",
            "keywords": ["test", "nwb"],
            "protocol": "TEST-PROTOCOL",
        }

        nwbfile = create_nwb_file(metadata)

        assert nwbfile.session_id == "S001"
        assert nwbfile.experimenter == ["Borja Esteban"]
        assert nwbfile.institution == "Test University"
        assert nwbfile.lab == "Test Lab"
        assert nwbfile.keywords == ["test", "nwb"]
        assert nwbfile.protocol == "TEST-PROTOCOL"


class TestNWBFileMetadata:
    """Test NWBFile metadata access."""

    def test_nwbfile_has_metadata(self):
        """Test that NWBFile contains expected metadata."""
        metadata = {
            "session_description": "Test session",
            "identifier": "TEST-001",
            "session_start_time": "2025-01-15T14:30:00",
            "session_id": "S001",
            "subject": {
                "subject_id": "M001",
                "species": "Mus musculus",
                "sex": "M",
            },
            "devices": [{"name": "camera_0", "description": "Test camera"}],
        }

        nwbfile = create_nwb_file(metadata)

        assert nwbfile.identifier == "TEST-001"
        assert nwbfile.session_id == "S001"
        assert nwbfile.subject is not None
        assert nwbfile.subject.subject_id == "M001"
        assert len(nwbfile.devices) == 1
        assert "camera_0" in nwbfile.devices


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow(self):
        """Test complete workflow from file to NWBFile."""
        session_path = Path("data/raw/Session-000001/metadata.toml")

        if not session_path.exists():
            pytest.skip("Session file not found")

        # Load metadata
        metadata = load_metadata(session_path)
        assert metadata

        # Create NWBFile
        nwbfile = create_nwb_file(metadata)
        assert nwbfile

        # Verify key fields
        assert nwbfile.identifier
        assert nwbfile.session_start_time
        assert len(nwbfile.devices) > 0
