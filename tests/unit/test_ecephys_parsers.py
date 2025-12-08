"""
Unit tests for ecephys parsers module.

Tests SpikeGLX .meta file parsing and Kilosort file loading.
"""

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

from w2t_bkin.ingest.ecephys.parsers import load_cluster_labels, load_cluster_metrics, load_kilosort_data, parse_spikeglx_meta


class TestParseSpikeGLXMeta:
    """Test SpikeGLX .meta file parsing."""

    @pytest.fixture
    def sample_meta_path(self):
        """Path to sample .meta fixture."""
        return Path(__file__).parent.parent / "fixtures/ecephys/sample_np20.imec0.ap.meta"

    def test_parse_valid_meta(self, sample_meta_path):
        """Test parsing a valid .meta file."""
        meta = parse_spikeglx_meta(sample_meta_path)

        assert meta["sampling_rate"] == 30000.0
        assert meta["n_channels"] == 384
        assert meta["probe_type"] == "21"  # NP2.0
        assert meta["file_size_bytes"] == 230400000
        assert "High-pass" in meta["filtering"] or "Bandpass" in meta["filtering"]

    def test_parse_geometry(self, sample_meta_path):
        """Test electrode geometry parsing."""
        meta = parse_spikeglx_meta(sample_meta_path)

        geometry = meta.get("geometry", [])
        assert len(geometry) > 0
        assert isinstance(geometry[0], tuple)
        assert len(geometry[0]) == 2  # (x, y)

        # Check first few coordinates match fixture
        assert geometry[0] == (16.0, 0.0)
        assert geometry[1] == (48.0, 0.0)

    def test_parse_nonexistent_file(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_spikeglx_meta(Path("/nonexistent/file.meta"))

    def test_parse_malformed_meta(self, tmp_path):
        """Test error handling for malformed .meta file."""
        # Create malformed .meta (missing required fields)
        malformed_meta = tmp_path / "malformed.meta"
        malformed_meta.write_text("somekey=somevalue\n")

        with pytest.raises(ValueError, match="Required field missing"):
            parse_spikeglx_meta(malformed_meta)

    def test_caching(self, sample_meta_path):
        """Test that repeated parsing uses cache."""
        # First parse
        meta1 = parse_spikeglx_meta(sample_meta_path)

        # Second parse (should hit cache)
        meta2 = parse_spikeglx_meta(sample_meta_path)

        # Should be the exact same object (cached)
        assert meta1 is meta2


class TestLoadKilosortData:
    """Test Kilosort file loading."""

    @pytest.fixture
    def mock_kilosort_dir(self, tmp_path):
        """Create a mock Kilosort output directory."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Create spike_times.npy (100 spikes)
        spike_times = np.arange(0, 100000, 1000, dtype=np.int64)
        np.save(ks_dir / "spike_times.npy", spike_times)

        # Create spike_clusters.npy (10 units, 10 spikes each)
        spike_clusters = np.repeat(np.arange(10, dtype=np.int32), 10)
        np.save(ks_dir / "spike_clusters.npy", spike_clusters)

        # Create templates.npy (10 templates, 82 samples, 384 channels)
        templates = np.random.randn(10, 82, 384).astype(np.float32)
        np.save(ks_dir / "templates.npy", templates)

        return ks_dir

    def test_load_valid_data(self, mock_kilosort_dir):
        """Test loading valid Kilosort data."""
        data = load_kilosort_data(mock_kilosort_dir)

        assert "spike_times" in data
        assert "spike_clusters" in data
        assert "templates" in data

        assert data["spike_times"].shape == (100,)
        assert data["spike_clusters"].shape == (100,)
        assert data["templates"].shape == (10, 82, 384)

    def test_load_without_templates(self, tmp_path):
        """Test loading when templates.npy is missing."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Only create required files
        np.save(ks_dir / "spike_times.npy", np.array([100, 200, 300]))
        np.save(ks_dir / "spike_clusters.npy", np.array([0, 0, 1]))

        data = load_kilosort_data(ks_dir)

        assert data["templates"] is None

    def test_load_missing_required_file(self, tmp_path):
        """Test error handling when required files are missing."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="spike_times.npy"):
            load_kilosort_data(ks_dir)


class TestLoadClusterLabels:
    """Test cluster label loading."""

    @pytest.fixture
    def mock_labels_dir(self, tmp_path):
        """Create mock label files."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Create cluster_info.tsv (newer format)
        cluster_info = pd.DataFrame(
            {
                "cluster_id": [0, 1, 2, 3, 4],
                "KSLabel": ["good", "good", "mua", "noise", "good"],
                "ch": [10, 20, 30, 40, 50],
                "Amplitude": [100.0, 120.0, 80.0, 30.0, 110.0],
            }
        )
        cluster_info.to_csv(ks_dir / "cluster_info.tsv", sep="\t", index=False)

        return ks_dir

    def test_load_cluster_info(self, mock_labels_dir):
        """Test loading from cluster_info.tsv."""
        labels = load_cluster_labels(mock_labels_dir)

        assert "cluster_id" in labels.columns
        assert "KSLabel" in labels.columns
        assert len(labels) == 5
        assert labels["KSLabel"].iloc[0] == "good"

    def test_load_fallback_format(self, tmp_path):
        """Test fallback to cluster_KSLabel.tsv."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Create only cluster_KSLabel.tsv
        ks_labels = pd.DataFrame(
            {
                "cluster_id": [0, 1, 2],
                "KSLabel": ["good", "mua", "noise"],
            }
        )
        ks_labels.to_csv(ks_dir / "cluster_KSLabel.tsv", sep="\t", index=False)

        labels = load_cluster_labels(ks_dir)

        assert len(labels) == 3
        assert "KSLabel" in labels.columns

    def test_load_no_label_file(self, tmp_path):
        """Test error when no label file exists."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="No cluster label file"):
            load_cluster_labels(ks_dir)


class TestLoadClusterMetrics:
    """Test cluster quality metrics loading."""

    @pytest.fixture
    def mock_metrics_dir(self, tmp_path):
        """Create mock metric files."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Create cluster_info.tsv with metrics
        cluster_info = pd.DataFrame(
            {
                "cluster_id": [0, 1, 2],
                "ContamPct": [0.05, 0.10, 0.15],
                "Amplitude": [100.0, 120.0, 80.0],
            }
        )
        cluster_info.to_csv(ks_dir / "cluster_info.tsv", sep="\t", index=False)

        return ks_dir

    def test_load_metrics_from_cluster_info(self, mock_metrics_dir):
        """Test loading metrics from cluster_info.tsv."""
        metrics = load_cluster_metrics(mock_metrics_dir)

        assert metrics is not None
        assert "ContamPct" in metrics.columns
        assert "Amplitude" in metrics.columns
        assert len(metrics) == 3

    def test_load_metrics_from_separate_files(self, tmp_path):
        """Test loading metrics from separate TSV files."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        # Create separate metric files
        contam = pd.DataFrame({"cluster_id": [0, 1], "ContamPct": [0.05, 0.10]})
        contam.to_csv(ks_dir / "cluster_ContamPct.tsv", sep="\t", index=False)

        amp = pd.DataFrame({"cluster_id": [0, 1], "Amplitude": [100.0, 120.0]})
        amp.to_csv(ks_dir / "cluster_Amplitude.tsv", sep="\t", index=False)

        metrics = load_cluster_metrics(ks_dir)

        assert metrics is not None
        assert "ContamPct" in metrics.columns
        assert "Amplitude" in metrics.columns

    def test_load_no_metrics(self, tmp_path):
        """Test when no metric files exist."""
        ks_dir = tmp_path / "kilosort"
        ks_dir.mkdir()

        metrics = load_cluster_metrics(ks_dir)

        assert metrics is None
