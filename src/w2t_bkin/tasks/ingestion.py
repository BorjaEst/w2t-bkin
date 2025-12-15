"""Prefect tasks for data ingestion."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from prefect import task

from w2t_bkin.models import BpodData, PoseData, TrialAlignment, TTLData
from w2t_bkin.operations import align_trials_to_ttl, ingest_bpod_data, ingest_dlc_poses, ingest_sleap_poses, ingest_ttl_pulses

logger = logging.getLogger(__name__)


@task(
    name="Ingest Bpod Data",
    description="Parse Bpod behavioral data files",
    tags=["ingestion", "bpod", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_bpod_task(session_dir: Path, pattern: str, order: str = "time_asc", continuous_time: bool = False) -> BpodData:
    """Ingest Bpod behavioral data files.

    Prefect task wrapper for ingest_bpod_data operation.

    Args:
        session_dir: Path to session directory
        pattern: File pattern for Bpod data files
        order: Trial ordering ("time_asc", "time_desc", "file_order")
        continuous_time: Whether to use continuous time

    Returns:
        BpodData object with parsed data and trial count

    Raises:
        FileNotFoundError: If no Bpod files found
        ValueError: If parsing fails
    """
    logger.info(f"Ingesting Bpod data from {session_dir}")

    return ingest_bpod_data(session_dir=session_dir, pattern=pattern, order=order, continuous_time=continuous_time)


@task(
    name="Ingest DLC Poses",
    description="Load DLC pose estimation H5 files",
    tags=["ingestion", "dlc", "pose", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_dlc_poses_task(video_paths: List[Path], dlc_dir: Path, camera_id: str) -> List[PoseData]:
    """Ingest DLC pose estimation data for video files.

    Prefect task wrapper for ingest_dlc_poses operation.

    Args:
        video_paths: List of video file paths
        dlc_dir: Directory containing DLC H5 outputs
        camera_id: Camera identifier

    Returns:
        List of PoseData objects for successfully loaded poses
    """
    logger.info(f"Ingesting DLC poses for camera '{camera_id}'")

    return ingest_dlc_poses(video_paths=video_paths, dlc_dir=dlc_dir, camera_id=camera_id)


@task(
    name="Ingest SLEAP Poses",
    description="Load SLEAP pose estimation H5 files",
    tags=["ingestion", "sleap", "pose", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_sleap_poses_task(video_paths: List[Path], sleap_dir: Path, camera_id: str) -> List[PoseData]:
    """Ingest SLEAP pose estimation data for video files.

    Prefect task wrapper for ingest_sleap_poses operation.

    Args:
        video_paths: List of video file paths
        sleap_dir: Directory containing SLEAP H5 outputs
        camera_id: Camera identifier

    Returns:
        List of PoseData objects for successfully loaded poses
    """
    logger.info(f"Ingesting SLEAP poses for camera '{camera_id}'")

    return ingest_sleap_poses(video_paths=video_paths, sleap_dir=sleap_dir, camera_id=camera_id)


@task(
    name="Ingest TTL Pulses",
    description="Extract TTL pulse timestamps from files",
    tags=["ingestion", "ttl", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def ingest_ttl_task(session_dir: Path, ttl_patterns: Dict[str, str]) -> Dict[str, TTLData]:
    """Ingest TTL pulse timestamps from files.

    Prefect task wrapper for ingest_ttl_pulses operation.

    Args:
        session_dir: Path to session directory
        ttl_patterns: Dictionary mapping TTL ID to file pattern

    Returns:
        Dictionary mapping TTL ID to TTLData objects
    """
    logger.info(f"Ingesting TTL pulses from {session_dir}")

    return ingest_ttl_pulses(session_dir=session_dir, ttl_patterns=ttl_patterns)


@task(
    name="Align Trials to TTL",
    description="Align Bpod trials to TTL pulses for synchronization",
    tags=["ingestion", "sync", "alignment"],
    retries=1,
)
def align_trials_task(trial_type_configs: Dict, bpod_data: Dict[str, Any], ttl_pulses: Dict[str, List[float]]) -> TrialAlignment:
    """Align Bpod trials to TTL pulses for temporal synchronization.

    Prefect task wrapper for align_trials_to_ttl operation.

    Args:
        trial_type_configs: Trial type synchronization configurations
        bpod_data: Parsed Bpod data structure
        ttl_pulses: TTL pulse timestamps per channel

    Returns:
        TrialAlignment object with offsets and warnings
    """
    logger.info("Aligning Bpod trials to TTL pulses")

    return align_trials_to_ttl(trial_type_configs=trial_type_configs, bpod_data=bpod_data, ttl_pulses=ttl_pulses)
