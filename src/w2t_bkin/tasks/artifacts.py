"""Prefect tasks for artifact generation (DLC, SLEAP)."""

import logging
from pathlib import Path
from typing import Dict, List

from prefect import task

from w2t_bkin.models import DLCArtifact, SessionConfig, SLEAPArtifact
from w2t_bkin.operations import discover_dlc_poses, discover_sleap_poses, generate_dlc_poses, generate_dlc_poses_for_session

logger = logging.getLogger(__name__)


@task(
    name="Generate DLC Poses",
    description="Run DLC pose estimation on video files",
    tags=["artifact", "dlc", "gpu"],
    retries=1,
    retry_delay_seconds=30,
    timeout_seconds=3600,  # 1 hour timeout for GPU tasks
)
def generate_dlc_poses_task(
    video_paths: List[Path], model_path: Path, output_dir: Path, camera_id: str, force_rerun: bool = False, gpu_index: int | None = None, save_csv: bool = False
) -> List[DLCArtifact]:
    """Generate DLC pose estimation for video files.

    Prefect task wrapper for generate_dlc_poses operation.
    This is a GPU-intensive task that should be routed to GPU workers.

    Args:
        video_paths: List of video file paths to process
        model_path: Path to DLC model config.yaml
        output_dir: Directory to write H5 output files
        camera_id: Camera identifier
        force_rerun: If True, regenerate even if outputs exist
        gpu_index: GPU index to use (None for auto-detect)
        save_csv: Also generate CSV output files

    Returns:
        List of DLCArtifact objects with paths to generated/cached H5 files

    Raises:
        ValueError: If model validation fails
        RuntimeError: If DLC inference fails
    """
    logger.info(f"Generating DLC poses for camera '{camera_id}' " f"({len(video_paths)} video(s))")

    return generate_dlc_poses(
        video_paths=video_paths, model_path=model_path, output_dir=output_dir, camera_id=camera_id, force_rerun=force_rerun, gpu_index=gpu_index, save_csv=save_csv
    )


@task(
    name="Generate DLC Session",
    description="Run DLC pose estimation for all cameras in session",
    tags=["artifact", "dlc", "gpu", "session"],
    retries=1,
    retry_delay_seconds=30,
    timeout_seconds=7200,  # 2 hour timeout for full session
)
def generate_dlc_session_task(session_config: SessionConfig, force_rerun: bool = False) -> Dict[str, List[DLCArtifact]]:
    """Generate DLC pose estimation for all cameras in a session.

    Prefect task wrapper for generate_dlc_poses_for_session operation.
    Convenience task that processes all cameras configured for DLC.

    Args:
        session_config: Session configuration
        force_rerun: If True, regenerate even if outputs exist

    Returns:
        Dictionary mapping camera_id to list of DLCArtifact objects

    Raises:
        ValueError: If DLC not enabled or not properly configured
    """
    logger.info(f"Generating DLC poses for session {session_config.session_id}")

    return generate_dlc_poses_for_session(session_config=session_config, force_rerun=force_rerun)


@task(
    name="Discover DLC Poses",
    description="Discover existing DLC pose estimation outputs",
    tags=["artifact", "dlc", "discovery"],
    cache_policy=None,
    retries=1,
)
def discover_dlc_poses_task(video_paths: List[Path], dlc_dir: Path, camera_id: str) -> List[DLCArtifact]:
    """Discover existing DLC pose estimation outputs.

    Prefect task wrapper for discover_dlc_poses operation.
    Does not execute DLC inference - only finds existing outputs.

    Args:
        video_paths: List of video file paths to find DLC outputs for
        dlc_dir: Directory containing DLC H5 output files
        camera_id: Camera identifier

    Returns:
        List of DLCArtifact objects for found H5 files
    """
    logger.info(f"Discovering DLC poses for camera '{camera_id}' ({len(video_paths)} video(s))")

    return discover_dlc_poses(video_paths=video_paths, dlc_dir=dlc_dir, camera_id=camera_id)


@task(
    name="Discover SLEAP Poses",
    description="Discover existing SLEAP pose estimation outputs",
    tags=["artifact", "sleap", "discovery"],
    cache_policy=None,
    retries=1,
)
def discover_sleap_poses_task(video_paths: List[Path], sleap_dir: Path, camera_id: str) -> List[SLEAPArtifact]:
    """Discover existing SLEAP pose estimation outputs.

    Prefect task wrapper for discover_sleap_poses operation.
    Does not execute SLEAP inference - only finds existing outputs.

    Args:
        video_paths: List of video file paths to find SLEAP outputs for
        sleap_dir: Directory containing SLEAP H5 output files
        camera_id: Camera identifier

    Returns:
        List of SLEAPArtifact objects for found H5 files
    """
    logger.info(f"Discovering SLEAP poses for camera '{camera_id}' " f"({len(video_paths)} video(s))")

    return discover_sleap_poses(video_paths=video_paths, sleap_dir=sleap_dir, camera_id=camera_id)
