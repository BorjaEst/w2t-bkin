"""Pure functions for discovering files in session directories."""

import logging
from pathlib import Path
from typing import Dict, List

from w2t_bkin import utils
from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.metadata import BpodMeta, CameraMeta, TTLsMeta
from w2t_bkin.models import DiscoveryResult, SessionInfo

logger = logging.getLogger(__name__)


def discover_camera_files(session_dir: Path, metas: List[CameraMeta], sort_order: str = "name_asc") -> Dict[str, List[Path]]:
    camera_files = {}

    for camera in metas:
        camera_id = camera.id
        pattern = camera.paths
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


def discover_ttl_files(session_dir: Path, metas: List[Dict]) -> Dict[str, List[Path]]:
    ttl_files = {}

    for ttl in metas:
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


def discover_bpod_files(session_dir: Path, meta: Dict) -> Dict[str, List[Path]]:
    """Discover Bpod data files.

    Args:
        session_dir: Path to session directory
        meta: Bpod configuration dictionary

    Returns:
        Dictionary with 'bpod' key mapping to list of file paths
    """
    if not meta:
        logger.debug("No Bpod configuration - skipping discovery")
        return {"bpod": []}

    # Support both legacy and current metadata keys.
    # - metadata template uses: path
    # - some code paths use: paths
    # - config-driven fallback uses: pattern
    pattern = meta.get("path") or meta.get("paths") or meta.get("pattern") or "Bpod/*.mat"
    order = meta.get("order", "name_asc")

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


def discover_pose_files(session_dir: Path, meta: Dict) -> Dict[str, List[Path]]:
    pass  # TODO implement pose file discovery
