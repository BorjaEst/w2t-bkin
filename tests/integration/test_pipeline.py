"""Integration tests for SessionPipeline.

Tests the full pipeline orchestration using synthetic data.
"""

from pathlib import Path

from pynwb import NWBHDF5IO
import pytest

from synthetic import build_raw_folder
from w2t_bkin.core.pipeline import RunOptions, SessionPipeline


class TestSessionPipelineIntegration:
    """Test full pipeline execution."""

    def test_Should_RunFullPipeline_When_ValidSessionProvided(self, tmp_path):
        """Should successfully run the full pipeline on a synthetic session."""

        # 1. Generate synthetic session
        raw_root = tmp_path / "raw"
        result = build_raw_folder(
            out_root=raw_root,
            project_name="test-project",
            subject_id="subject-001",
            session_id="session-001",
            n_frames=30,  # Small number for speed
            n_trials=5,
            camera_ids=["cam0"],
            ttl_ids=["ttl_camera", "ttl_cue"],
        )

        # 2. Initialize pipeline
        pipeline = SessionPipeline(
            config_path=result.config_path,
            subject_id="subject-001",
            session_id="session-001",
            options=RunOptions(
                skip_nwb_validation=True,  # Skip validation to avoid nwbinspector dependency in tests if not installed
                skip_pose=True,  # Skip pose for basic test
            ),
        )

        # 3. Run pipeline
        run_result = pipeline.run()

        # 4. Verify success
        assert run_result.success
        assert run_result.nwb_path.exists()
        assert run_result.nwbfile is not None

        # 5. Verify NWB content
        with NWBHDF5IO(str(run_result.nwb_path), "r") as io:
            nwb = io.read()
            assert nwb.identifier == "session-001"
            assert "cam0" in nwb.acquisition
            # Check if trials are present (since we have Bpod data)
            assert nwb.trials is not None
            assert len(nwb.trials) > 0

    def test_Should_SkipBpod_When_OptionSet(self, tmp_path):
        """Should skip Bpod processing when requested."""

        # 1. Generate synthetic session
        raw_root = tmp_path / "raw"
        result = build_raw_folder(
            out_root=raw_root,
            subject_id="subject-002",
            session_id="session-001",
            n_frames=30,
            n_trials=5,
        )

        # 2. Initialize pipeline with skip_bpod=True
        pipeline = SessionPipeline(
            config_path=result.config_path,
            subject_id="subject-002",
            session_id="session-001",
            options=RunOptions(
                skip_bpod=True,
                skip_nwb_validation=True,
                skip_pose=True,
            ),
        )

        # 3. Run pipeline
        run_result = pipeline.run()

        # 4. Verify success
        assert run_result.success

        # 5. Verify NWB content (should NOT have trials)
        with NWBHDF5IO(str(run_result.nwb_path), "r") as io:
            nwb = io.read()
            # Trials table might exist but be empty or None depending on implementation
            # In current implementation, if skip_bpod is True, trials table is not added
            assert nwb.trials is None or len(nwb.trials) == 0

    def test_Should_FailGracefully_When_ConfigInvalid(self, tmp_path):
        """Should return failed result when config is invalid."""

        # 1. Create invalid config path
        invalid_config = tmp_path / "invalid_config.toml"
        invalid_config.touch()

        # 2. Initialize pipeline
        pipeline = SessionPipeline(
            config_path=invalid_config,
            subject_id="subject-003",
            session_id="session-001",
        )

        # 3. Run pipeline
        run_result = pipeline.run()

        # 4. Verify failure
        assert not run_result.success
        assert run_result.error is not None
