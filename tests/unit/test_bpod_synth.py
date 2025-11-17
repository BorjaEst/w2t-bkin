"""Tests for Bpod .mat file generation."""

from pathlib import Path

import pytest

pytest.importorskip("scipy", reason="scipy required for Bpod generation")


class TestBpodGeneration:
    """Test Bpod .mat file generation."""

    def test_create_bpod_mat_file(self, tmp_path):
        """Test basic Bpod .mat file creation."""
        from scipy.io import loadmat

        from synthetic.bpod_synth import create_bpod_mat_file

        mat_path = tmp_path / "test_bpod.mat"
        result = create_bpod_mat_file(mat_path, n_trials=10, seed=42)

        assert result.exists()
        assert result == mat_path

        # Load and verify structure
        data = loadmat(mat_path, struct_as_record=False, squeeze_me=True)
        assert "SessionData" in data

        session_data = data["SessionData"]
        assert hasattr(session_data, "nTrials")
        assert session_data.nTrials == 10
        assert hasattr(session_data, "Info")
        assert hasattr(session_data, "RawEvents")

    def test_bpod_trial_structure(self, tmp_path):
        """Test that trials have correct structure."""
        from scipy.io import loadmat

        from synthetic.bpod_synth import create_bpod_mat_file

        mat_path = tmp_path / "test_trials.mat"
        create_bpod_mat_file(mat_path, n_trials=5, seed=42)

        data = loadmat(mat_path, struct_as_record=False, squeeze_me=True)
        session_data = data["SessionData"]

        # Check trials array
        trials = session_data.RawEvents.Trial
        assert len(trials) == 5

        # Check first trial structure
        trial_0 = trials[0]
        assert hasattr(trial_0, "States")
        assert hasattr(trial_0, "Events")

        # Check states
        assert hasattr(trial_0.States, "ITI")
        assert hasattr(trial_0.States, "Response_window")

        # Check events
        assert hasattr(trial_0.Events, "Port1In")
        assert hasattr(trial_0.Events, "Port1Out")

    def test_bpod_deterministic(self, tmp_path):
        """Test that same seed produces same output."""
        import numpy as np
        from scipy.io import loadmat

        from synthetic.bpod_synth import create_bpod_mat_file

        mat1 = tmp_path / "bpod1.mat"
        mat2 = tmp_path / "bpod2.mat"

        create_bpod_mat_file(mat1, n_trials=5, seed=42)
        create_bpod_mat_file(mat2, n_trials=5, seed=42)

        data1 = loadmat(mat1, struct_as_record=False, squeeze_me=True)
        data2 = loadmat(mat2, struct_as_record=False, squeeze_me=True)

        # Timestamps should be identical
        timestamps1 = data1["SessionData"].TrialStartTimestamp
        timestamps2 = data2["SessionData"].TrialStartTimestamp
        assert np.allclose(timestamps1, timestamps2)

    def test_simple_bpod_file(self, tmp_path):
        """Test simple Bpod file creation."""
        from scipy.io import loadmat

        from synthetic.bpod_synth import create_simple_bpod_file

        mat_path = tmp_path / "simple.mat"
        create_simple_bpod_file(mat_path, n_trials=3, seed=42)

        data = loadmat(mat_path, struct_as_record=False, squeeze_me=True)
        assert data["SessionData"].nTrials == 3


class TestBpodIntegration:
    """Test Bpod integration with session generation."""

    def test_session_with_bpod(self, tmp_path):
        """Test session generation with Bpod files."""
        from synthetic.scenarios import happy_path

        session = happy_path.make_session_with_bpod(
            root=tmp_path,
            n_frames=64,
            n_trials=10,
            seed=42,
            use_ffmpeg=False,
        )

        # Check Bpod file was created
        assert session.bpod_path is not None
        assert session.bpod_path.exists()
        assert session.bpod_path.suffix == ".mat"

        # Verify it's a valid .mat file
        from scipy.io import loadmat

        data = loadmat(session.bpod_path, struct_as_record=False, squeeze_me=True)
        assert "SessionData" in data
        assert data["SessionData"].nTrials == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
