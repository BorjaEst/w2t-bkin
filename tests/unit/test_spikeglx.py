"""
Unit tests for SpikeGLX hardware ingestion.

Tests SpikeGLX metadata parsing and electrode table population.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dateutil.tz import tzlocal
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup
import pytest

from w2t_bkin.ingest.spikeglx import build_device_from_meta, build_electrode_group_from_meta, build_electrodes_table_from_meta, parse_spikeglx_meta


class TestSpikeGLXIngest:
    """Test NWB object creation from SpikeGLX metadata."""

    @pytest.fixture
    def mock_meta(self) -> Dict[str, Any]:
        """Create a mock parsed metadata dictionary."""
        return {
            "sampling_rate": 30000.0,
            "n_channels": 4,  # Small number for testing
            "probe_type": "0",  # Neuropixels 1.0
            "geometry": [(0.0, 0.0), (32.0, 0.0), (0.0, 20.0), (32.0, 20.0)],
            "filtering": "AP band: 300Hz high-pass",
            "file_size_bytes": 1000000,
        }

    @pytest.fixture
    def nwbfile(self):
        """Create a minimal NWBFile for testing."""
        return NWBFile(
            session_description="test session",
            identifier="test-001",
            session_start_time=datetime.now(tzlocal()),
        )

    def test_build_device_from_meta(self, mock_meta):
        """Test creating a Device object from metadata."""
        device = build_device_from_meta(mock_meta, "imec0")

        assert isinstance(device, Device)
        assert device.name == "neuropixels_imec0"
        assert device.manufacturer == "IMEC"
        assert "Neuropixels 1.0" in device.description

    def test_build_device_unknown_probe_type(self, mock_meta):
        """Test device creation with unknown probe type."""
        mock_meta["probe_type"] = "9999"
        device = build_device_from_meta(mock_meta, "imec1")

        assert device.name == "neuropixels_imec1"
        assert "type 9999" in device.description

    def test_build_electrode_group_from_meta(self, mock_meta):
        """Test creating an ElectrodeGroup from metadata."""
        device = build_device_from_meta(mock_meta, "imec0")

        group = build_electrode_group_from_meta(
            name="probe_imec0",
            device=device,
            location="Motor Cortex",
            meta=mock_meta,
        )

        assert isinstance(group, ElectrodeGroup)
        assert group.name == "probe_imec0"
        assert group.device is device
        assert group.location == "Motor Cortex"
        assert "neuropixels_imec0" in group.description
        assert "4 channels" in group.description

    def test_build_electrodes_table_from_meta(self, mock_meta):
        """Test creating electrode table rows from metadata."""
        device = build_device_from_meta(mock_meta, "imec0")
        group = build_electrode_group_from_meta(
            name="probe_imec0",
            device=device,
            location="Motor Cortex",
            meta=mock_meta,
        )

        rows = build_electrodes_table_from_meta(mock_meta, group, "Motor Cortex")

        assert len(rows) == 4  # Matches n_channels/geometry length

        # Check first row
        row0 = rows[0]
        assert row0["x"] == 0.0
        assert row0["y"] == 0.0
        assert row0["z"] == 0.0
        assert row0["group"] is group
        assert row0["location"] == "Motor Cortex"
        assert row0["filtering"] == mock_meta["filtering"]

        # Check second row
        row1 = rows[1]
        assert row1["x"] == 32.0
        assert row1["y"] == 0.0
        assert row1["z"] == 0.0

    def test_integration_with_nwbfile(self, nwbfile, mock_meta):
        """Test adding created objects to an NWBFile."""
        # 1. Create Device
        device = build_device_from_meta(mock_meta, "imec0")
        nwbfile.add_device(device)
        assert "neuropixels_imec0" in nwbfile.devices

        # 2. Create ElectrodeGroup
        group = build_electrode_group_from_meta(
            name="probe_imec0",
            device=device,
            location="Striatum",
            meta=mock_meta,
        )
        nwbfile.create_electrode_group(
            name=group.name,
            description=group.description,
            location=group.location,
            device=group.device,
        )
        assert "probe_imec0" in nwbfile.electrode_groups

        # 3. Add Electrodes
        rows = build_electrodes_table_from_meta(mock_meta, group, "Striatum")
        for row in rows:
            nwbfile.add_electrode(**row)

        assert len(nwbfile.electrodes) == 4
        assert nwbfile.electrodes[0, "location"] == "Striatum"
