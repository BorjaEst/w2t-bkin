"""
Integration test for Phase 1: Ecephys Foundation.

Tests end-to-end device and electrode creation from .meta file.
"""

from datetime import datetime
from pathlib import Path

from dateutil.tz import tzlocal
from pynwb import NWBHDF5IO, NWBFile
import pytest

from w2t_bkin.ingest.ecephys import create_device
from w2t_bkin.ingest.spikeglx import add_electrodes_from_spikeglx


class TestPhase1Integration:
    """Integration tests for Phase 1: Device and electrode creation."""

    @pytest.fixture
    def sample_meta_path(self):
        """Path to sample .meta fixture."""
        return Path(__file__).parent.parent / "fixtures/ecephys/sample_np20.imec0.ap.meta"

    def test_phase1_end_to_end(self, tmp_path, sample_meta_path):
        """
        Test complete Phase 1 workflow:
        1. Create NWBFile
        2. Create Device
        3. Add electrodes from .meta
        4. Write to disk
        5. Read back and verify
        """
        # Create NWBFile
        nwbfile = NWBFile(
            session_description="Phase 1 integration test",
            identifier="phase1-test-001",
            session_start_time=datetime.now(tzlocal()),
            experimenter=["Test User"],
            lab="Test Lab",
            institution="Test Institution",
        )

        # Create device
        device = create_device(
            nwbfile=nwbfile,
            device_name="neuropixels_imec0",
            manufacturer="IMEC",
            model_name="Neuropixels 2.0",
            description="Test probe for integration test",
        )

        assert device.name == "neuropixels_imec0"

        # Add electrodes from .meta
        n_added = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex, M1",
        )

        assert n_added == 384
        assert len(nwbfile.electrodes) == 384

        # Write to disk
        nwb_path = tmp_path / "phase1_test.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        # Read back and verify
        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()

            # Verify device
            assert "neuropixels_imec0" in read_nwb.devices
            device = read_nwb.devices["neuropixels_imec0"]
            assert device.manufacturer == "IMEC"

            # Verify electrodes
            assert len(read_nwb.electrodes) == 384

            # Verify electrode group
            assert "probe_imec0" in read_nwb.electrode_groups

            # Verify electrodes table structure
            df = read_nwb.electrodes.to_dataframe()
            assert "location" in df.columns
            assert "filtering" in df.columns
            assert df.iloc[0]["location"] == "Motor Cortex, M1"

    def test_phase1_multi_probe(self, tmp_path, sample_meta_path):
        """
        Test Phase 1 with multiple probes.
        Verifies electrode ID uniqueness across probes.
        """
        nwbfile = NWBFile(
            session_description="Multi-probe integration test",
            identifier="phase1-test-002",
            session_start_time=datetime.now(tzlocal()),
        )

        # Add first probe
        device0 = create_device(
            nwbfile=nwbfile,
            device_name="neuropixels_imec0",
        )

        n_added0 = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device0,
            probe_id="imec0",
            location="Motor Cortex, M1",
        )

        # Add second probe
        device1 = create_device(
            nwbfile=nwbfile,
            device_name="neuropixels_imec1",
        )

        n_added1 = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device1,
            probe_id="imec1",
            location="Sensory Cortex, S1",
        )

        # Verify total electrodes
        assert n_added0 == 384
        assert n_added1 == 384
        assert len(nwbfile.electrodes) == 768

        # Write and read back
        nwb_path = tmp_path / "phase1_multi_probe.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()

            # Verify both devices
            assert "neuropixels_imec0" in read_nwb.devices
            assert "neuropixels_imec1" in read_nwb.devices

            # Verify both electrode groups
            assert "probe_imec0" in read_nwb.electrode_groups
            assert "probe_imec1" in read_nwb.electrode_groups

            # Verify electrode count
            assert len(read_nwb.electrodes) == 768

            # Verify electrode IDs are unique
            df = read_nwb.electrodes.to_dataframe()
            assert len(df.index.unique()) == 768

    def test_phase1_minimal_workflow(self, tmp_path, sample_meta_path):
        """
        Test minimal Phase 1 workflow with default parameters.
        """
        nwbfile = NWBFile(
            session_description="Minimal test",
            identifier="phase1-test-003",
            session_start_time=datetime.now(tzlocal()),
        )

        # Use all defaults
        device = create_device(
            nwbfile=nwbfile,
            device_name="test_probe",
        )

        n_added = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="test",
        )

        assert n_added == 384

        # Write to disk
        nwb_path = tmp_path / "phase1_minimal.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        # Verify file is valid and readable
        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()
            assert len(read_nwb.electrodes) == 384
