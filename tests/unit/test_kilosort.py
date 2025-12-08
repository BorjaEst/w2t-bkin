"""Unit tests for Kilosort spike sorting ingestion module."""

from datetime import datetime
from pathlib import Path

from dateutil.tz import tzlocal
import numpy as np
import pandas as pd
from pynwb import NWBFile
import pytest

from w2t_bkin.ingest.kilosort import add_units_from_kilosort, load_cluster_labels, load_cluster_metrics, load_kilosort_data

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_kilosort_dir(tmp_path):
    """Create a temporary Kilosort output directory with sample data."""
    sorting_dir = tmp_path / "kilosort_output"
    sorting_dir.mkdir()

    # Create spike_times.npy (10k spikes, sample indices)
    spike_times = np.random.randint(0, 1_000_000, size=10_000, dtype=np.int64)
    np.save(sorting_dir / "spike_times.npy", spike_times)

    # Create spike_clusters.npy (10 clusters, 0-9)
    spike_clusters = np.random.randint(0, 10, size=10_000, dtype=np.int32)
    np.save(sorting_dir / "spike_clusters.npy", spike_clusters)

    # Create templates.npy (10 clusters, 82 samples, 384 channels)
    templates = np.random.randn(10, 82, 384).astype(np.float32)
    np.save(sorting_dir / "templates.npy", templates)

    # Create cluster_info.tsv
    cluster_info = pd.DataFrame(
        {
            "cluster_id": range(10),
            "KSLabel": ["good"] * 5 + ["mua"] * 3 + ["noise"] * 2,
            "ch": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "ContamPct": np.random.rand(10) * 0.2,
            "Amplitude": np.random.rand(10) * 100,
        }
    )
    cluster_info.to_csv(sorting_dir / "cluster_info.tsv", sep="\t", index=False)

    return sorting_dir


@pytest.fixture
def nwbfile():
    """Create a minimal NWBFile for testing."""
    nwbfile = NWBFile(
        session_description="test session",
        identifier="test-001",
        session_start_time=datetime.now(tzlocal()),
    )
    return nwbfile


