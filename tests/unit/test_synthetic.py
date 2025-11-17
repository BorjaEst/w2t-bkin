"""Tests for synthetic data generation package.

These tests verify that the synthetic package can generate valid data files
that conform to the W2T-BKIN pipeline's expectations.
"""

from pathlib import Path

import pytest

from synthetic.config_synth import create_config_toml, create_session_toml
from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
from synthetic.session_synth import create_minimal_session
from synthetic.ttl_synth import create_ttl_file


class TestTTLGeneration:
    """Test TTL pulse file generation."""

    def test_create_ttl_file_basic(self, tmp_path):
        """Test basic TTL file creation."""
        ttl = SyntheticTTL(
            ttl_id="test_ttl",
            pulse_count=10,
            start_time_s=0.0,
            period_s=0.1,
            jitter_s=0.0,
        )

        output_path = tmp_path / "test.ttl"
        result = create_ttl_file(output_path, ttl, seed=42)

        assert result.exists()
        assert result == output_path

        # Verify content
        with open(result) as f:
            lines = f.readlines()

        assert len(lines) == 10

        # Check timestamps are roughly correct
        for i, line in enumerate(lines):
            timestamp = float(line.strip())
            expected = i * 0.1
            assert abs(timestamp - expected) < 0.01

    def test_create_ttl_file_with_jitter(self, tmp_path):
        """Test TTL file creation with jitter."""
        ttl = SyntheticTTL(
            ttl_id="jitter_ttl",
            pulse_count=100,
            start_time_s=0.0,
            period_s=0.033,
            jitter_s=0.005,
        )

        output_path = tmp_path / "jitter.ttl"
        result = create_ttl_file(output_path, ttl, seed=42)

        assert result.exists()

        with open(result) as f:
            lines = f.readlines()

        assert len(lines) == 100

    def test_create_ttl_deterministic(self, tmp_path):
        """Test that same seed produces same output."""
        ttl = SyntheticTTL(
            ttl_id="det_ttl",
            pulse_count=50,
            period_s=0.02,
            jitter_s=0.001,
        )

        path1 = tmp_path / "det1.ttl"
        path2 = tmp_path / "det2.ttl"

        create_ttl_file(path1, ttl, seed=42)
        create_ttl_file(path2, ttl, seed=42)

        # Content should be identical
        content1 = path1.read_text()
        content2 = path2.read_text()
        assert content1 == content2


class TestConfigGeneration:
    """Test configuration file generation."""

    def test_create_config_toml(self, tmp_path):
        """Test config.toml generation."""
        config_path = create_config_toml(
            tmp_path / "config.toml",
            raw_root=tmp_path / "raw",
            processed_root=tmp_path / "processed",
            temp_root=tmp_path / "temp",
            timebase_source="ttl",
            timebase_ttl_id="test_ttl",
        )

        assert config_path.exists()

        content = config_path.read_text()
        assert "[project]" in content
        assert "[paths]" in content
        assert "[timebase]" in content
        assert 'source = "ttl"' in content
        assert 'ttl_id = "test_ttl"' in content

    def test_create_session_toml(self, tmp_path):
        """Test session.toml generation."""
        camera = SyntheticCamera(
            camera_id="cam0",
            ttl_id="cam0_ttl",
            frame_count=100,
        )
        ttl = SyntheticTTL(
            ttl_id="cam0_ttl",
            pulse_count=100,
        )
        params = SyntheticSessionParams(
            session_id="test-001",
            cameras=[camera],
            ttls=[ttl],
        )

        session_path = create_session_toml(
            tmp_path / "session.toml",
            params=params,
            cameras=[camera],
            ttls=[ttl],
        )

        assert session_path.exists()

        content = session_path.read_text()
        assert "[session]" in content
        assert 'id = "test-001"' in content
        assert "[[cameras]]" in content
        assert 'id = "cam0"' in content
        assert "[[TTLs]]" in content  # Capital TTLs per schema
        assert 'id = "cam0_ttl"' in content


class TestSessionGeneration:
    """Test complete session generation."""

    def test_create_minimal_session(self, tmp_path):
        """Test minimal session creation."""
        session = create_minimal_session(
            root=tmp_path,
            session_id="test-minimal",
            n_frames=32,
            seed=42,
        )

        # Check paths exist
        assert session.config_path.exists()
        assert session.session_path.exists()
        assert session.raw_dir.exists()

        # Check video files were created
        assert len(session.camera_video_paths) == 1
        assert "cam0" in session.camera_video_paths
        assert len(session.camera_video_paths["cam0"]) == 1
        assert session.camera_video_paths["cam0"][0].exists()

        # Check TTL files were created
        assert len(session.ttl_paths) == 1
        assert "cam0_ttl" in session.ttl_paths
        assert session.ttl_paths["cam0_ttl"].exists()

        # Verify TTL content
        ttl_path = session.ttl_paths["cam0_ttl"]
        with open(ttl_path) as f:
            lines = f.readlines()
        assert len(lines) == 32

    def test_session_deterministic(self, tmp_path):
        """Test that sessions are deterministic with same seed."""
        session1 = create_minimal_session(
            root=tmp_path / "s1",
            session_id="det-test",
            n_frames=32,
            seed=42,
        )

        session2 = create_minimal_session(
            root=tmp_path / "s2",
            session_id="det-test",
            n_frames=32,
            seed=42,
        )

        # TTL files should have identical content
        ttl1 = session1.ttl_paths["cam0_ttl"].read_text()
        ttl2 = session2.ttl_paths["cam0_ttl"].read_text()
        assert ttl1 == ttl2


class TestScenarios:
    """Test scenario templates."""

    def test_happy_path_scenario(self, tmp_path):
        """Test happy path scenario generation."""
        from synthetic.scenarios import happy_path

        session = happy_path.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        assert session.config_path.exists()
        assert session.session_path.exists()
        assert len(session.camera_video_paths) == 1
        assert len(session.ttl_paths) == 1

    def test_mismatch_scenario(self, tmp_path):
        """Test mismatch counts scenario generation."""
        from synthetic.scenarios import mismatch_counts

        session = mismatch_counts.make_session(
            root=tmp_path,
            n_frames=100,
            n_pulses=95,
            seed=42,
        )

        # Verify mismatch
        ttl_path = session.ttl_paths["cam0_ttl"]
        with open(ttl_path) as f:
            lines = f.readlines()
        assert len(lines) == 95  # Mismatch!

    def test_no_ttl_scenario(self, tmp_path):
        """Test no TTL scenario generation."""
        from synthetic.scenarios import no_ttl

        session = no_ttl.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        assert session.config_path.exists()
        assert len(session.camera_video_paths) == 1
        assert len(session.ttl_paths) == 0  # No TTLs

        # Check config uses nominal_rate
        config_content = session.config_path.read_text()
        assert 'source = "nominal_rate"' in config_content

    def test_multi_camera_scenario(self, tmp_path):
        """Test multi-camera scenario generation."""
        from synthetic.scenarios import multi_camera

        session = multi_camera.make_session(
            root=tmp_path,
            n_cameras=3,
            n_frames=64,
            seed=42,
        )

        assert len(session.camera_video_paths) == 3
        assert len(session.ttl_paths) == 3
        assert "cam0" in session.camera_video_paths
        assert "cam1" in session.camera_video_paths
        assert "cam2" in session.camera_video_paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
