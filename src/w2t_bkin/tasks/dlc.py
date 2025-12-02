"""DeepLabCut pose estimation preprocessing task.

This module implements the DLC pose estimation task for the preprocessing
phase. It handles:
- Checking for existing DLC outputs in interim folder (manual or cached)
- Validating DLC model configuration
- Running DLC inference on videos (if configured and needed)
- Storing outputs in interim folder for downstream ingestion

The task is designed to be transparent to whether outputs were generated
automatically or provided manually by users.
"""

import logging
from pathlib import Path
from typing import List, Optional

from .. import utils
from ..processors.dlc import DLCInferenceOptions, DLCModelInfo, predict_output_paths, run_dlc_inference_batch, validate_dlc_model
from .base import PipelineTask, TaskConfig, TaskStatus

logger = logging.getLogger(__name__)


class DLCPoseTask(PipelineTask):
    """DeepLabCut pose estimation preprocessing task.

    This task generates pose tracking data from video files using DeepLabCut.
    It intelligently handles three scenarios:
    1. Manual outputs: User provided DLC H5 files in interim folder
    2. Cached outputs: Previously generated DLC outputs exist
    3. Generate outputs: Run DLC inference if configured and needed

    The task validates that DLC outputs exist for all cameras before
    proceeding to the ingestion phase.

    Configuration:
        Required in metadata.toml:
        - cameras: List of camera configurations with video paths

        Optional in config.toml [preprocessing.dlc]:
        - enabled: Enable DLC processing (default: true)
        - model_path: Path to DLC model config.yaml (required if enabled)
        - gpu: GPU index to use (default: auto-detect)
        - save_csv: Generate CSV output in addition to H5 (default: false)

    Example:
        >>> task = DLCPoseTask()
        >>> status, outputs = task.run(task_config)
        >>> if status == TaskStatus.COMPLETED:
        ...     print(f"Generated {len(outputs)} pose files")
    """

    def __init__(self):
        """Initialize DLC pose task."""
        super().__init__(name="dlc_pose", description="DeepLabCut pose estimation on camera videos")
        self._model_info: Optional[DLCModelInfo] = None

    def check_dependencies(self, task_config: TaskConfig) -> tuple[bool, Optional[str]]:
        """Check if DLC task dependencies are satisfied.

        Dependencies:
        1. At least one camera configured in metadata
        2. Camera video files exist in session_dir
        3. DLC model exists and is valid (if enabled)

        Args:
            task_config: Task configuration

        Returns:
            Tuple of (dependencies_met, error_message)
        """
        # Check for camera configuration
        cameras = task_config.metadata.get("cameras", [])
        if not cameras:
            return False, "No cameras configured in metadata"

        # Discover video files for each camera
        total_videos = 0
        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]
            video_paths = utils.discover_files(task_config.session_dir, pattern, sort=True)
            if not video_paths:
                logger.warning(f"No videos found for camera '{camera_id}' (pattern: {pattern})")
            else:
                total_videos += len(video_paths)
                logger.debug(f"Found {len(video_paths)} video(s) for camera '{camera_id}'")

        if total_videos == 0:
            return False, "No video files found for any camera"

        # If enabled, validate DLC model
        if task_config.enabled:
            dlc_config = task_config.config.preprocessing.dlc if hasattr(task_config.config, "preprocessing") else None
            if not dlc_config:
                return False, "DLC enabled but no preprocessing.dlc configuration found"

            model_path = dlc_config.model_path
            if not model_path:
                return False, "DLC enabled but model_path not configured"

            # Validate model
            try:
                self._model_info = validate_dlc_model(model_path)
                logger.debug(f"Validated DLC model: {self._model_info.scorer}")
            except Exception as e:
                return False, f"DLC model validation failed: {e}"

        logger.debug(f"DLC dependencies satisfied: {total_videos} video(s) found")
        return True, None

    def check_output(self, task_config: TaskConfig) -> bool:
        """Check if DLC pose outputs already exist in interim folder.

        This checks for DLC H5 files matching the expected naming convention
        for each camera video.

        Args:
            task_config: Task configuration

        Returns:
            True if all expected outputs exist, False otherwise
        """
        # Get camera configurations
        cameras = task_config.metadata.get("cameras", [])
        if not cameras:
            return False

        # Build interim DLC output directory
        interim_dlc_dir = task_config.interim_dir / "dlc"

        # Check outputs for each camera
        all_outputs_exist = True
        missing_outputs = []

        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]

            # Discover video files
            video_paths = utils.discover_files(task_config.session_dir, pattern, sort=True)

            for video_path in video_paths:
                # Predict expected H5 output path
                # Note: We need model_info to predict the exact filename
                # If model not validated yet, we can do a simple check for any H5 file
                # matching the video stem pattern

                video_stem = video_path.stem
                # Look for any H5 file starting with video_stem and containing "DLC"
                pattern_dlc = f"{video_stem}DLC_*.h5"
                existing_h5 = list(interim_dlc_dir.glob(pattern_dlc))

                if not existing_h5:
                    all_outputs_exist = False
                    missing_outputs.append(f"{camera_id}/{video_path.name}")
                    logger.debug(f"Missing DLC output for {camera_id}/{video_path.name}")
                else:
                    logger.debug(f"Found existing DLC output: {existing_h5[0].name}")

        if missing_outputs:
            logger.debug(f"Missing DLC outputs for {len(missing_outputs)} video(s)")
        else:
            logger.debug("All DLC outputs exist in interim folder")

        return all_outputs_exist

    def execute(self, task_config: TaskConfig) -> List[Path]:
        """Execute DLC inference to generate pose outputs.

        Runs DLC inference on all camera videos and stores outputs in
        interim/dlc folder.

        Args:
            task_config: Task configuration

        Returns:
            List of generated H5 output file paths

        Raises:
            Exception: If DLC inference fails critically
        """
        # Ensure model is validated
        if self._model_info is None:
            # Re-validate (should not happen if check_dependencies was called)
            dlc_config = task_config.config.preprocessing.dlc
            self._model_info = validate_dlc_model(dlc_config.model_path)

        # Build interim DLC output directory
        interim_dlc_dir = task_config.interim_dir / "dlc"
        interim_dlc_dir.mkdir(parents=True, exist_ok=True)

        # Get DLC inference options from config
        dlc_config = task_config.config.preprocessing.dlc
        inference_options = DLCInferenceOptions(
            gputouse=dlc_config.gpu if hasattr(dlc_config, "gpu") else None,
            save_as_csv=dlc_config.save_csv if hasattr(dlc_config, "save_csv") else False,
            allow_growth=True,  # Default for better GPU memory management
        )

        # Collect all video paths from all cameras
        cameras = task_config.metadata.get("cameras", [])
        all_video_paths = []
        camera_video_map = {}  # Track which videos belong to which camera

        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]
            video_paths = utils.discover_files(task_config.session_dir, pattern, sort=True)
            all_video_paths.extend(video_paths)
            for vp in video_paths:
                camera_video_map[vp] = camera_id

        logger.info(f"Running DLC inference on {len(all_video_paths)} video(s)")

        # Run batch inference
        results = run_dlc_inference_batch(
            video_paths=all_video_paths,
            model_config_path=self._model_info.config_path,
            output_dir=interim_dlc_dir,
            options=inference_options,
        )

        # Collect output paths and report failures
        output_paths = []
        failed_videos = []

        for result in results:
            if result.success and result.h5_output_path:
                output_paths.append(result.h5_output_path)
                camera_id = camera_video_map.get(result.video_path, "unknown")
                logger.debug(f"  ✓ {camera_id}/{result.video_path.name}: " f"{result.frame_count} frames in {result.inference_time_s:.1f}s")
            else:
                failed_videos.append((result.video_path.name, result.error_message))
                camera_id = camera_video_map.get(result.video_path, "unknown")
                logger.warning(f"  ✗ {camera_id}/{result.video_path.name}: {result.error_message}")

        # Log summary
        logger.info(f"DLC inference completed: {len(output_paths)}/{len(all_video_paths)} succeeded")

        if failed_videos:
            logger.warning(f"Failed videos: {len(failed_videos)}")
            for video_name, error in failed_videos[:5]:  # Show first 5
                logger.warning(f"  - {video_name}: {error}")
            if len(failed_videos) > 5:
                logger.warning(f"  ... and {len(failed_videos) - 5} more")

        # If all videos failed, raise exception
        if not output_paths:
            raise Exception("DLC inference failed for all videos")

        return output_paths

    def _find_output_files(self, task_config: TaskConfig) -> List[Path]:
        """Find existing DLC output files in interim folder.

        Args:
            task_config: Task configuration

        Returns:
            List of H5 file paths found
        """
        interim_dlc_dir = task_config.interim_dir / "dlc"
        if not interim_dlc_dir.exists():
            return []

        # Find all DLC H5 files
        h5_files = list(interim_dlc_dir.glob("*DLC_*.h5"))
        return sorted(h5_files)
