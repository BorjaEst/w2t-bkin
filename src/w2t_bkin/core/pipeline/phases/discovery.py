"""Phase 1: Discovery & Verification."""

import logging
from typing import Optional

from rich.progress import Progress, TaskID

from ... import session, validate
from .... import utils
from ....exceptions import IngestError, MismatchExceedsToleranceError
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_1(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Discover and verify files."""
    logger.info("Discovering files and verifying synchronization...")

    # Discover cameras
    cameras = context.metadata.get("cameras", [])
    ttls = context.metadata.get("TTLs", [])
    bpod_config = context.metadata.get("bpod")

    # Calculate total steps
    total_steps = len(cameras) + len(ttls)
    if not context.options.skip_verification:
        total_steps += 1
    if bpod_config:
        total_steps += 1

    if progress and task_id is not None:
        progress.update(task_id, total=total_steps)

    _discover_cameras(context, cameras, progress, task_id)
    _discover_ttls(context, ttls, progress, task_id)
    _verify_synchronization(context, cameras, progress, task_id)
    _discover_bpod(context, bpod_config, progress, task_id)


def _discover_cameras(context: PipelineContext, cameras: list, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    logger.debug(f"Searching for {len(cameras)} camera(s)")

    for camera in cameras:
        camera_id = camera["id"]
        pattern = camera["paths"]
        logger.debug(f"  Scanning camera '{camera_id}' with pattern: {pattern}")

        video_paths = utils.discover_files(context.session_dir, pattern, sort=True)
        if not video_paths:
            logger.error(f"No video files found for camera '{camera_id}'")
            raise IngestError(
                message=f"No video files found for camera '{camera_id}'",
                context={"camera_id": camera_id, "pattern": pattern},
                hint=f"Check that files exist matching pattern: {pattern}",
            )

        context.camera_files[camera_id] = video_paths
        timeout = context.options.video_frame_timeout
        frame_count = sum(utils.count_video_frames(p, timeout=timeout) for p in video_paths)

        logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s), {frame_count} frames")
        logger.debug(f"    Files: {[p.name for p in video_paths]}")

        # Add video acquisition to NWBFile
        device = context.nwbfile.devices.get(camera_id)
        if device:
            logger.debug(f"    Linked to device: {device.name}")
        else:
            logger.warning(f"    Device '{camera_id}' not found in NWBFile devices")

        # Determine frame rate with warning if missing
        fps = camera.get("fps")
        if fps is None:
            logger.warning(f"    Camera '{camera_id}': 'fps' not configured in metadata, defaulting to 30.0 Hz")
            fps = 30.0
        else:
            logger.debug(f"    Camera '{camera_id}': configured fps={fps} Hz")

        session.add_video_acquisition(
            context.nwbfile,
            camera_id=camera_id,
            video_files=[str(p) for p in video_paths],
            frame_rate=fps,
            device=device,
        )

        if progress and task_id is not None:
            progress.advance(task_id)


def _discover_ttls(context: PipelineContext, ttls: list, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    logger.debug(f"Searching for {len(ttls)} TTL source(s)")

    for ttl in ttls:
        ttl_id = ttl["id"]
        pattern = ttl["paths"]
        logger.debug(f"  Scanning TTL '{ttl_id}' with pattern: {pattern}")

        ttl_paths = utils.discover_files(context.session_dir, pattern, sort=True)
        if ttl_paths:
            context.ttl_files[ttl_id] = ttl_paths
            pulse_count = sum(utils.count_ttl_pulses(p) for p in ttl_paths)
            logger.info(f"  TTL '{ttl_id}': {len(ttl_paths)} file(s), {pulse_count} pulses")
            logger.debug(f"    Files: {[p.name for p in ttl_paths]}")
        else:
            logger.warning(f"  TTL '{ttl_id}': No files found (pattern: {pattern})")
            context.ttl_files[ttl_id] = []

        if progress and task_id is not None:
            progress.advance(task_id)


def _verify_synchronization(context: PipelineContext, cameras: list, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if not context.options.skip_verification:
        logger.debug("Verifying synchronization between cameras and TTLs...")
        for camera in cameras:
            camera_id = camera["id"]
            ttl_id = camera.get("ttl_id")

            if not ttl_id:
                logger.debug(f"  Skipping verification for '{camera_id}' (no ttl_id configured)")
                continue

            if ttl_id not in context.ttl_files:
                logger.warning(f"  Skipping verification for '{camera_id}': TTL source '{ttl_id}' not found")
                continue

            timeout = context.options.video_frame_timeout
            frame_count = sum(utils.count_video_frames(p, timeout=timeout) for p in context.camera_files[camera_id])
            pulse_count = sum(utils.count_ttl_pulses(p) for p in context.ttl_files[ttl_id])

            logger.debug(f"  Verifying '{camera_id}' ({frame_count} frames) vs '{ttl_id}' ({pulse_count} pulses)")

            try:
                validate.verify_synchronization(
                    camera_id=camera_id,
                    ttl_id=ttl_id,
                    frame_count=frame_count,
                    pulse_count=pulse_count,
                    tolerance=context.config.verification.mismatch_tolerance_frames,
                )
            except MismatchExceedsToleranceError as e:
                if context.config.verification.warn_on_mismatch:
                    logger.warning(f"  Synchronization mismatch (warning only): {e}")
                else:
                    raise

        if progress and task_id is not None:
            progress.advance(task_id)
    else:
        logger.info("Skipping synchronization verification (requested by options)")


def _discover_bpod(context: PipelineContext, bpod_config: dict, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if bpod_config:
        pattern = bpod_config["path"]
        logger.debug(f"Scanning Bpod with pattern: {pattern}")
        bpod_paths = utils.discover_files(context.session_dir, pattern, sort=True)
        if bpod_paths:
            context.bpod_files["bpod"] = bpod_paths
            logger.info(f"  Bpod: {len(bpod_paths)} file(s)")
            logger.debug(f"    Files: {[p.name for p in bpod_paths]}")
        else:
            logger.warning(f"  Bpod: No files found (pattern: {pattern})")

        if progress and task_id is not None:
            progress.advance(task_id)
