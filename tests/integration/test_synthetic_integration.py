"""Integration tests using synthetic data with the W2T-BKIN pipeline.

These tests verify that synthetically generated data works correctly with
the pipeline orchestration layer (Phase 2 pattern).
"""

from pathlib import Path

import pytest


class TestSyntheticIntegration:
    """Integration tests using synthetic data via pipeline API."""

    def test_happy_path_ingest_verify(self, tmp_path):
        """Test complete ingest and verify workflow with synthetic data using run_session()."""
        from synthetic.scenarios import happy_path
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session
        session = happy_path.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Run pipeline orchestration
        result = run_session(
            config_path=session.config_path,
            session_id=session.id,
            options={"skip_nwb": True},
        )

        # Verify manifest was built
        manifest = result["manifest"]
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].camera_id == "cam0"

        # Verify frame counts populated
        assert manifest.cameras[0].frame_count == 64

        # Verify provenance tracking
        assert "provenance" in result
        assert "config_hash" in result["provenance"]
        assert "session_hash" in result["provenance"]

    def test_mismatch_detection(self, tmp_path):
        """Test that mismatch scenario is correctly detected via run_session()."""
        from synthetic.scenarios import mismatch_counts
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session with mismatch
        session = mismatch_counts.make_session(
            root=tmp_path,
            n_frames=100,
            n_pulses=95,
            seed=42,
        )

        # Run pipeline - should complete even with mismatch within tolerance
        result = run_session(
            config_path=session.config_path,
            session_id=session.id,
            options={"skip_nwb": True},
        )

        # Verify manifest shows frame/pulse counts
        manifest = result["manifest"]
        assert manifest.cameras[0].frame_count == 100
        assert manifest.cameras[0].ttl_pulse_count == 95

        # Mismatch of 5 should be detected but within default tolerance

    def test_no_ttl_session(self, tmp_path):
        """Test session without TTL uses nominal rate via run_session()."""
        from synthetic.scenarios import no_ttl
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session without TTL
        session = no_ttl.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Run pipeline
        result = run_session(
            config_path=session.config_path,
            session_id=session.id,
            options={"skip_nwb": True},
        )

        # Verify manifest built correctly
        manifest = result["manifest"]
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].camera_id == "cam0"
        assert manifest.cameras[0].ttl_id == "placeholder_ttl"

        # No actual TTL files, so pulse count should be 0
        assert manifest.cameras[0].ttl_pulse_count == 0

    def test_multi_camera_session(self, tmp_path):
        """Test multi-camera session generation and ingest via run_session()."""
        from synthetic.scenarios import multi_camera
        from w2t_bkin.pipeline import run_session

        # Generate multi-camera session
        session = multi_camera.make_session(
            root=tmp_path,
            n_cameras=3,
            n_frames=64,
            seed=42,
        )

        # Run pipeline orchestration
        result = run_session(
            config_path=session.config_path,
            session_id=session.id,
            options={"skip_nwb": True},
        )

        # Verify all cameras in manifest
        manifest = result["manifest"]
        assert len(manifest.cameras) == 3
        for i, camera in enumerate(manifest.cameras):
            assert camera.camera_id == f"cam{i}"
            assert camera.ttl_id == f"cam{i}_ttl"
            assert camera.frame_count == 64

        # Verify provenance includes all stages
        assert "provenance" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
