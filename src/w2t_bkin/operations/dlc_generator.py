"""Pure functions for generating DLC pose estimation artifacts."""

from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List

from w2t_bkin import utils
from w2t_bkin.models import DLCArtifact, SessionInfo
from w2t_bkin.processors.dlc import DLCInferenceOptions, predict_output_paths, run_dlc_inference_batch, validate_dlc_model

logger = logging.getLogger(__name__)


def discover_dlc_poses(video_paths: List[Path], dlc_dir: Path, camera_id: str) -> List[DLCArtifact]:
    """Discover existing DLC pose estimation outputs.

    Pure function that looks for DLC H5 files matching video file names.
    Does not execute DLC inference.

    Args:
        video_paths: List of video file paths to find DLC outputs for
        dlc_dir: Directory containing DLC H5 output files
        camera_id: Camera identifier

    Returns:
        List of DLCArtifact objects for found H5 files
    """
    logger.info(f"Discovering DLC outputs for {len(video_paths)} video(s) in {dlc_dir}")

    if not dlc_dir.exists():
        logger.debug(f"DLC output directory does not exist: {dlc_dir}")
        return []

    artifacts = []

    for video_path in video_paths:
        video_stem = video_path.stem

        # Look for H5 files matching video stem
        # DLC outputs: {video_stem}DLC*.h5
        pattern = f"{video_stem}DLC*.h5"
        matching_h5 = list(dlc_dir.glob(pattern))

        if matching_h5:
            # Use first match (should only be one per video)
            h5_path = matching_h5[0]

            # Extract model name from filename if possible
            # Format: {video_stem}DLC_{model_name}_{...}.h5
            model_name = "unknown"
            if "DLC_" in h5_path.name:
                parts = h5_path.name.split("DLC_")[1].split("_")
                if parts:
                    model_name = parts[0]

            artifacts.append(
                DLCArtifact(
                    path=h5_path,
                    camera_id=camera_id,
                    model_name=model_name,
                    generated_at=datetime.fromtimestamp(h5_path.stat().st_mtime),
                    cached=True,
                )
            )

            logger.debug(f"Found DLC output: {h5_path.name}")
        else:
            logger.debug(f"No DLC output found for {video_path.name}")

    logger.info(f"Discovered {len(artifacts)} DLC artifact(s) for camera '{camera_id}'")
    return artifacts


