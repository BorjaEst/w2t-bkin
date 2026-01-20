"""Prefect tasks for file discovery."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from prefect import task

from w2t_bkin import utils
from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.metadata import PoseMeta
from w2t_bkin.models import DiscoveryResult, SessionInfo
from w2t_bkin.operations.discovery import discover_bpod_files, discover_camera_files, discover_pose_files, discover_pose_models, discover_ttl_files

logger = logging.getLogger(__name__)


@task(
    name="Discover All Files",
    description="Discover all input files (cameras, Bpod, TTL)",
    tags=["discovery", "io"],
    cache_policy=None,
    retries=1,
)
def discover_all_files_task(info: SessionInfo, config: Optional[DiscoveryConfig] = None) -> DiscoveryResult:
    """Discover all input files for the session.

    Prefect task wrapper for discover_all_files operation.
    Combines camera, Bpod, and TTL discovery into one task.

    Args:
        info: Session configuration
        config: Discovery configuration (defaults to all enabled if not provided)

    Returns:
        DiscoveryResult with all discovered files
    """
    config = config or DiscoveryConfig()

    logger.info(f"Discovering all files for session {info.session_id} in {info.raw_dir}")
    cameras = info.metadata.cameras if config.discover_cameras else []
    ttls = info.metadata.TTLs if config.discover_ttl_signals else []
    bpod = info.metadata.bpod if config.discover_bpod else None
    pose = info.metadata.pose if config.discover_pose else PoseMeta()
    logger.debug(f"  Cameras: {len(cameras)}, TTLs: {len(ttls)}, Bpod: {bpod is not None}, Pose: {list(pose.models.keys())}")

    logger.info(f"Discovering all models for session {info.session_id}")
    models = info.metadata.pose.models if config.discover_models else {}
    logger.debug(f"  Models: {models.keys()}")

    return DiscoveryResult(
        camera_files=discover_camera_files(info.raw_dir, cameras),
        ttl_files=discover_ttl_files(info.raw_dir, ttls),
        bpod_files=discover_bpod_files(info.raw_dir, bpod),
        pose_files=discover_pose_files(info.raw_dir, pose),
        models_files=discover_pose_models(info.models_dir, models),
    )
