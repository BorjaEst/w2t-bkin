"""Prefect tasks for data ingestion."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from prefect import task

from w2t_bkin.config import IngestionConfig
from w2t_bkin.models import ArtifactsResult, BpodData, DiscoveryResult, PoseData, SessionInfo, TTLData, VideoData
from w2t_bkin.operations import ingestion

logger = logging.getLogger(__name__)


# NOTE IMPORTANT THE VALIDATION PROCESS LIKE COUNTING TRIALS ETC SHOULD BE DONE IN THE INGESTION STEP
# THIS IS CONTOLLED BY THE INGESTION CONFIG,
# FOR EXAMPLE IN VIDEO INGEST, IF CONFIG SAYS ttl_validation TRUE, WE VALIDATE THE VIDEO FILES AGAINST THE TTL DATA


@task(
    name="Ingest TTL Pulses",
    description="Extract TTL pulse timestamps from files",
    tags=["ingestion", "ttl", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_ttl_task(discovery: DiscoveryResult, info: SessionInfo, config: IngestionConfig) -> Dict[str, TTLData]:
    logger.info(f"Ingesting TTL pulses for session {info.session_id}")
    # TODO: complete ingestion operation


@task(
    name="Ingest Video Data",
    description="Load video files and metadata",
    tags=["ingestion", "video", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_video_taks(discovery: DiscoveryResult, TTL_data: Dict[str, TTLData], info: SessionInfo, config: IngestionConfig) -> Dict[str, VideoData]:
    logger.info(f"Ingesting TTL pulses for session {info.session_id}")
    # TODO: complete ingestion operation
    # TODO: Here we validate according to config and load video metadata, we need ttl data


@task(
    name="Ingest Bpod Data",
    description="Parse Bpod behavioral data files",
    tags=["ingestion", "bpod", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_bpod_task(session_dir: Path, pattern: str, order: str = "time_asc", continuous_time: bool = False) -> BpodData:
    logger.info(f"Ingesting Bpod data from {session_dir}")
    # TODO: complete ingestion operation


@task(
    name="Ingest Pose Data",
    description="Load pose estimation data from files",
    tags=["ingestion", "dlc", "pose", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_pose_data(discovery: DiscoveryResult, artifacts: ArtifactsResult, info: SessionInfo, config: IngestionConfig) -> Dict[str, PoseData]:
    logger.info(f"Ingesting pose data for session {info.session_id}")
    # TODO: complete ingestion operation