def generate_dlc_poses(
    video_paths: List[Path], model_path: Path, output_dir: Path, camera_id: str, force_rerun: bool = False, gpu_index: int | None = None, save_csv: bool = False
) -> List[DLCArtifact]:
    """Generate DLC pose estimation for video files.

    Pure function that runs DLC inference on videos. Checks for cached
    outputs and only regenerates if needed.

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
    logger.info(f"Processing {len(video_paths)} video(s) for camera '{camera_id}'")

    # Validate DLC model
    model_info = validate_dlc_model(model_path)
    logger.debug(f"DLC model validated: {model_info.scorer}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Predict expected output paths
    expected_outputs = predict_output_paths(video_paths=video_paths, model_info=model_info, output_dir=output_dir)

    # Check which outputs already exist (cached)
    artifacts = []
    videos_to_process = []

    for video_path, expected_h5 in zip(video_paths, expected_outputs):
        if expected_h5.exists() and not force_rerun:
            # Cached output
            logger.debug(f"Using cached DLC output: {expected_h5.name}")
            artifacts.append(
                DLCArtifact(path=expected_h5, camera_id=camera_id, model_name=model_info.scorer, generated_at=datetime.fromtimestamp(expected_h5.stat().st_mtime), cached=True)
            )
        else:
            # Need to generate
            videos_to_process.append(video_path)

    # Run DLC inference on videos that need processing
    if videos_to_process:
        logger.info(f"Running DLC inference on {len(videos_to_process)} video(s)")

        # Configure DLC inference options
        options = DLCInferenceOptions(gputouse=gpu_index, save_as_csv=save_csv)

        # Run batch inference
        generated_paths = run_dlc_inference_batch(video_paths=videos_to_process, model_path=model_path, output_dir=output_dir, options=options)

        # Create artifacts for generated outputs
        for h5_path in generated_paths:
            artifacts.append(DLCArtifact(path=h5_path, camera_id=camera_id, model_name=model_info.scorer, generated_at=datetime.now(), cached=False))

        logger.info(f"Generated {len(generated_paths)} DLC pose file(s)")
    else:
        logger.info(f"All DLC outputs cached for camera '{camera_id}'")

    return artifacts


def generate_dlc_poses_for_session(session_info: SessionInfo, force_rerun: bool = False) -> Dict[str, List[DLCArtifact]]:
    """Generate DLC pose estimation for all cameras in a session.

    Iterates over cameras defined in metadata["pose"]["cameras"] and generates
    DLC poses using per-camera model configurations from metadata["pose"]["models"].

    Args:
        session_info: Session configuration with metadata containing pose.cameras
                     and pose.models sections
        force_rerun: If True, regenerate even if outputs exist

    Returns:
        Dictionary mapping camera_id to list of DLCArtifact objects

    Raises:
        ValueError: If DLC not enabled, pose configuration missing, or model references invalid
    """
    dlc_config = session_info.config.preprocessing.dlc

    if not dlc_config.enabled:
        logger.info("DLC processing disabled")
        return {}

    # Validate metadata structure
    pose_meta = session_info.metadata.get("pose")
    if not pose_meta:
        raise ValueError("DLC enabled but metadata['pose'] section is missing")

    cameras_meta = pose_meta.get("cameras", {})
    models_meta = pose_meta.get("models", {})

    if not cameras_meta:
        logger.warning("No cameras configured in metadata['pose']['cameras']")
        return {}

    if not models_meta:
        raise ValueError("DLC enabled but metadata['pose']['models'] is empty. Define at least one DLC model.")

    logger.info(f"Starting DLC processing for session {session_info.session_id}")
    logger.debug(f"Processing {len(cameras_meta)} camera(s) with {len(models_meta)} model(s) available")

    # Get video path patterns from base cameras metadata
    base_cameras = session_info.metadata.get("cameras", [])
    camera_patterns = {cam["id"]: cam["paths"] for cam in base_cameras}

    # Process each camera configured for DLC
    all_artifacts = {}

    for camera_id, camera_config in cameras_meta.items():
        # Skip cameras not using DLC
        if camera_config.get("source") != "dlc":
            logger.debug(f"Skipping camera '{camera_id}': source is '{camera_config.get('source')}', not 'dlc'")
            continue

        # Resolve model path from model_id reference
        model_id = camera_config.get("model_id")
        if not model_id:
            raise ValueError(f"Camera '{camera_id}' has source='dlc' but no 'model_id' specified")

        if model_id not in models_meta:
            raise ValueError(f"Camera '{camera_id}' references model_id='{model_id}' but metadata['pose']['models']['{model_id}'] does not exist")

        model_config = models_meta[model_id]
        model_path = Path(model_config.get("path", ""))

        if not model_path or not model_path.exists():
            raise ValueError(f"Model '{model_id}' has invalid or missing path: {model_path}")

        logger.debug(f"Camera '{camera_id}' → model '{model_id}': {model_path}")

        # Get video path pattern for this camera
        if camera_id not in camera_patterns:
            logger.warning(f"Camera '{camera_id}' not found in metadata['cameras'], skipping")
            all_artifacts[camera_id] = []
            continue

        pattern = camera_patterns[camera_id]

        # Discover video files
        video_paths = utils.discover_files(session_info.session_dir, pattern, sort=True)

        if not video_paths:
            logger.warning(f"No videos found for camera '{camera_id}' with pattern '{pattern}'")
            all_artifacts[camera_id] = []
            continue

        # Create camera-specific output directory
        camera_output_dir = session_info.interim_dir / "dlc-pose" / camera_id

        # Generate DLC poses with per-camera model
        artifacts = generate_dlc_poses(
            video_paths=video_paths,
            model_path=model_path,
            output_dir=camera_output_dir,
            camera_id=camera_id,
            force_rerun=force_rerun,
            gpu_index=dlc_config.gpu,
            save_csv=dlc_config.save_csv,
        )

        all_artifacts[camera_id] = artifacts

        logger.info(
            f"Camera '{camera_id}': {len(artifacts)} artifact(s) " f"({sum(1 for a in artifacts if not a.cached)} generated, " f"{sum(1 for a in artifacts if a.cached)} cached)"
        )

    return all_artifacts
