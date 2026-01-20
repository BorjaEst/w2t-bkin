"""Prefect tasks for data ingestion."""

import logging
from typing import Any, Dict, List, Optional

from prefect import get_run_logger, task

from w2t_bkin.config import IngestionConfig
from w2t_bkin.models import ArtifactsResult, BpodData, DiscoveryResult, PoseData, SessionInfo, TTLData, VideoData
from w2t_bkin.operations import ingestion as ingestion_ops

logger = logging.getLogger(__name__)


@task(
    name="Ingest TTL Pulses",
    description="Extract TTL pulse timestamps from files",
    tags=["ingestion", "ttl", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_ttl_task(discovery: DiscoveryResult, info: SessionInfo, config: IngestionConfig) -> Dict[str, TTLData]:
    """Ingest TTL pulse data from discovered files.

    Args:
        discovery: Discovery result containing ttl_files
        info: Session information
        config: Ingestion configuration

    Returns:
        Dict mapping ttl_id to TTLData
    """
    run_logger = get_run_logger()
    run_logger.info(f"Ingesting TTL pulses for session {info.session_id}")

    # Delegate to pure operation
    ttl_data = ingestion_ops.ingest_ttls(discovery=discovery, info=info)

    run_logger.info(f"Completed TTL ingestion: {len(ttl_data)} channel(s)")
    return ttl_data


@task(
    name="Ingest Video Data",
    description="Load video files and metadata",
    tags=["ingestion", "video", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_video_task(
    discovery: DiscoveryResult,
    info: SessionInfo,
    config: IngestionConfig,
    ttl_data: Optional[Dict[str, TTLData]] = None,
) -> Dict[str, VideoData]:
    """Ingest video metadata with optional TTL validation.

    Args:
        discovery: Discovery result containing camera_files
        info: Session information
        config: Ingestion configuration
        ttl_data: TTL data (required if ttl_validation enabled)

    Returns:
        Dict mapping camera_id to VideoData
    """
    run_logger = get_run_logger()
    run_logger.info(f"Ingesting video data for session {info.session_id}")

    # Delegate to pure operation
    video_data = ingestion_ops.ingest_videos(
        discovery=discovery,
        info=info,
        ttl_data=ttl_data,
        enable_loading=config.video.enable_loading,
        ttl_validation=config.video.ttl_validation,
        ttl_tolerance=config.video.ttl_tolerance,
        mismatch_warn_only=config.video.mismatch_warn_only,
    )

    run_logger.info(f"Completed video ingestion: {len(video_data)} camera(s)")
    return video_data


@task(
    name="Ingest Bpod Data",
    description="Parse Bpod behavioral data files",
    tags=["ingestion", "bpod", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_bpod_task(discovery: DiscoveryResult, info: SessionInfo, config: IngestionConfig) -> Optional[BpodData]:
    """Ingest Bpod behavioral data from discovered files.

    Args:
        discovery: Discovery result containing bpod_files
        info: Session information
        config: Ingestion configuration

    Returns:
        BpodData or None if no files or loading disabled
    """
    run_logger = get_run_logger()
    run_logger.info(f"Ingesting Bpod data for session {info.session_id}")

    # Delegate to pure operation
    bpod_data = ingestion_ops.ingest_bpod(
        discovery=discovery,
        info=info,
        enable_loading=config.bpod.enable_loading,
        continuous_time=config.bpod.continuous_time,
    )

    if bpod_data:
        run_logger.info(f"Completed Bpod ingestion: {bpod_data.n_trials} trials")
    else:
        run_logger.info("Bpod ingestion returned None (no data or disabled)")

    return bpod_data


@task(
    name="Ingest Pose Data",
    description="Load pose estimation data from files",
    tags=["ingestion", "dlc", "pose", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_pose_task(discovery: DiscoveryResult, artifacts: ArtifactsResult, info: SessionInfo, config: IngestionConfig) -> Dict[str, List[PoseData]]:
    """Ingest pose estimation data from artifacts or discovery.

    Args:
        discovery: Discovery result
        artifacts: Artifacts result containing pose file paths
        info: Session information
        config: Ingestion configuration

    Returns:
        Dict mapping camera_id to list of PoseData
    """
    run_logger = get_run_logger()
    run_logger.info(f"Ingesting pose data for session {info.session_id}")

    # Delegate to pure operation
    pose_data = ingestion_ops.ingest_pose(
        discovery=discovery,
        artifacts=artifacts,
        info=info,
        enable_loading=config.pose.enable_loading,
        file_type=config.pose.file_type,
    )

    run_logger.info(f"Completed pose ingestion: {len(pose_data)} camera(s)")
    return pose_data
