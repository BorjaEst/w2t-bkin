"""SLEAP pose estimation preprocessing task.

This module implements the SLEAP pose estimation task for the preprocessing
phase. It handles:
- Checking for existing SLEAP outputs in interim folder (manual or cached)
- Validating SLEAP model configuration
- Storing outputs in interim folder for downstream ingestion

The task is designed to be transparent to whether outputs were generated
automatically or provided manually by users.
"""

import logging
from pathlib import Path
from typing import List, Optional

from .. import utils
from .base import PipelineTask, TaskConfig, TaskStatus

logger = logging.getLogger(__name__)


class SLEAPPoseTask(PipelineTask):
    """SLEAP pose estimation preprocessing task.

    This task manages SLEAP pose tracking data.
    Currently supports discovery of existing outputs. Inference execution
    is not yet implemented.

    Configuration:
        Required in metadata.toml:
        - cameras: List of camera configurations with video paths

        Optional in config.toml [preprocessing.sleap]:
        - enabled: Enable SLEAP processing (default: false)
        - model_path: Path to SLEAP model (required if enabled)
    """

    def __init__(self):
        """Initialize SLEAP pose task."""
        super().__init__(name="sleap_pose", description="SLEAP pose estimation on camera videos")

    def check_dependencies(self, task_config: TaskConfig) -> tuple[bool, Optional[str]]:
        """Check if SLEAP task dependencies are satisfied.

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
            if video_paths:
                total_videos += len(video_paths)

        if total_videos == 0:
            return False, "No video files found for any camera"

        # If enabled, validate SLEAP model config
        if task_config.enabled:
            sleap_config = task_config.config.preprocessing.sleap if hasattr(task_config.config, "preprocessing") else None
            if not sleap_config:
                return False, "SLEAP enabled but no preprocessing.sleap configuration found"

            # Model path check (optional if we only support manual outputs for now)
            if sleap_config.model_path and not sleap_config.model_path.exists():
                logger.warning(f"SLEAP model path not found: {sleap_config.model_path}")

        return True, None

    def check_output(self, task_config: TaskConfig) -> bool:
        """Check if SLEAP pose outputs already exist in interim folder.

        This checks for SLEAP H5 files in the camera-specific subfolder.
        Expected pattern: {video_stem}.h5 or {video_stem}.sleap.h5

        Args:
            task_config: Task configuration

        Returns:
            True if all expected outputs exist, False otherwise
        """
        # Get camera configurations
        cameras = task_config.metadata.get("cameras", [])
        if not cameras:
            return False

        # Check outputs for each camera
        all_outputs_exist = True
        missing_outputs = []

        for camera in cameras:
            camera_id = camera["id"]
            pattern = camera["paths"]

            # Build interim SLEAP output directory for this camera
            # Structure: interim/session/sleap-pose/{camera_id}/
            camera_sleap_dir = task_config.interim_dir / "sleap-pose" / camera_id

            # Discover video files
            video_paths = utils.discover_files(task_config.session_dir, pattern, sort=True)

            for video_path in video_paths:
                video_stem = video_path.stem

                # Look for H5 file matching video stem
                # SLEAP often outputs as {video_name}.h5 or {video_name}.predictions.h5
                # We'll look for *{video_stem}*.h5
                pattern_sleap = f"*{video_stem}*.h5"
                existing_h5 = list(camera_sleap_dir.glob(pattern_sleap))

                if not existing_h5:
                    all_outputs_exist = False
                    missing_outputs.append(f"{camera_id}/{video_path.name}")
                    logger.debug(f"Missing SLEAP output for {camera_id}/{video_path.name} in {camera_sleap_dir}")
                else:
                    logger.debug(f"Found existing SLEAP output: {existing_h5[0].name}")

        if missing_outputs:
            logger.debug(f"Missing SLEAP outputs for {len(missing_outputs)} video(s)")
        else:
            logger.debug("All SLEAP outputs exist in interim folder")

        return all_outputs_exist

    def execute(self, task_config: TaskConfig) -> List[Path]:
        """Execute SLEAP inference.

        Currently not implemented. Raises NotImplementedError.
        """
        raise NotImplementedError("SLEAP inference execution is not yet implemented. Please provide manual outputs in interim/sleap-pose/")

    def _find_output_files(self, task_config: TaskConfig) -> List[Path]:
        """Find existing SLEAP output files in interim folder.

        Args:
            task_config: Task configuration

        Returns:
            List of H5 file paths found
        """
        interim_sleap_dir = task_config.interim_dir / "sleap-pose"
        if not interim_sleap_dir.exists():
            return []

        # Find all SLEAP H5 files in all camera subdirectories
        h5_files = list(interim_sleap_dir.glob("*/*.h5"))
        return sorted(h5_files)
