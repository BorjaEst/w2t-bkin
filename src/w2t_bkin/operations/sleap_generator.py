"""Pure functions for generating SLEAP pose estimation artifacts."""

from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List

from w2t_bkin import utils
from w2t_bkin.models import SessionConfig, SLEAPArtifact

logger = logging.getLogger(__name__)


def discover_sleap_poses(video_paths: List[Path], sleap_dir: Path, camera_id: str) -> List[SLEAPArtifact]:
    """Discover existing SLEAP pose estimation outputs.

    Pure function that looks for SLEAP H5 files matching video file names.
    Does not execute SLEAP inference.

    Args:
        video_paths: List of video file paths to find SLEAP outputs for
        sleap_dir: Directory containing SLEAP H5 output files
        camera_id: Camera identifier

    Returns:
        List of SLEAPArtifact objects for found H5 files
    """
    logger.info(f"Discovering SLEAP outputs for {len(video_paths)} video(s) in {sleap_dir}")

    if not sleap_dir.exists():
        logger.debug(f"SLEAP output directory does not exist: {sleap_dir}")
        return []

    artifacts = []

    for video_path in video_paths:
        video_stem = video_path.stem

        # Look for H5 files matching video stem
        # SLEAP outputs: {video_name}.h5, {video_name}.predictions.h5, {video_name}.sleap.h5
        pattern = f"*{video_stem}*.h5"
        matching_h5 = list(sleap_dir.glob(pattern))

        if matching_h5:
            # Use first match (should only be one per video)
            h5_path = matching_h5[0]

            artifacts.append(
                SLEAPArtifact(
                    path=h5_path,
                    camera_id=camera_id,
                    model_name="unknown",  # SLEAP doesn't embed model name in output
                    generated_at=datetime.fromtimestamp(h5_path.stat().st_mtime),
                    cached=True,
                )
            )

            logger.debug(f"Found SLEAP output: {h5_path.name}")
        else:
            logger.debug(f"No SLEAP output found for {video_path.name}")

    logger.info(f"Discovered {len(artifacts)} SLEAP artifact(s) for camera '{camera_id}'")
    return artifacts


def generate_sleap_poses(video_paths: List[Path], model_path: Path, output_dir: Path, camera_id: str, force_rerun: bool = False) -> List[SLEAPArtifact]:
    """Generate SLEAP pose estimation for video files.

    Pure function stub for SLEAP inference. Currently not implemented.
    Use discover_sleap_poses() to find manually-generated outputs.

    Args:
        video_paths: List of video file paths to process
        model_path: Path to SLEAP model file
        output_dir: Directory to write H5 output files
        camera_id: Camera identifier
        force_rerun: If True, regenerate even if outputs exist

    Returns:
        List of SLEAPArtifact objects

    Raises:
        NotImplementedError: SLEAP inference not yet implemented
    """
    raise NotImplementedError("SLEAP inference execution is not yet implemented. " f"Please manually generate SLEAP outputs and place them in: {output_dir}")


def discover_sleap_poses_for_session(session_config: SessionConfig) -> Dict[str, List[SLEAPArtifact]]:
    """Discover SLEAP pose estimation outputs for all cameras in a session.

    Convenience function that processes all cameras configured for SLEAP.

    Args:
        session_config: Session configuration

    Returns:
        Dictionary mapping camera_id to list of SLEAPArtifact objects
    """
    sleap_config = session_config.config.preprocessing.sleap

    if not sleap_config.enabled:
        logger.info("SLEAP processing disabled")
        return {}

    logger.info(f"Discovering SLEAP outputs for session {session_config.session_id}")

    # Get camera configurations
    cameras = session_config.metadata.get("cameras", [])

    if not cameras:
        logger.warning("No cameras configured in metadata")
        return {}

    # Process each camera
    all_artifacts = {}

    for camera in cameras:
        camera_id = camera["id"]
        pattern = camera["paths"]

        # Discover video files
        video_paths = utils.discover_files(session_config.session_dir, pattern, sort=True)

        if not video_paths:
            logger.warning(f"No videos found for camera '{camera_id}'")
            all_artifacts[camera_id] = []
            continue

        # Camera-specific SLEAP output directory
        camera_sleap_dir = session_config.interim_dir / "sleap-pose" / camera_id

        # Discover SLEAP poses
        artifacts = discover_sleap_poses(video_paths=video_paths, sleap_dir=camera_sleap_dir, camera_id=camera_id)

        all_artifacts[camera_id] = artifacts

        logger.info(f"Camera '{camera_id}': {len(artifacts)} artifact(s) discovered " f"({len(video_paths) - len(artifacts)} missing)")

    return all_artifacts