@pytest.fixture
def nwbfile_with_electrodes(nwbfile):
    """Create NWBFile with device and electrodes."""
    from w2t_bkin.ingest.ecephys import create_device, create_electrode_group

    # Create device
    device = create_device(
        nwbfile=nwbfile,
        name="neuropixels_imec0",
        manufacturer="IMEC",
        description="Neuropixels 2.0",
    )

    # Create electrode group
    group = create_electrode_group(
        nwbfile=nwbfile,
        name="probe_imec0",
        description="Neuropixels probe",
        location="Motor Cortex",
        device=device,
    )

    # Add 384 electrodes
    for i in range(384):
        nwbfile.add_electrode(
            id=i,
            x=float(i % 2 * 32),
            y=float(i // 2 * 15),
            z=0.0,
            imp=-1.0,
            location="Motor Cortex",
            filtering="AP band: 300-10000 Hz",
            group=group,
        )

    return nwbfile


# ============================================================================
# Test load_kilosort_data()
# ============================================================================


class TestLoadKilosortData:
    """Tests for load_kilosort_data()."""

    def test_load_basic(self, sample_kilosort_dir):
        """Test loading basic Kilosort files."""
        data = load_kilosort_data(sample_kilosort_dir)

        assert "spike_times" in data
        assert "spike_clusters" in data
        assert "templates" in data

        assert data["spike_times"].shape == (10_000,)
        assert data["spike_clusters"].shape == (10_000,)
        assert data["templates"].shape == (10, 82, 384)

    def test_missing_spike_times(self, tmp_path):
        """Test error when spike_times.npy missing."""
        sorting_dir = tmp_path / "incomplete"
        sorting_dir.mkdir()

        # Only create spike_clusters.npy
        np.save(sorting_dir / "spike_clusters.npy", np.array([0, 1, 2]))

        with pytest.raises(FileNotFoundError, match="spike_times.npy"):
            load_kilosort_data(sorting_dir)

    def test_missing_spike_clusters(self, tmp_path):
        """Test error when spike_clusters.npy missing."""
        sorting_dir = tmp_path / "incomplete"
        sorting_dir.mkdir()

        # Only create spike_times.npy
        np.save(sorting_dir / "spike_times.npy", np.array([100, 200, 300]))

        with pytest.raises(FileNotFoundError, match="spike_clusters.npy"):
            load_kilosort_data(sorting_dir)

    def test_optional_templates(self, tmp_path):
        """Test loading without templates.npy (optional file)."""
        sorting_dir = tmp_path / "no_templates"
        sorting_dir.mkdir()

        np.save(sorting_dir / "spike_times.npy", np.array([100, 200, 300]))
        np.save(sorting_dir / "spike_clusters.npy", np.array([0, 1, 0]))

        data = load_kilosort_data(sorting_dir)

        assert data["templates"] is None
        assert data["spike_times"] is not None
        assert data["spike_clusters"] is not None


# ============================================================================
# Test load_cluster_labels()
# ============================================================================


class TestLoadClusterLabels:
    """Tests for load_cluster_labels()."""

    def test_load_cluster_info(self, sample_kilosort_dir):
        """Test loading cluster_info.tsv."""
        labels = load_cluster_labels(sample_kilosort_dir)

        assert "cluster_id" in labels.columns
        assert "KSLabel" in labels.columns
        assert len(labels) == 10

        good_units = labels[labels["KSLabel"] == "good"]
        assert len(good_units) == 5

    def test_missing_label_files(self, tmp_path):
        """Test error when no cluster label file found."""
        sorting_dir = tmp_path / "no_labels"
        sorting_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="No cluster label file"):
            load_cluster_labels(sorting_dir)

    def test_ks_label_fallback(self, tmp_path):
        """Test fallback to cluster_KSLabel.tsv."""
        sorting_dir = tmp_path / "ks_label"
        sorting_dir.mkdir()

        ks_label_df = pd.DataFrame(
            {
                "cluster_id": [0, 1, 2],
                "KSLabel": ["good", "mua", "noise"],
            }
        )
        ks_label_df.to_csv(sorting_dir / "cluster_KSLabel.tsv", sep="\t", index=False)

        labels = load_cluster_labels(sorting_dir)

        assert "cluster_id" in labels.columns
        assert "KSLabel" in labels.columns
        assert len(labels) == 3


# ============================================================================
# Test load_cluster_metrics()
# ============================================================================


class TestLoadClusterMetrics:
    """Tests for load_cluster_metrics()."""

    def test_load_from_cluster_info(self, sample_kilosort_dir):
        """Test loading metrics from cluster_info.tsv."""
        metrics = load_cluster_metrics(sample_kilosort_dir)

        assert metrics is not None
        assert "cluster_id" in metrics.columns
        assert "ContamPct" in metrics.columns
        assert "Amplitude" in metrics.columns

    def test_no_metrics_returns_none(self, tmp_path):
        """Test returns None when no metric files found."""
        sorting_dir = tmp_path / "no_metrics"
        sorting_dir.mkdir()

        metrics = load_cluster_metrics(sorting_dir)
        assert metrics is None


# ============================================================================
# Test add_units_from_kilosort()
# ============================================================================


