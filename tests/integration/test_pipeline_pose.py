"""Integration tests for Pose Ingestion in SessionPipeline."""

from pathlib import Path
import shutil

from pynwb import NWBHDF5IO
import pytest

from synthetic import build_raw_folder
from synthetic.pose_synth import PoseH5Params, create_dlc_pose_h5
from w2t_bkin.core.pipeline import RunOptions, SessionPipeline


class TestPipelinePoseIngestion:
    """Test pose ingestion logic."""

    def test_Should_IngestPoseData_When_FilesExist(self, tmp_path):
        """Should successfully ingest DLC pose data into NWB."""

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

        # 2. Create Interim DLC Data
        # Pipeline expects: interim_root / subject_id / session_id / "dlc-pose" / camera_id / "{video_stem}DLC_*.h5"
        dlc_dir = interim_root / subject_id / session_id / "dlc-pose" / camera_id
        dlc_dir.mkdir(parents=True, exist_ok=True)

        # Get video stem from generated raw files
        # result.video_paths contains all videos. We need the one for cam0.
        # build_raw_folder generates videos like "cam0_...avi"
        video_path = next(p for p in result.video_paths if camera_id in p.name)
        video_stem = video_path.stem

        dlc_filename = f"{video_stem}DLC_resnet50_model_shuffle1_100000.h5"
        dlc_path = dlc_dir / dlc_filename

        # Generate synthetic DLC H5 content
        pose_params = PoseH5Params(
            keypoints=["nose", "tail_base"],
            n_frames=n_frames,
            fps=30.0,
        )
        create_dlc_pose_h5(dlc_path, pose_params)

        # 2.5 Update config to enable DLC preprocessing
        # The synthetic config generator defaults to dlc.enabled=False
        config_content = result.config_path.read_text()
        if "[preprocessing.dlc]" not in config_content:
            # Append if missing (it should be there now with my changes, but defaults to false)
            # Actually, since I just updated config_synth.py, build_raw_folder will write it.
            # But build_raw_folder uses defaults, so enabled=False.
            # We can just replace it.
            config_content = config_content.replace("enabled = false", "enabled = true")
            # If it wasn't there (e.g. if I didn't update config_synth correctly), append it
            if "enabled = true" not in config_content:
                config_content += "\n[preprocessing.dlc]\nenabled = true\n"
        else:
            config_content = config_content.replace("enabled = false", "enabled = true")

        result.config_path.write_text(config_content)

        # 3. Initialize pipeline
        # Ensure config points to our interim root
        # build_raw_folder sets intermediate_root to out_root.parent / "interim"
        # which matches our tmp_path / "interim" if raw_root is tmp_path / "raw"

        pipeline = SessionPipeline(
            config_path=result.config_path,
            subject_id=subject_id,
            session_id=session_id,
            options=RunOptions(
                skip_nwb_validation=True,
                skip_pose=False,  # Enable pose
                skip_bpod=True,  # Skip bpod to focus on pose
            ),
        )

        # 4. Run pipeline
        run_result = pipeline.run()

        # 5. Verify success
        assert run_result.success, f"Pipeline failed: {run_result.error}"
        assert run_result.nwb_path.exists()

        # 6. Verify NWB content
        with NWBHDF5IO(str(run_result.nwb_path), "r") as io:
            nwb = io.read()

            # Check Processing Module
            assert "behavior" in nwb.processing
            behavior_mod = nwb.processing["behavior"]

            # Check PoseEstimation
            # Name format: "pose_{camera_id}" or similar?
            # In pipeline.py: pe = pose.build_pose_estimation(...) -> name defaults to 'pose_estimation' or similar?
            # Wait, pose.build_pose_estimation usually sets name.
            # Let's check if any object in behavior_mod is PoseEstimation

            pose_objects = [obj for obj in behavior_mod.data_interfaces.values() if "PoseEstimation" in obj.__class__.__name__]
            assert len(pose_objects) > 0, "No PoseEstimation objects found in behavior module"

            pe = pose_objects[0]
            # PoseEstimation contains PoseEstimationSeries
            assert len(pe.pose_estimation_series) > 0

            # Check first series
            series = list(pe.pose_estimation_series.values())[0]
            assert series.data.shape[0] == n_frames

            # Check if skeleton is linked
            assert pe.skeleton is not None
            assert "nose" in pe.skeleton.nodes[:]
