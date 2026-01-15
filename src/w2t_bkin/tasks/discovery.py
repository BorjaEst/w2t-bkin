"""Prefect tasks for file discovery."""

import logging
from pathlib import Path
from typing import Dict, List

from prefect import task

from w2t_bkin import utils
from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.models import DiscoveryResult, SessionInfo
from w2t_bkin.operations import discover_bpod_files, discover_camera_files, discover_pose_files, discover_ttl_files

logger = logging.getLogger(__name__)


@task(
    name="Discover All Files",
    description="Discover all input files (cameras, Bpod, TTL)",
    tags=["discovery", "io"],
    cache_policy=None,
    retries=1,
)
def discover_all_files_task(info: SessionInfo, config: DiscoveryConfig) -> DiscoveryResult:
    """Discover all input files for the session.

    Prefect task wrapper for discover_all_files operation.
    Combines camera, Bpod, and TTL discovery into one task.

    Args:
        session_info: Session configuration

    Returns:
        DiscoveryResult with all discovered files
    """
    logger.info(f"Discovering all files for session {info.session_dir}")
    cameras = info.metadata.get("cameras", [])
    ttls = info.metadata.get("TTLs", [])
    bpod = info.metadata.get("bpod", None)
    pose = info.metadata.get("pose", {})

    logger.info(f"Discovering files in {info.raw_dir}")
    logger.debug(f"  Cameras: {len(cameras)}, TTLs: {len(ttls)}, Bpod: {bpod is not None}, Pose: {pose.keys()}")

    # Discover files
    camera_files = discover_camera_files(info.session_dir, cameras)
    ttl_files = discover_ttl_files(info.session_dir, ttls)
    bpod_files = discover_bpod_files(info.session_dir, bpod)
    pose = discover_pose_files(info.session_dir, pose)

    return DiscoveryResult(camera_files=camera_files, bpod_files=bpod_files, ttl_files=ttl_files)


@task(
    name="Count All Video Frames",
    description="Count total frames for all discovered camera videos",
    tags=["discovery", "io", "counting"],
    cache_policy=None,
    retries=1,
)
def verify_camera_ttl_sync_task(discovery: DiscoveryResult, config: DiscoveryConfig) -> Dict[str, int]:
    pass  # TODO: Implement this task using count_all_camera_frames operation
