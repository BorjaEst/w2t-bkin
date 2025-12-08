"""
Unit tests for SpikeGLX hardware parsers.

Tests SpikeGLX .meta file parsing only (hardware metadata).
Kilosort parsing tests moved to test_kilosort.py.
"""

from pathlib import Path
import tempfile

import pytest

from w2t_bkin.ingest.spikeglx import parse_spikeglx_meta


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
