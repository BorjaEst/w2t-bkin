"""Prefect tasks for file discovery."""

import logging
from pathlib import Path
from typing import Dict, List

from prefect import task

from w2t_bkin.models import DiscoveryResult, SessionConfig
from w2t_bkin.operations import discover_all_files, discover_bpod_files, discover_camera_files, discover_ttl_files

logger = logging.getLogger(__name__)


@task(
    name="Discover Camera Files",
    description="Discover video files for all cameras",
    tags=["discovery", "io", "camera"],
    cache_policy=None,  # Cache disabled - files may change
    retries=1,
)
def discover_camera_files_task(session_config: SessionConfig) -> Dict[str, List[Path]]:
    """Discover video files for all configured cameras.

    Prefect task wrapper for discover_camera_files operation.

    Args:
        session_config: Session configuration

    Returns:
        Dictionary mapping camera_id to list of video file paths
    """
    logger.info(f"Discovering camera files for session {session_config.session_id}")

    return discover_camera_files(session_config)


@task(
    name="Discover Bpod Files",
    description="Discover Bpod behavioral data files",
    tags=["discovery", "io", "bpod"],
    cache_policy=None,
    retries=1,
)
def discover_bpod_files_task(session_config: SessionConfig) -> Dict[str, List[Path]]:
    """Discover Bpod data files.

    Prefect task wrapper for discover_bpod_files operation.

    Args:
        session_config: Session configuration

    Returns:
        Dictionary mapping bpod_id to list of file paths
    """
    logger.info(f"Discovering Bpod files for session {session_config.session_id}")

    return discover_bpod_files(session_config)


@task(
    name="Discover TTL Files",
    description="Discover TTL pulse files",
    tags=["discovery", "io", "ttl"],
    cache_policy=None,
    retries=1,
)
def discover_ttl_files_task(session_config: SessionConfig) -> Dict[str, List[Path]]:
    """Discover TTL pulse files.

    Prefect task wrapper for discover_ttl_files operation.

    Args:
        session_config: Session configuration

    Returns:
        Dictionary mapping ttl_id to list of file paths
    """
    logger.info(f"Discovering TTL files for session {session_config.session_id}")

    return discover_ttl_files(session_config)


@task(
    name="Discover All Files",
    description="Discover all input files (cameras, Bpod, TTL)",
    tags=["discovery", "io"],
    cache_policy=None,
    retries=1,
)
def discover_all_files_task(session_config: SessionConfig) -> DiscoveryResult:
    """Discover all input files for the session.

    Prefect task wrapper for discover_all_files operation.
    Combines camera, Bpod, and TTL discovery into one task.

    Args:
        session_config: Session configuration

    Returns:
        DiscoveryResult with all discovered files
    """
    logger.info(f"Discovering all files for session {session_config.session_id}")

    return discover_all_files(session_config)
