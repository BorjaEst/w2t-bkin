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
from w2t_bkin.ingest.kilosort import add_units_from_kilosort
from w2t_bkin.ingest.spikeglx import add_electrodes_from_spikeglx, parse_spikeglx_meta


class TestPhase1Integration:
    """Integration tests for Phase 1: Device and electrode creation."""

    @pytest.fixture
    def sample_meta_path(self):
        """Path to sample .meta fixture."""
        return Path(__file__).parent.parent / "fixtures/spikeglx/sample_np20.imec0.ap.meta"

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
            name="neuropixels_imec0",
            manufacturer="IMEC",
            description="Neuropixels 2.0 - Test probe for integration test",
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
            name="neuropixels_imec0",
            manufacturer="IMEC",
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
            name="neuropixels_imec1",
            manufacturer="IMEC",
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
            name="test_probe",
            manufacturer="IMEC",
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


class TestPhase2Integration:
    """Integration tests for Phase 2: Spike sorting ingestion."""

    @pytest.fixture
    def sample_meta_path(self):
        """Path to sample .meta fixture."""
        return Path(__file__).parent.parent / "fixtures/spikeglx/sample_np20.imec0.ap.meta"

    @pytest.fixture
    def kilosort_dir(self):
        """Path to sample Kilosort output directory."""
        return Path(__file__).parent.parent / "fixtures/kilosort"

    def test_phase2_end_to_end(self, tmp_path, sample_meta_path, kilosort_dir):
        """
        Test complete Phase 2 workflow:
        1. Create NWBFile
        2. Create Device (Phase 1)
        3. Add electrodes from .meta (Phase 1)
        4. Add units from Kilosort (Phase 2)
        5. Write to disk
        6. Read back and verify
        """
        # Create NWBFile
        nwbfile = NWBFile(
            session_description="Phase 2 integration test",
            identifier="phase2-test-001",
            session_start_time=datetime.now(tzlocal()),
            experimenter=["Test User"],
            lab="Test Lab",
            institution="Test Institution",
        )

        # Phase 1: Create device and electrodes
        device = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec0",
            manufacturer="IMEC",
            description="Neuropixels 2.0 probe",
        )

        n_electrodes = add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex, M1",
        )

        assert n_electrodes == 384

        # Phase 2: Add spike sorting results
        meta = parse_spikeglx_meta(sample_meta_path)
        sampling_rate = meta["sampling_rate"]

        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=kilosort_dir,
            probe_id="imec0",
            sampling_rate=sampling_rate,
            include_labels=["good", "mua"],
            min_spike_count=0,
            include_waveforms=True,
            include_metrics=True,
        )

        # Verify stats (12 good + 5 mua = 17 units)
        assert stats["n_units_added"] == 17
        assert stats["n_units_filtered"] == 3  # 3 noise units filtered
        assert stats["filter_reasons"]["quality_label"] == 3

        # Verify units table
        assert len(nwbfile.units) == 17
        assert "spike_times" in nwbfile.units.colnames
        assert "probe_id" in nwbfile.units.colnames
        assert "contamination_pct" in nwbfile.units.colnames
        assert "amplitude" in nwbfile.units.colnames
        assert "waveform_mean" in nwbfile.units.colnames

        # Write to disk
        nwb_path = tmp_path / "phase2_test.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        # Read back and verify
        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()

            # Verify Phase 1 components
            assert "neuropixels_imec0" in read_nwb.devices
            assert len(read_nwb.electrodes) == 384

            # Verify Phase 2 components
            assert read_nwb.units is not None
            assert len(read_nwb.units) == 17

            # Verify spike times are in seconds (not samples)
            first_unit_spikes = read_nwb.units["spike_times"][0]
            assert first_unit_spikes[0] < 100  # Should be in seconds, not samples

            # Verify quality metrics
            assert "contamination_pct" in read_nwb.units.colnames
            assert "amplitude" in read_nwb.units.colnames

            # Verify waveforms
            first_waveform = read_nwb.units["waveform_mean"][0]
            assert first_waveform.shape == (82, 32)  # n_samples x n_channels

    def test_phase2_quality_filtering(self, tmp_path, sample_meta_path, kilosort_dir):
        """
        Test Phase 2 with strict quality filtering (only 'good' units).
        """
        nwbfile = NWBFile(
            session_description="Phase 2 quality filtering test",
            identifier="phase2-test-002",
            session_start_time=datetime.now(tzlocal()),
        )

        # Phase 1: Setup
        device = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec0",
            manufacturer="IMEC",
        )

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex",
        )

        # Phase 2: Only include "good" units
        meta = parse_spikeglx_meta(sample_meta_path)

        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=kilosort_dir,
            probe_id="imec0",
            sampling_rate=meta["sampling_rate"],
            include_labels=["good"],  # Strict filtering
            min_spike_count=0,
            include_waveforms=False,
            include_metrics=True,
        )

        # Should only add 12 good units
        assert stats["n_units_added"] == 12
        assert stats["n_units_filtered"] == 8  # 5 mua + 3 noise filtered

        # Write and verify
        nwb_path = tmp_path / "phase2_quality_filter.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()
            assert len(read_nwb.units) == 12

    def test_phase2_spike_count_filtering(self, tmp_path, sample_meta_path, kilosort_dir):
        """
        Test Phase 2 with minimum spike count threshold.
        """
        nwbfile = NWBFile(
            session_description="Phase 2 spike count filtering test",
            identifier="phase2-test-003",
            session_start_time=datetime.now(tzlocal()),
        )

        # Phase 1: Setup
        device = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec0",
            manufacturer="IMEC",
        )

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device,
            probe_id="imec0",
            location="Motor Cortex",
        )

        # Phase 2: Set high spike count threshold
        meta = parse_spikeglx_meta(sample_meta_path)

        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=kilosort_dir,
            probe_id="imec0",
            sampling_rate=meta["sampling_rate"],
            include_labels=["good", "mua"],
            min_spike_count=500,  # High threshold - will filter low-firing units
            include_metrics=False,
        )

        # Some units should be filtered by spike count
        assert stats["n_units_added"] > 0
        assert stats["n_units_added"] < 17  # Less than without filtering
        assert stats["filter_reasons"]["spike_count"] > 0

        # Write and verify
        nwb_path = tmp_path / "phase2_spike_filter.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()
            assert len(read_nwb.units) == stats["n_units_added"]

    def test_phase2_multi_probe(self, tmp_path, sample_meta_path, kilosort_dir):
        """
        Test Phase 2 with multiple probes.
        Verifies unit probe_id tracking across probes.
        """
        nwbfile = NWBFile(
            session_description="Phase 2 multi-probe test",
            identifier="phase2-test-004",
            session_start_time=datetime.now(tzlocal()),
        )

        meta = parse_spikeglx_meta(sample_meta_path)

        # Add first probe (imec0)
        device0 = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec0",
            manufacturer="IMEC",
        )

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device0,
            probe_id="imec0",
            location="Motor Cortex",
        )

        stats0 = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=kilosort_dir,
            probe_id="imec0",
            sampling_rate=meta["sampling_rate"],
            include_labels=["good"],
            include_metrics=False,
        )

        # Add second probe (imec1) - reuse same fixture data
        device1 = create_device(
            nwbfile=nwbfile,
            name="neuropixels_imec1",
            manufacturer="IMEC",
        )

        add_electrodes_from_spikeglx(
            nwbfile=nwbfile,
            meta_path=sample_meta_path,
            device=device1,
            probe_id="imec1",
            location="Sensory Cortex",
        )

        stats1 = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=kilosort_dir,
            probe_id="imec1",
            sampling_rate=meta["sampling_rate"],
            include_labels=["good"],
            include_metrics=False,
        )

        # Verify both probes added units
        assert stats0["n_units_added"] == 12
        assert stats1["n_units_added"] == 12
        assert len(nwbfile.units) == 24

        # Write and verify
        nwb_path = tmp_path / "phase2_multi_probe.nwb"
        with NWBHDF5IO(str(nwb_path), mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(str(nwb_path), mode="r") as io:
            read_nwb = io.read()

            # Verify total units
            assert len(read_nwb.units) == 24

            # Verify probe_id tracking
            units_df = read_nwb.units.to_dataframe()
            imec0_units = units_df[units_df["probe_id"] == "imec0"]
            imec1_units = units_df[units_df["probe_id"] == "imec1"]

            assert len(imec0_units) == 12
            assert len(imec1_units) == 12
