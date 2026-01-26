"""Unit tests for pose assembly task behavior."""

import datetime
import logging
from pathlib import Path

from pynwb import NWBFile

from w2t_bkin.config import AssemblyConfig
from w2t_bkin.ingest.pose import PoseMetadata
from w2t_bkin.models import PoseData
from w2t_bkin.tasks import assembly as assembly_tasks


def test_assemble_pose_estimation_handles_none_video_and_ttl(monkeypatch, caplog, tmp_path: Path) -> None:
    """Should assemble pose when video and TTL metadata are missing."""
    logger = logging.getLogger("test_pose_assembly_task")
    logger.setLevel(logging.DEBUG)
    monkeypatch.setattr(assembly_tasks, "get_run_logger", lambda: logger)

    nwbfile = NWBFile(
        session_description="test",
        identifier="test",
        session_start_time=datetime.datetime.now(datetime.timezone.utc),
    )

    frames = [
        {
            "frame_index": 0,
            "keypoints": {
                "nose": {"name": "nose", "x": 1.0, "y": 2.0, "confidence": 0.9},
                "ear_left": {"name": "ear_left", "x": 1.5, "y": 2.5, "confidence": 0.8},
            },
        },
        {
            "frame_index": 1,
            "keypoints": {
                "nose": {"name": "nose", "x": 1.1, "y": 2.1, "confidence": 0.91},
                "ear_left": {"name": "ear_left", "x": 1.6, "y": 2.6, "confidence": 0.81},
            },
        },
    ]

    metadata = PoseMetadata(
        confidence_definition="likelihood",
        scorer="test_scorer",
        source_software="DeepLabCut",
        source_software_version="0.0.0",
        bodyparts=["nose", "ear_left"],
    )

    pose_item = PoseData(
        camera_id="camera_0",
        video_path=tmp_path / "video.mp4",
        pose_path=tmp_path / "pose.h5",
        frames=frames,
        metadata=metadata,
    )

    pose_data = {"camera_0": [pose_item]}

    caplog.set_level(logging.WARNING)

    assembly_tasks.assemble_pose_estimation.fn(
        nwbfile=nwbfile,
        pose_data=pose_data,
        video_data=None,
        ttl_data=None,
        config=AssemblyConfig(),
    )

    # Idempotent retry should not raise or duplicate
    assembly_tasks.assemble_pose_estimation.fn(
        nwbfile=nwbfile,
        pose_data=pose_data,
        video_data=None,
        ttl_data=None,
        config=AssemblyConfig(),
    )

    behavior_module = nwbfile.processing["behavior"]
    assert "Skeletons" in behavior_module.data_interfaces

    pose_objects = [obj for obj in behavior_module.data_interfaces.values() if obj.__class__.__name__ == "PoseEstimation"]
    assert len(pose_objects) == 1

    skeletons_container = behavior_module.data_interfaces["Skeletons"]
    skeleton_names = []
    if hasattr(skeletons_container, "skeletons"):
        skeletons = skeletons_container.skeletons
        if isinstance(skeletons, dict):
            skeleton_names = list(skeletons.keys())
        elif isinstance(skeletons, list):
            skeleton_names = [skeleton.name for skeleton in skeletons]
    assert any("skeleton" in name for name in skeleton_names)

    assert any("Video metadata not provided" in message for message in caplog.messages)
    assert any("TTL data not provided" in message for message in caplog.messages)
