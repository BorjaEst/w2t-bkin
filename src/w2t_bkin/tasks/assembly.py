"""Prefect tasks for NWB data structure assembly."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from prefect import task
from pynwb import NWBFile

from w2t_bkin.models import BpodData, PoseData, TTLData
from w2t_bkin.operations import add_skeletons_container, assemble_behavior_tables, assemble_pose_estimation

logger = logging.getLogger(__name__)


@task(
    name="Assemble Behavior Tables",
    description="Build behavior tables (trials, states, events, actions)",
    tags=["assembly", "nwb", "behavior"],
    retries=1,
    timeout_seconds=600,  # 10 minute timeout
)
def assemble_behavior_task(nwbfile: NWBFile, bpod_data: BpodData, trial_offsets: List[float]) -> Tuple[Any, Any, Any]:
    """Assemble behavior tables and add to NWB file.

    Prefect task wrapper for assemble_behavior_tables operation.
    Modifies nwbfile in place by adding trials, task_recording, and task.

    Args:
        nwbfile: NWB file object to modify
        bpod_data: Parsed Bpod data
        trial_offsets: Trial offset times for alignment

    Returns:
        Tuple of (trials_table, task_recording, task) objects

    Raises:
        ValueError: If data extraction fails
    """
    logger.info("Assembling behavior tables")

    return assemble_behavior_tables(nwbfile=nwbfile, bpod_data=bpod_data, trial_offsets=trial_offsets)


@task(
    name="Assemble Pose Estimation",
    description="Build pose estimation objects for one camera",
    tags=["assembly", "nwb", "pose"],
    retries=1,
    timeout_seconds=300,  # 5 minute timeout
)
def assemble_pose_task(
    nwbfile: NWBFile,
    camera_id: str,
    pose_data_list: List[PoseData],
    camera_config: Dict[str, Any],
    ttl_pulses: Optional[Dict[str, TTLData]],
    skeletons_config: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """Assemble pose estimation data for one camera and add to NWB file.

    Prefect task wrapper for assemble_pose_estimation operation.
    Modifies nwbfile in place by adding PoseEstimation objects.

    Args:
        nwbfile: NWB file object to modify
        camera_id: Camera identifier
        pose_data_list: List of PoseData for this camera
        camera_config: Camera configuration (fps, ttl_id, skeleton_id)
        ttl_pulses: TTL pulse data (optional for timestamp alignment)
        skeletons_config: Skeleton definitions (optional)

    Returns:
        List of created PoseEstimation objects

    Raises:
        ValueError: If pose assembly fails
    """
    logger.info(f"Assembling pose estimation for camera '{camera_id}'")

    return assemble_pose_estimation(
        nwbfile=nwbfile, camera_id=camera_id, pose_data_list=pose_data_list, camera_config=camera_config, ttl_pulses=ttl_pulses, skeletons_config=skeletons_config
    )


@task(
    name="Add Skeletons Container",
    description="Add Skeletons container to NWB file",
    tags=["assembly", "nwb", "pose"],
    retries=1,
)
def add_skeletons_task(nwbfile: NWBFile, skeletons: List[Any]) -> Any:
    """Add Skeletons container to NWB file.

    Prefect task wrapper for add_skeletons_container operation.
    Modifies nwbfile in place.

    Args:
        nwbfile: NWB file object to modify
        skeletons: List of Skeleton objects

    Returns:
        Skeletons container object

    Raises:
        ValueError: If skeletons container creation fails
    """
    logger.info(f"Adding Skeletons container with {len(skeletons)} skeleton(s)")

    return add_skeletons_container(nwbfile=nwbfile, skeletons=skeletons)
