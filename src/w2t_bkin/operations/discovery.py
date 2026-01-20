"""Pure functions for discovering files in session directories."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from w2t_bkin import utils
from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.ingest.bpod import discover_bpod_files_from_pattern
from w2t_bkin.metadata import BpodMeta, CameraMeta, PoseMeta, TTLsMeta
from w2t_bkin.models import DiscoveryResult, SessionInfo

logger = logging.getLogger(__name__)


def discover_camera_files(session_dir: Path, cameras: List[CameraMeta]) -> Dict[str, List[Path]]:
    """Discover camera video files from metadata configuration.

    Args:
        session_dir: Session raw directory
        cameras: List of camera metadata from [[cameras]] in metadata.toml

    Returns:
        Dict mapping camera_id to sorted list of video file paths

    Raises:
        IngestError: If required camera files are not found
    """
    camera_files = {}

    for camera in cameras:
        camera_id = camera.id
        pattern = camera.paths
        order = camera.order or "name_asc"
        is_optional = camera.optional

        logger.debug(f"Discovering camera '{camera_id}' with pattern: {pattern}")

        # Discover files
        files = utils.discover_files(session_dir, pattern, sort=False)

        # Check if required camera has no files
        if not files and not is_optional:
            raise IngestError(
                f"No video files found for required camera '{camera_id}'",
                context={"camera_id": camera_id, "pattern": pattern, "search_path": str(session_dir)},
                hint=f"Check that video files exist matching pattern: {pattern}",
            )

        # Sort files
        if files:
            files = utils.sort_files(files, order)
            logger.info(f"Discovered {len(files)} video file(s) for camera '{camera_id}'")
        else:
            logger.warning(f"No video files found for optional camera '{camera_id}' (pattern: {pattern})")

        camera_files[camera_id] = files

    return camera_files


def discover_ttl_files(session_dir: Path, ttls: List[TTLsMeta]) -> Dict[str, List[Path]]:
    """Discover TTL signal files from metadata configuration.

    Args:
        session_dir: Session raw directory
        ttls: List of TTL metadata from [[TTLs]] in metadata.toml

    Returns:
        Dict mapping ttl_id to sorted list of TTL file paths

    Note:
        Missing TTL files generate warnings but do not raise errors, since
        TTL necessity depends on sync strategy and ingestion config.
    """
    ttl_files = {}

    for ttl in ttls:
        ttl_id = ttl.id
        pattern = ttl.paths
        order = ttl.order or "name_asc"

        logger.debug(f"Discovering TTL channel '{ttl_id}' with pattern: {pattern}")

        # Discover files
        files = utils.discover_files(session_dir, pattern, sort=False)

        # Sort files
        if files:
            files = utils.sort_files(files, order)
            logger.info(f"Discovered {len(files)} TTL file(s) for channel '{ttl_id}'")
        else:
            logger.warning(f"No TTL files found for channel '{ttl_id}' (pattern: {pattern})")

        ttl_files[ttl_id] = files

    return ttl_files


def discover_bpod_files(session_dir: Path, bpod: Optional[BpodMeta]) -> Dict[str, List[Path]]:
    """Discover Bpod behavioral data files from metadata configuration.

    Args:
        session_dir: Session raw directory
        bpod: Bpod metadata from [bpod] in metadata.toml (None if not configured)

    Returns:
        Dict with single key "bpod" mapping to sorted list of .mat file paths,
        or empty dict if bpod is None

    Raises:
        IngestError: If bpod is configured but no files are found
    """
    if bpod is None:
        return {}

    pattern = bpod.path
    order = bpod.order

    logger.debug(f"Discovering Bpod files with pattern: {pattern}")

    # Reuse existing bpod discovery logic for consistent ordering
    try:
        files = discover_bpod_files_from_pattern(session_dir=session_dir, pattern=pattern, order=order)
        logger.info(f"Discovered {len(files)} Bpod .mat file(s)")
        return {"bpod": files}
    except Exception as e:
        raise IngestError(
            f"Failed to discover Bpod files: {e}",
            context={"pattern": pattern, "search_path": str(session_dir)},
            hint="Check that Bpod .mat files exist and pattern is correct",
        )


def discover_pose_files(session_dir: Path, pose: PoseMeta) -> Dict[str, List[Path]]:
    """Discover pose estimation files (currently stubbed).

    Pose H5 artifact discovery is handled in Phase 2 (artifacts) based on
    interim directory structure. This function is reserved for future use
    if raw pose data input patterns are added to metadata schema.

    Args:
        session_dir: Session raw directory
        pose: Pose metadata from [pose] in metadata.toml

    Returns:
        Empty dict (pose discovery happens in artifacts phase)
    """
    logger.debug("Pose file discovery skipped (handled in artifacts phase)")
    return {}


def discover_pose_models(models_root: Path, models: Dict[str, "PoseModelMeta"]) -> Dict[str, Path]:
    """Discover pose estimation model files.

    Args:
        models_root: Root directory for pose models (from W2T_MODELS_ROOT)
        models: Dict of model metadata from [pose.models.*] in metadata.toml

    Returns:
        Dict mapping model_id to resolved config file path (only includes models that exist)

    Note:
        Missing models generate warnings but do not raise errors, since
        model necessity depends on artifacts.mode config.
    """
    model_files = {}

    for model_id, model_meta in models.items():
        model_path_str = model_meta.path
        model_path = models_root / model_path_str

        logger.debug(f"Checking for model '{model_id}' at: {model_path}")

        if model_path.exists():
            logger.info(f"Found model '{model_id}': {model_path}")
            model_files[model_id] = model_path
        else:
            logger.warning(f"Model '{model_id}' not found at: {model_path} (may be needed for artifacts.mode='generate')")

    return model_files
