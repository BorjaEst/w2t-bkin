"""
Unit tests for SpikeGLX hardware ingestion.

Tests SpikeGLX metadata parsing and electrode table population.
"""

from datetime import datetime
from pathlib import Path

from dateutil.tz import tzlocal
from pynwb import NWBFile
import pytest

from w2t_bkin.ingest.ecephys import create_device
from w2t_bkin.ingest.spikeglx import add_electrodes_from_spikeglx, parse_spikeglx_meta


class TestCreateNeuropixelsDevice:
    """Test Device creation for Neuropixels probes."""

    @pytest.fixture
    def nwbfile(self):
        """Create a minimal NWBFile for testing."""
        return NWBFile(
            session_description="test session",
            identifier="test-001",
            session_start_time=datetime.now(tzlocal()),
        )

    def test_create_device_basic(self, nwbfile):
        """Test creating a device with default parameters."""
        device = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec0",
            manufacturer="IMEC",
        )

        assert device.name == "neuropixels_imec0"
        assert device.manufacturer == "IMEC"

    def test_create_device_custom_params(self, nwbfile):
        """Test creating a device with custom parameters."""
        device = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec1",
            manufacturer="IMEC",
            description="Neuropixels 1.0 - Custom probe description",
        )

        assert device.name == "neuropixels_imec1"
        assert device.manufacturer == "IMEC"
        assert "Custom probe description" in device.description

    def test_create_duplicate_device(self, nwbfile):
        """Test error when creating duplicate device."""
        create_device(nwbfile, "probe1")

        with pytest.raises(ValueError, match="already exists"):
            create_device(nwbfile, "probe1")

    def test_device_added_to_nwbfile(self, nwbfile):
        """Test that device is added to nwbfile.devices."""
        device = create_device(nwbfile, "test_probe")

        assert "test_probe" in nwbfile.devices
        assert nwbfile.devices["test_probe"] is device


class TestAddElectrodesFromMeta:
    """Test electrodes table population from .meta file."""

    @pytest.fixture
    def nwbfile(self):
        """Create NWBFile with a device."""
        nwb = NWBFile(
            session_description="test session",
            identifier="test-002",
            session_start_time=datetime.now(tzlocal()),
        )
        create_device(nwb, "neuropixels_imec0")
        return nwb

    @pytest.fixture
    def sample_meta_path(self):
        """Path to sample .meta fixture."""
        return Path(__file__).parent.parent / "fixtures/ecephys/sample_np20.imec0.ap.meta"

    def test_add_electrodes_basic(self, nwbfile, sample_meta_path):
        """Test adding electrodes from .meta file."""
        device = nwbfile.devices["neuropixels_imec0"]

        n_added = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex, M1",
        )

        assert n_added == 384
        assert len(nwbfile.electrodes) == 384

    def test_electrodes_have_correct_attributes(self, nwbfile, sample_meta_path):
        """Test that electrodes have correct attributes."""
        device = nwbfile.devices["neuropixels_imec0"]

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex, M1",
        )

        # Check electrodes table structure
        assert "filtering" in nwbfile.electrodes.colnames
        assert "location" in nwbfile.electrodes.colnames

        # Check first electrode via DataFrame
        df = nwbfile.electrodes.to_dataframe()
        assert df.iloc[0]["location"] == "Motor Cortex, M1"

    def test_electrode_group_created(self, nwbfile, sample_meta_path):
        """Test that ElectrodeGroup is created."""
        device = nwbfile.devices["neuropixels_imec0"]

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
        )

        # Check electrode group exists
        assert "probe_imec0" in nwbfile.electrode_groups

    def test_custom_group_name(self, nwbfile, sample_meta_path):
        """Test custom electrode group name."""
        device = nwbfile.devices["neuropixels_imec0"]

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            group_name="custom_group",
        )

        assert "custom_group" in nwbfile.electrode_groups

    def test_multiple_probes_unique_ids(self, sample_meta_path):
        """Test that electrode IDs are unique across multiple probes."""
        nwb = NWBFile(
            session_description="multi-probe test",
            identifier="test-003",
            session_start_time=datetime.now(tzlocal()),
        )

        # Add two probes
        device0 = create_device(nwb, "neuropixels_imec0")
        device1 = create_device(nwb, "neuropixels_imec1")

        add_electrodes_from_spikeglx(nwb, sample_meta_path, device0, "imec0")
        add_electrodes_from_spikeglx(nwb, sample_meta_path, device1, "imec1")

        # Should have 384 * 2 = 768 electrodes with unique IDs
        assert len(nwb.electrodes) == 768

        # Check that electrode IDs are sequential and unique
        electrode_ids = [row.index for row in nwb.electrodes.to_dataframe().itertuples()]
        assert len(set(electrode_ids)) == 768  # All unique

    def test_missing_meta_file(self, nwbfile):
        """Test error handling for missing .meta file."""
        device = nwbfile.devices["neuropixels_imec0"]

        with pytest.raises(FileNotFoundError):
            add_electrodes_from_spikeglx(
                nwbfile=nwbfile,
                meta_path=Path("/nonexistent/file.meta"),
                device=device,
                probe_id="imec0",
            )
