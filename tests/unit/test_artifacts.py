from pathlib import Path
from unittest.mock import patch

import pytest

from w2t_bkin.config import ArtifactsConfig
from w2t_bkin.models import DiscoveryResult, SessionInfo
from w2t_bkin.operations.pose_generator import auto_pose_artifacts, discover_pose_artifacts, generate_pose_artifacts
from w2t_bkin.processors.dlc import DLCInferenceResult


def _session_info(tmp_path: Path, metadata: dict) -> SessionInfo:
    raw_dir = tmp_path / "raw"
    interim_dir = tmp_path / "interim"
    processed_dir = tmp_path / "processed"
    models_dir = tmp_path / "models"
    raw_dir.mkdir()
    interim_dir.mkdir()
    processed_dir.mkdir()
    models_dir.mkdir()

    return SessionInfo(
        subject_id="subject-001",
        session_id="session-001",
        metadata=metadata,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
        models_dir=models_dir,
    )


def test_discover_pose_artifacts_finds_dlc_h5(tmp_path: Path):
    video_path = tmp_path / "raw" / "cam0_video.avi"

    metadata = {
        "cameras": [{"id": "camera_0", "paths": "Video/*.avi", "optional": False}],
        "pose": {
            "models": {"dlc_cam0": {"source": "dlc", "path": "iteration-1/model/config.yaml", "artifacts": "dlc-pose"}},
            "cameras": {"camera_0": {"source": "dlc", "model_id": "dlc_cam0"}},
        },
    }

    info = _session_info(tmp_path, metadata)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_text("fake video")

    dlc_dir = info.interim_dir / "dlc-pose" / "camera_0"
    dlc_dir.mkdir(parents=True, exist_ok=True)
    expected_h5 = dlc_dir / f"{video_path.stem}DLC_test_model.h5"
    expected_h5.write_text("fake h5")

    discovery = DiscoveryResult(
        camera_files={"camera_0": [video_path]},
        bpod_files={},
        ttl_files={},
        pose_files={},
        models_files={},
    )

    artifacts = discover_pose_artifacts(discovery, info)
    assert "camera_0" in artifacts.pose_h5_by_camera
    assert expected_h5 in artifacts.pose_h5_by_camera["camera_0"]


def test_generate_pose_artifacts_calls_dlc_and_returns_paths(tmp_path: Path):
    video_path = tmp_path / "raw" / "cam0_video.avi"

    metadata = {
        "cameras": [{"id": "camera_0", "paths": "Video/*.avi", "optional": False}],
        "pose": {
            "models": {"dlc_cam0": {"source": "dlc", "path": "iteration-1/model/config.yaml", "artifacts": "dlc-pose"}},
            "cameras": {"camera_0": {"source": "dlc", "model_id": "dlc_cam0"}},
        },
    }

    info = _session_info(tmp_path, metadata)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_text("fake video")

    # Model file must exist because generate_pose_artifacts checks it pre-call
    model_config = info.models_dir / "iteration-1/model/config.yaml"
    model_config.parent.mkdir(parents=True, exist_ok=True)
    model_config.write_text("Task: test\nbodyparts: [nose]\n")

    output_dir = info.interim_dir / "dlc-pose" / "camera_0"
    expected_h5 = output_dir / f"{video_path.stem}DLC_test_model.h5"

    discovery = DiscoveryResult(
        camera_files={"camera_0": [video_path]},
        bpod_files={},
        ttl_files={},
        pose_files={},
        models_files={},
    )

    fake_result = DLCInferenceResult(
        video_path=video_path,
        h5_output_path=expected_h5,
        csv_output_path=None,
        model_config_path=model_config,
        frame_count=10,
        inference_time_s=0.1,
        gpu_used=None,
        success=True,
        error_message=None,
    )

    with patch("w2t_bkin.operations.pose_generator.dlc.run_dlc_inference_batch", return_value=[fake_result]):
        artifacts = generate_pose_artifacts(discovery, info, ArtifactsConfig())
        assert artifacts.pose_h5_by_camera["camera_0"] == [expected_h5]


def test_auto_pose_artifacts_prefers_discovery(tmp_path: Path):
    video_path = tmp_path / "raw" / "cam0_video.avi"

    metadata = {
        "cameras": [{"id": "camera_0", "paths": "Video/*.avi", "optional": False}],
        "pose": {
            "models": {"dlc_cam0": {"source": "dlc", "path": "iteration-1/model/config.yaml", "artifacts": "dlc-pose"}},
            "cameras": {"camera_0": {"source": "dlc", "model_id": "dlc_cam0"}},
        },
    }

    info = _session_info(tmp_path, metadata)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_text("fake video")

    dlc_dir = info.interim_dir / "dlc-pose" / "camera_0"
    dlc_dir.mkdir(parents=True, exist_ok=True)
    expected_h5 = dlc_dir / f"{video_path.stem}DLC_test_model.h5"
    expected_h5.write_text("fake h5")

    discovery = DiscoveryResult(
        camera_files={"camera_0": [video_path]},
        bpod_files={},
        ttl_files={},
        pose_files={},
        models_files={},
    )

    with patch("w2t_bkin.operations.pose_generator.dlc.run_dlc_inference_batch") as mocked:
        artifacts = auto_pose_artifacts(discovery, info, ArtifactsConfig())
        assert expected_h5 in artifacts.pose_h5_by_camera["camera_0"]
        mocked.assert_not_called()
