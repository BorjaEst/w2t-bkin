"""Integration tests for Prefect flow orchestration.

Tests the full flow-based pipeline using synthetic data.
"""

from pathlib import Path

from pynwb import NWBHDF5IO
import pytest

from synthetic import build_raw_folder
from w2t_bkin.api import SessionConfig
from w2t_bkin.flows import process_session_flow


class TestSessionFlowIntegration:
    """Test full flow execution."""

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

        # 2. Run flow
        config = SessionConfig(
            config_path=str(result.config_path),
            subject_id="subject-001",
            session_id="session-001",
            skip_nwb_validation=True,  # Skip validation to avoid nwbinspector dependency in tests if not installed
            skip_pose=True,  # Skip pose for basic test
        )
        flow_result = process_session_flow(config)

        # 3. Verify success
        assert flow_result.success
        assert flow_result.nwb_path.exists()

        # 4. Verify NWB content
        with NWBHDF5IO(str(flow_result.nwb_path), "r") as io:
            nwb = io.read()
            assert nwb.identifier == "session-001"
            assert "cam0" in nwb.devices  # Camera is registered as a device
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

        # 2. Run flow with skip_bpod=True
        config = SessionConfig(
            config_path=str(result.config_path),
            subject_id="subject-002",
            session_id="session-001",
            skip_bpod=True,  # Skip Bpod processing
            skip_nwb_validation=True,
            skip_pose=True,
        )
        flow_result = process_session_flow(config)

        # 3. Verify success
        assert flow_result.success

        # 4. Verify NWB content (should NOT have trials)
        with NWBHDF5IO(str(flow_result.nwb_path), "r") as io:
            nwb = io.read()
            # Trials table might exist but be empty or None depending on implementation
            # In current implementation, if skip_bpod is True, trials table is not added
            assert nwb.trials is None or len(nwb.trials) == 0

    def test_Should_FailGracefully_When_ConfigInvalid(self, tmp_path):
        """Should return failed result when config is invalid."""

        # 1. Create invalid config path
        invalid_config = tmp_path / "invalid_config.toml"
        invalid_config.touch()

        # 2. Run flow
        config = SessionConfig(
            config_path=str(invalid_config),
            subject_id="subject-003",
            session_id="session-001",
        )
        flow_result = process_session_flow(config)

        # 3. Verify failure
        assert not flow_result.success
        assert flow_result.error is not None
