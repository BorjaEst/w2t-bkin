"""Pose processing phase helpers."""

from typing import Dict, List, Optional, Tuple

from pynwb import NWBFile

from w2t_bkin.models import DiscoveryResult, PoseData, PosePlan, SessionInfo, TTLData


def assemble_pose_data(nwbfile: NWBFile, pose_data: Dict[str, List[PoseData]], session_info: SessionInfo, ttl_data: Dict[str, TTLData], run_logger):
    """Assemble pose estimation data into NWB file.

    Args:
        nwbfile: NWB file object
        pose_data: Dictionary of pose data by camera
        session_info: Session configuration
        ttl_data: TTL pulse data
        run_logger: Prefect logger
    """
    if not pose_data:
        return

    cameras_meta = session_info.metadata.get("cameras", [])
    camera_configs_dict = {cam["id"]: cam for cam in cameras_meta} if cameras_meta else {}

    pose_meta = session_info.metadata.get("pose", {})
    pose_cameras_config = pose_meta.get("cameras", {})
    skeletons_config = pose_meta.get("skeletons") or session_info.metadata.get("skeletons")

    for camera_id, pose_list in pose_data.items():
        camera_config = camera_configs_dict.get(camera_id, {}).copy()

        # Allow pose metadata to supply skeleton selection per camera
        pose_cam_cfg = pose_cameras_config.get(camera_id, {}) if isinstance(pose_cameras_config, dict) else {}
        if isinstance(pose_cam_cfg, dict) and pose_cam_cfg.get("skeleton_id"):
            camera_config["skeleton_id"] = pose_cam_cfg["skeleton_id"]

        tasks.assemble_pose_task(
            nwbfile=nwbfile,
            camera_id=camera_id,
            pose_data_list=pose_list,
            camera_config=camera_config,
            ttl_pulses=ttl_data if ttl_data else None,
            skeletons_config=skeletons_config,
        )

    run_logger.info(f"Assembled pose data for {len(pose_data)} cameras")
