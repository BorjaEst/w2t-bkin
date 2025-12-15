"""Pure functions for discovering files in session directories."""

import logging
from pathlib import Path
from typing import Dict, List

from w2t_bkin import utils
from w2t_bkin.exceptions import IngestError
from w2t_bkin.models import DiscoveryResult, SessionConfig

logger = logging.getLogger(__name__)


def discover_camera_files(session_dir: Path, camera_configs: List[Dict], sort_order: str = "name_asc") -> Dict[str, List[Path]]:
    """Discover video files for all configured cameras.

    Pure function that searches for video files matching camera patterns.

    Args:
        session_dir: Path to session directory
        camera_configs: List of camera configuration dictionaries
        sort_order: File sorting order ("name_asc", "name_desc", "mtime_asc", "mtime_desc")

    Returns:
        Dictionary mapping camera_id to list of video file paths

    Raises:
        IngestError: If required camera files not found
    """
    camera_files = {}

    for camera in camera_configs:
        camera_id = camera["id"]
        pattern = camera["paths"]
        order = camera.get("order", sort_order)
        optional = camera.get("optional", False)

        logger.debug(f"Scanning camera '{camera_id}': pattern={pattern}, optional={optional}")

        # Discover files matching pattern
        video_paths = utils.discover_files(session_dir, pattern, sort=False)

        if not video_paths:
            if optional:
                logger.warning(f"Camera '{camera_id}' is optional and no files found - skipping")
                camera_files[camera_id] = []
                continue
            else:
                raise IngestError(
                    message=f"No video files found for camera '{camera_id}'",
                    context={"camera_id": camera_id, "pattern": pattern},
                    hint=f"Check that files exist matching pattern: {pattern}. " f"If this camera is optional, set 'optional = true' in metadata.",
                )

        # Sort files according to specified order
        video_paths = utils.sort_files(video_paths, order)
        camera_files[camera_id] = video_paths

        logger.info(f"Camera '{camera_id}': found {len(video_paths)} file(s)")
        logger.debug(f"  Files: {[p.name for p in video_paths]}")

    return camera_files


def discover_bpod_files(session_dir: Path, bpod_config: Dict) -> Dict[str, List[Path]]:
    """Discover Bpod data files.

    Args:
        session_dir: Path to session directory
        bpod_config: Bpod configuration dictionary

    Returns:
        Dictionary with 'bpod' key mapping to list of file paths
    """
    if not bpod_config:
        logger.debug("No Bpod configuration - skipping discovery")
        return {"bpod": []}

    pattern = bpod_config.get("paths", "Bpod/*.mat")
    order = bpod_config.get("order", "name_asc")

    logger.debug(f"Scanning Bpod files: pattern={pattern}")

    file_paths = utils.discover_files(session_dir, pattern, sort=False)

    if not file_paths:
        logger.warning(f"No Bpod files found matching pattern: {pattern}")
        return {"bpod": []}

    # Sort files
    file_paths = utils.sort_files(file_paths, order)

    logger.info(f"Bpod: found {len(file_paths)} file(s)")
    logger.debug(f"  Files: {[p.name for p in file_paths]}")

    return {"bpod": file_paths}


def discover_ttl_files(session_dir: Path, ttl_configs: List[Dict]) -> Dict[str, List[Path]]:
    """Discover TTL channel files.

    Args:
        session_dir: Path to session directory
        ttl_configs: List of TTL configuration dictionaries

    Returns:
        Dictionary mapping ttl_id to list of file paths
    """
    ttl_files = {}

    for ttl in ttl_configs:
        ttl_id = ttl["id"]
        pattern = ttl["paths"]
        order = ttl.get("order", "name_asc")

        logger.debug(f"Scanning TTL '{ttl_id}': pattern={pattern}")

        file_paths = utils.discover_files(session_dir, pattern, sort=False)

        if not file_paths:
            logger.warning(f"No TTL files found for '{ttl_id}' matching: {pattern}")
            ttl_files[ttl_id] = []
            continue

        # Sort files
        file_paths = utils.sort_files(file_paths, order)

        logger.info(f"TTL '{ttl_id}': found {len(file_paths)} file(s)")
        logger.debug(f"  Files: {[p.name for p in file_paths]}")

        ttl_files[ttl_id] = file_paths

    return ttl_files


def discover_all_files(session_config: SessionConfig) -> DiscoveryResult:
    """Discover all files for a session.

    Convenience function that discovers cameras, Bpod, and TTL files.

    Args:
        session_config: Session configuration

    Returns:
        DiscoveryResult with all discovered file paths
    """
    cameras = session_config.metadata.get("cameras", [])
    ttls = session_config.metadata.get("TTLs", [])
    bpod_config = session_config.metadata.get("bpod")

    logger.info(f"Discovering files in {session_config.session_dir}")
    logger.debug(f"  Cameras: {len(cameras)}, TTLs: {len(ttls)}, Bpod: {bpod_config is not None}")

    # Discover files
    camera_files = discover_camera_files(session_config.session_dir, cameras)
    ttl_files = discover_ttl_files(session_config.session_dir, ttls)
    bpod_files = discover_bpod_files(session_config.session_dir, bpod_config)

    return DiscoveryResult(camera_files=camera_files, bpod_files=bpod_files, ttl_files=ttl_files)
