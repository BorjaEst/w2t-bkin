"""Integration tests for SLEAP Pose Ingestion in flow orchestration."""

from pathlib import Path
import shutil

from pynwb import NWBHDF5IO
import pytest

from synthetic import build_raw_folder
from synthetic.pose_synth import PoseH5Params, create_sleap_pose_h5
from w2t_bkin.api import SessionFlowConfig
from w2t_bkin.flows import process_session_flow


class TestFlowSLEAPIngestion:
    """Test SLEAP pose ingestion logic."""

    def test_Should_IngestSLEAPData_When_FilesExist(self, tmp_path):
        """Should successfully ingest SLEAP pose data into NWB."""

        # 1. Generate synthetic session
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"

        subject_id = "subject-001"
        session_id = "session-001"
        camera_id = "cam0"
        n_frames = 30

        result = build_raw_folder(
            out_root=raw_root,
            project_name="test-project",
            subject_id=subject_id,
            session_id=session_id,
            n_frames=n_frames,
            n_trials=5,
            camera_ids=[camera_id],
            ttl_ids=["ttl_camera"],
        )

        # 2. Create Interim SLEAP Data
        # Pipeline expects: interim_root / subject_id / session_id / "sleap-pose" / camera_id / "*{video_stem}*.h5"
        sleap_dir = interim_root / subject_id / session_id / "sleap-pose" / camera_id
        sleap_dir.mkdir(parents=True, exist_ok=True)

        # Get video stem from generated raw files
        video_path = next(p for p in result.video_paths if camera_id in p.name)
        video_stem = video_path.stem

        sleap_filename = f"{video_stem}.predictions.h5"
        sleap_path = sleap_dir / sleap_filename

        # Generate synthetic SLEAP H5 content
        pose_params = PoseH5Params(
            keypoints=["nose", "tail_base"],
            n_frames=n_frames,
            fps=30.0,
        )
        create_sleap_pose_h5(sleap_path, pose_params)

        # Enable SLEAP preprocessing in config (needed for ingestion)
        # But we skip generation with skip_sleap=True to use pre-existing files
        config_content = result.config_path.read_text()
        if "[preprocessing.sleap]" in config_content:
            config_content = config_content.replace("[preprocessing.sleap]\nenabled = false", "[preprocessing.sleap]\nenabled = true")
        else:
            config_content += "\n[preprocessing.sleap]\nenabled = true\n"
        result.config_path.write_text(config_content)

        # 3. Run flow
        config = SessionFlowConfig(
            config_path=str(result.config_path),
            subject_id=subject_id,
            session_id=session_id,
            skip_nwb_validation=True,
            skip_pose=False,
            skip_sleap=True,  # Skip generation, use pre-generated files
            skip_bpod=True,
        )
        flow_result = process_session_flow(config)

        # 4. Verify success
        assert flow_result.success, f"Flow failed: {flow_result.error}"
        assert flow_result.nwb_path.exists()

        # 5. Verify NWB content
        with NWBHDF5IO(str(flow_result.nwb_path), "r") as io:
            nwb = io.read()

            # Check Processing Module
            assert "behavior" in nwb.processing
            behavior_mod = nwb.processing["behavior"]

            # Check PoseEstimation
            pose_objects = [obj for obj in behavior_mod.data_interfaces.values() if "PoseEstimation" in obj.__class__.__name__]
            assert len(pose_objects) > 0, "No PoseEstimation objects found in behavior module"

            pe = pose_objects[0]

            # Verify source software is SLEAP
            # Note: ndx-pose might store this in description or specific field
            # Our build_pose_estimation sets source_software="SLEAP"
            # But accessing it might depend on the extension version
            # Let's check description
            assert "SLEAP" in pe.description or (hasattr(pe, "source_software") and pe.source_software == "SLEAP")

            # Check first series
            series = list(pe.pose_estimation_series.values())[0]
            assert series.data.shape[0] == n_frames

            # Check if skeleton is linked
            assert pe.skeleton is not None
            assert "nose" in pe.skeleton.nodes[:]
