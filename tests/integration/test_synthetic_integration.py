"""Integration tests using synthetic data with the W2T-BKIN pipeline.

These tests verify that synthetically generated data works correctly with
the actual pipeline components.
"""

from pathlib import Path

import pytest


class TestSyntheticIntegration:
    """Integration tests using synthetic data."""

    def test_happy_path_ingest_verify(self, tmp_path):
        """Test complete ingest and verify workflow with synthetic data."""
        from synthetic.scenarios import happy_path
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_and_count_manifest, verify_manifest

        # Generate synthetic session
        session = happy_path.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Load config and session
        config = load_config(session.config_path)
        session_data = load_session(session.session_path)

        # Build manifest
        manifest = build_and_count_manifest(config, session_data)

        # Verify counts
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].camera_id == "cam0"

        # Verify frame/TTL alignment
        result = verify_manifest(manifest, tolerance=5)

        # Should succeed with no errors
        assert hasattr(result, "camera_results")
        camera_result = result.camera_results[0]
        assert camera_result.verifiable is True
        assert camera_result.mismatch == 0

    def test_mismatch_detection(self, tmp_path):
        """Test that mismatch scenario is correctly detected."""
        from synthetic.scenarios import mismatch_counts
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_and_count_manifest, verify_manifest

        # Generate synthetic session with mismatch
        session = mismatch_counts.make_session(
            root=tmp_path,
            n_frames=100,
            n_pulses=95,
            seed=42,
        )

        # Load config and session
        config = load_config(session.config_path)
        session_data = load_session(session.session_path)

        # Build manifest
        manifest = build_and_count_manifest(config, session_data)

        # Verify counts show mismatch
        result = verify_manifest(manifest, tolerance=5)

        camera_result = result.camera_results[0]
        assert camera_result.mismatch == 5
        # Mismatch equals tolerance, might be at boundary

    def test_no_ttl_session(self, tmp_path):
        """Test session without TTL uses nominal rate."""
        from synthetic.scenarios import no_ttl
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_and_count_manifest

        # Generate synthetic session without TTL
        session = no_ttl.make_session(
            root=tmp_path,
            n_frames=64,
            seed=42,
        )

        # Load config and session
        config = load_config(session.config_path)
        session_data = load_session(session.session_path)

        # Verify config uses nominal_rate
        assert config.timebase.source == "nominal_rate"

        # Build manifest
        manifest = build_and_count_manifest(config, session_data)

        # Verify camera has placeholder TTL (schema requires it)
        assert len(manifest.cameras) == 1
        assert manifest.cameras[0].ttl_id == "placeholder_ttl"
        # No actual TTL files, so pulse count should be 0
        assert manifest.cameras[0].ttl_pulse_count == 0

    def test_multi_camera_session(self, tmp_path):
        """Test multi-camera session generation and ingest."""
        from synthetic.scenarios import multi_camera
        from w2t_bkin.config import load_config, load_session
        from w2t_bkin.ingest import build_and_count_manifest, verify_manifest

        # Generate multi-camera session
        session = multi_camera.make_session(
            root=tmp_path,
            n_cameras=3,
            n_frames=64,
            seed=42,
        )

        # Load config and session
        config = load_config(session.config_path)
        session_data = load_session(session.session_path)

        # Build manifest
        manifest = build_and_count_manifest(config, session_data)

        # Verify all cameras
        assert len(manifest.cameras) == 3
        for i, camera in enumerate(manifest.cameras):
            assert camera.camera_id == f"cam{i}"
            assert camera.ttl_id == f"cam{i}_ttl"

        # Verify all pass
        result = verify_manifest(manifest, tolerance=5)
        for camera_result in result.camera_results:
            assert camera_result.verifiable is True
            assert camera_result.mismatch == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
