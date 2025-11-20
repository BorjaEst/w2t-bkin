"""Tests for synthetic data generation package.

These tests verify that the synthetic package can generate valid data files
that conform to the W2T-BKIN pipeline's expectations.
"""

from pathlib import Path

import pytest

from synthetic.config_synth import build_config, write_config_toml
from synthetic.session_synth import build_session
from synthetic.ttl_synth import TTLGenerationOptions, generate_ttl_pulses, write_ttl_pulse_files


class TestTTLGeneration:
    """Test TTL pulse file generation."""

    def test_generate_ttl_pulses_basic(self):
        """Test basic TTL pulse generation."""
        pulses = generate_ttl_pulses(
            ttl_ids=["test_ttl"],
            options=TTLGenerationOptions(
                pulses_per_ttl=10,
                rate_hz=10.0,
                jitter_s=0.0,
                seed=42,
            ),
        )

        assert "test_ttl" in pulses
        assert len(pulses["test_ttl"]) == 10

        # Check timestamps are roughly correct
        for i, timestamp in enumerate(pulses["test_ttl"]):
            expected = i * 0.1  # 10 Hz = 0.1s period
            assert abs(timestamp - expected) < 0.01

    def test_generate_ttl_pulses_with_jitter(self):
        """Test TTL pulse generation with jitter."""
        pulses = generate_ttl_pulses(
            ttl_ids=["jitter_ttl"],
            options=TTLGenerationOptions(
                pulses_per_ttl=100,
                rate_hz=30.0,
                jitter_s=0.005,
                seed=42,
            ),
        )

        assert "jitter_ttl" in pulses
        assert len(pulses["jitter_ttl"]) == 100

    def test_generate_ttl_deterministic(self):
        """Test that same seed produces same output."""
        pulses1 = generate_ttl_pulses(
            ttl_ids=["det_ttl"],
            options=TTLGenerationOptions(
                pulses_per_ttl=50,
                rate_hz=50.0,
                jitter_s=0.001,
                seed=42,
            ),
        )

        pulses2 = generate_ttl_pulses(
            ttl_ids=["det_ttl"],
            options=TTLGenerationOptions(
                pulses_per_ttl=50,
                rate_hz=50.0,
                jitter_s=0.001,
                seed=42,
            ),
        )

        # Content should be identical
        assert pulses1["det_ttl"] == pulses2["det_ttl"]


class TestConfigGeneration:
    """Test configuration file generation."""

    def test_create_config_toml(self, tmp_path):
        """Test config.toml generation."""
        from synthetic.config_synth import SynthConfigOptions

        config = build_config(
            options=SynthConfigOptions(
                project_name="test-project",
                raw_root=str(tmp_path / "raw"),
                processed_root=str(tmp_path / "processed"),
                temp_root=str(tmp_path / "temp"),
                timebase_source="ttl",
                timebase_ttl_id="test_ttl",
            )
        )
        config_path = write_config_toml(tmp_path / "config.toml", config)

        assert config_path.exists()

        content = config_path.read_text()
        assert "[project]" in content
        assert "[paths]" in content
        assert "[timebase]" in content
        assert 'source = "ttl"' in content
        assert 'ttl_id = "test_ttl"' in content

    def test_create_session_toml(self, tmp_path):
        """Test session.toml generation."""
        from synthetic.session_synth import SessionSynthOptions, write_session_toml

        # Use SessionSynthOptions to build a session
        session = build_session(
            options=SessionSynthOptions(
                session_id="test-001",
                project_name="test-project",
                experimenter="Test User",
                subject_id="mouse-01",
            )
        )
        session_path = write_session_toml(tmp_path / "session.toml", session)

        assert session_path.exists()

        content = session_path.read_text()
        assert "[session]" in content
        assert 'id = "test-001"' in content


class TestSessionGeneration:
    """Test complete session generation."""

    def test_create_minimal_session(self, tmp_path):
        """Test minimal session creation using scenarios."""
        from synthetic.scenarios import happy_path

        session = happy_path.make_session(
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
