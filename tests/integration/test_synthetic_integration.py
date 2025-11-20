"""Integration tests using synthetic data with the W2T-BKIN pipeline.

These tests verify that synthetically generated data works correctly with
the pipeline orchestration API (Phase 2 pattern).
"""

from pathlib import Path

import pytest


class TestSyntheticIntegration:
    """Integration tests using synthetic data with pipeline orchestration."""

    def test_happy_path_pipeline(self, tmp_path):
        """Test complete pipeline workflow with synthetic data."""
        from synthetic.scenarios import happy_path
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session
        session = happy_path.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Run pipeline orchestration (Phase 2 pattern)
        result = run_session(config_path=session.config_path, session_id=session.session_id, options={"skip_nwb": True, "skip_validation": False})

        # Verify manifest
        manifest = result["manifest"]
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].camera_id == "cam0"
        assert manifest.cameras[0].frame_count == 64

        # Verify alignment stats created
        assert result["alignment_stats"] is not None
        assert result["alignment_stats"].timebase_source == "ttl"

        # Verify events summary created
        assert result["events_summary"] is not None
        assert result["events_summary"]["total_trials"] > 0

        # Verify provenance
        assert "provenance" in result
        assert "config_hash" in result["provenance"]

    def test_mismatch_detection(self, tmp_path):
        """Test that mismatch scenario is correctly detected by pipeline."""
        from synthetic.scenarios import mismatch_counts
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session with mismatch
        session = mismatch_counts.make_session(
            root=tmp_path,
            n_frames=100,
            n_pulses=95,
            seed=42,
        )

        # Run pipeline - should fail verification
        with pytest.raises(ValueError, match="Frame/TTL verification failed"):
            run_session(config_path=session.config_path, session_id=session.session_id, options={"skip_nwb": True, "skip_validation": False})

        # Run with validation skipped should succeed
        result = run_session(config_path=session.config_path, session_id=session.session_id, options={"skip_nwb": True, "skip_validation": True})

        # Manifest should still show the mismatch
        manifest = result["manifest"]
        assert manifest.cameras[0].frame_count == 100
        assert manifest.cameras[0].ttl_pulse_count == 95

    def test_no_ttl_session(self, tmp_path):
        """Test session without TTL uses nominal rate timebase."""
        from synthetic.scenarios import no_ttl
        from w2t_bkin.pipeline import run_session

        # Generate synthetic session without TTL
        session = no_ttl.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Run pipeline with nominal rate timebase
        result = run_session(config_path=session.config_path, session_id=session.session_id, options={"skip_nwb": True, "skip_validation": True})

        # Verify alignment stats use nominal_rate
        assert result["alignment_stats"] is not None
        assert result["alignment_stats"].timebase_source == "nominal_rate"

        # Verify camera has placeholder TTL
        manifest = result["manifest"]
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].ttl_id == "placeholder_ttl"
        assert manifest.cameras[0].ttl_pulse_count == 0

    def test_multi_camera_session(self, tmp_path):
        """Test multi-camera session through pipeline orchestration."""
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
        result = run_session(config_path=session.config_path, session_id=session.session_id, options={"skip_nwb": True, "skip_validation": False})

        # Verify all cameras in manifest
        manifest = result["manifest"]
        assert len(manifest.cameras) == 3
        for i, camera in enumerate(manifest.cameras):
            assert camera.camera_id == f"cam{i}"
            assert camera.ttl_id == f"cam{i}_ttl"
            assert camera.frame_count == 64

        # Verify alignment stats created
        assert result["alignment_stats"] is not None

        # Verify provenance tracks all cameras
        assert "provenance" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