class TestAddUnitsFromKilosort:
    """Tests for add_units_from_kilosort()."""

    def test_basic_ingestion(self, nwbfile, sample_kilosort_dir):
        """Test basic units ingestion with default parameters."""
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sample_kilosort_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
        )

        # Should add good + mua units (5 + 3 = 8)
        assert stats["n_units_added"] == 8
        assert stats["n_units_filtered"] == 2  # 2 noise units filtered out
        assert stats["filter_reasons"]["quality_label"] == 2

        # Check units table
        assert len(nwbfile.units) == 8
        # By default includes metrics, so check essential columns are present
        assert "spike_times" in nwbfile.units.colnames
        assert "probe_id" in nwbfile.units.colnames
        assert "contamination_pct" in nwbfile.units.colnames  # Metrics included by default
        assert "amplitude" in nwbfile.units.colnames

    def test_quality_filtering(self, nwbfile, sample_kilosort_dir):
        """Test filtering by quality labels."""
        # Only include "good" units
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sample_kilosort_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
            include_labels=["good"],
        )

        assert stats["n_units_added"] == 5  # Only good units
        assert stats["n_units_filtered"] == 5  # 3 mua + 2 noise filtered out

    def test_spike_count_filtering(self, nwbfile, tmp_path):
        """Test filtering by minimum spike count."""
        # Create data with variable spike counts
        sorting_dir = tmp_path / "kilosort_sparse"
        sorting_dir.mkdir()

        # Cluster 0: 50 spikes, Cluster 1: 150 spikes
        spike_times = np.concatenate(
            [
                np.random.randint(0, 100_000, size=50),
                np.random.randint(0, 100_000, size=150),
            ]
        )
        spike_clusters = np.concatenate(
            [
                np.zeros(50, dtype=np.int32),
                np.ones(150, dtype=np.int32),
            ]
        )

        np.save(sorting_dir / "spike_times.npy", spike_times)
        np.save(sorting_dir / "spike_clusters.npy", spike_clusters)

        cluster_info = pd.DataFrame(
            {
                "cluster_id": [0, 1],
                "KSLabel": ["good", "good"],
            }
        )
        cluster_info.to_csv(sorting_dir / "cluster_info.tsv", sep="\t", index=False)

        # Filter with min_spike_count=100
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sorting_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
            min_spike_count=100,
        )

        assert stats["n_units_added"] == 1  # Only cluster 1 (150 spikes)
        assert stats["n_units_filtered"] == 1  # Cluster 0 filtered out
        assert stats["filter_reasons"]["spike_count"] == 1

    def test_time_conversion(self, nwbfile, tmp_path):
        """Test spike time conversion from samples to seconds."""
        sorting_dir = tmp_path / "kilosort_timing"
        sorting_dir.mkdir()

        # Create 3 spikes at known sample indices
        spike_times = np.array([0, 30000, 60000], dtype=np.int64)  # 0s, 1s, 2s at 30kHz
        spike_clusters = np.zeros(3, dtype=np.int32)

        np.save(sorting_dir / "spike_times.npy", spike_times)
        np.save(sorting_dir / "spike_clusters.npy", spike_clusters)

        cluster_info = pd.DataFrame(
            {
                "cluster_id": [0],
                "KSLabel": ["good"],
            }
        )
        cluster_info.to_csv(sorting_dir / "cluster_info.tsv", sep="\t", index=False)

        add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sorting_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
        )

        unit_spike_times = nwbfile.units["spike_times"][0]
        np.testing.assert_allclose(unit_spike_times, [0.0, 1.0, 2.0], rtol=1e-6)

    def test_electrode_mapping(self, nwbfile_with_electrodes, tmp_path):
        """Test electrode mapping from cluster_info."""
        sorting_dir = tmp_path / "kilosort_electrodes"
        sorting_dir.mkdir()

        spike_times = np.random.randint(0, 100_000, size=100, dtype=np.int64)
        spike_clusters = np.zeros(100, dtype=np.int32)

        np.save(sorting_dir / "spike_times.npy", spike_times)
        np.save(sorting_dir / "spike_clusters.npy", spike_clusters)

        cluster_info = pd.DataFrame(
            {
                "cluster_id": [0],
                "KSLabel": ["good"],
                "ch": [42],  # Map to electrode 42
            }
        )
        cluster_info.to_csv(sorting_dir / "cluster_info.tsv", sep="\t", index=False)

        add_units_from_kilosort(
            nwbfile=nwbfile_with_electrodes,
            sorting_dir=sorting_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
        )

        # Check electrode reference
        # Access the electrodes for the first unit (row 0)
        unit_electrodes = nwbfile_with_electrodes.units[0]["electrodes"]
        # Electrodes are stored as nested list for DynamicTableRegion
        assert len(unit_electrodes) == 1
        assert unit_electrodes[0] == [42]

    def test_quality_metrics_inclusion(self, nwbfile, sample_kilosort_dir):
        """Test inclusion of quality metrics as custom columns."""
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sample_kilosort_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
            include_metrics=True,
        )

        assert stats["n_units_added"] == 8

        # Check custom columns added
        assert "contamination_pct" in nwbfile.units.colnames
        assert "amplitude" in nwbfile.units.colnames
        assert "probe_id" in nwbfile.units.colnames

        # Check values populated
        first_unit_contam = nwbfile.units["contamination_pct"][0]
        first_unit_amp = nwbfile.units["amplitude"][0]

        assert 0 <= first_unit_contam <= 1
        assert first_unit_amp > 0

    def test_waveforms_inclusion(self, nwbfile, sample_kilosort_dir):
        """Test inclusion of mean waveforms from templates."""
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sample_kilosort_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
            include_waveforms=True,
        )

        assert stats["n_units_added"] == 8

        # Check waveform column added
        assert "waveform_mean" in nwbfile.units.colnames

        # Check waveform shape
        first_waveform = nwbfile.units["waveform_mean"][0]
        assert first_waveform.shape == (82, 384)  # n_samples x n_channels

    def test_invalid_sampling_rate(self, nwbfile, sample_kilosort_dir):
        """Test error with invalid sampling rate."""
        with pytest.raises(ValueError, match="sampling_rate must be positive"):
            add_units_from_kilosort(
                nwbfile=nwbfile,
                sorting_dir=sample_kilosort_dir,
                probe_id="imec0",
                sampling_rate=0.0,
            )

        with pytest.raises(ValueError, match="sampling_rate must be positive"):
            add_units_from_kilosort(
                nwbfile=nwbfile,
                sorting_dir=sample_kilosort_dir,
                probe_id="imec0",
                sampling_rate=-30000.0,
            )

    def test_multiple_probes(self, nwbfile, tmp_path):
        """Test adding units from multiple probes sequentially."""
        # Create two probe directories
        for probe_id in ["imec0", "imec1"]:
            probe_dir = tmp_path / probe_id
            probe_dir.mkdir()

            spike_times = np.random.randint(0, 100_000, size=50, dtype=np.int64)
            spike_clusters = np.zeros(50, dtype=np.int32)

            np.save(probe_dir / "spike_times.npy", spike_times)
            np.save(probe_dir / "spike_clusters.npy", spike_clusters)

            cluster_info = pd.DataFrame(
                {
                    "cluster_id": [0],
                    "KSLabel": ["good"],
                }
            )
            cluster_info.to_csv(probe_dir / "cluster_info.tsv", sep="\t", index=False)

        # Add units from both probes
        stats0 = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=tmp_path / "imec0",
            probe_id="imec0",
            sampling_rate=30000.0,
        )

        stats1 = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=tmp_path / "imec1",
            probe_id="imec1",
            sampling_rate=30000.0,
        )

        # Check both probes added
        assert stats0["n_units_added"] == 1
        assert stats1["n_units_added"] == 1
        assert len(nwbfile.units) == 2

        # Check probe_id column
        assert nwbfile.units["probe_id"][0] == "imec0"
        assert nwbfile.units["probe_id"][1] == "imec1"

    def test_stats_accuracy(self, nwbfile, sample_kilosort_dir):
        """Test accuracy of returned statistics."""
        stats = add_units_from_kilosort(
            nwbfile=nwbfile,
            sorting_dir=sample_kilosort_dir,
            probe_id="imec0",
            sampling_rate=30000.0,
            include_labels=["good"],
        )

        # Verify stats match reality
        assert stats["n_units_added"] == 5
        assert stats["n_units_filtered"] == 5
        assert stats["n_units_added"] + stats["n_units_filtered"] == 10  # Total clusters

        # Check spike count
        assert stats["n_spikes_total"] > 0
        assert stats["n_spikes_total"] <= 10_000  # Can't exceed total spikes
