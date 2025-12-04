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
    should_verify = context.config.verification.enabled and context.config.verification.check_sync_mismatch
    if should_verify:
        total_steps += 1
    if bpod_config:
        total_steps += 1

    if progress and task_id is not None:
        progress.update(task_id, total=total_steps)

    # Discover TTLs BEFORE cameras so we can use TTL counts for frame estimation
    _discover_ttls(context, ttls, progress, task_id)
    _discover_cameras(context, cameras, progress, task_id)
    _verify_synchronization(context, cameras, progress, task_id)
    _discover_bpod(context, bpod_config, progress, task_id)


def _discover_cameras(context: PipelineContext, cameras: list, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    logger.debug(f"Searching for {len(cameras)} camera(s)")

    for camera in cameras:
        camera_id = camera["id"]
        pattern = camera["paths"]
        order = camera.get("order", "name_asc")  # Default to name_asc if not specified
        logger.debug(f"  Scanning camera '{camera_id}' with pattern: {pattern}, order: {order}")

        video_paths = utils.discover_files(context.session_dir, pattern, sort=False)
        if not video_paths:
            logger.error(f"No video files found for camera '{camera_id}'")
            raise IngestError(
                message=f"No video files found for camera '{camera_id}'",
                context={"camera_id": camera_id, "pattern": pattern},
                hint=f"Check that files exist matching pattern: {pattern}",
            )

        # Sort files according to specified order
        video_paths = utils.sort_files(video_paths, order)
        context.camera_files[camera_id] = video_paths

        # Verification logic hierarchy:
        # 1. verification.enabled = false -> skip all verification (master switch)
        # 2. verification.enabled = true:
        #    a. check_frame_counts = true -> always count frames
        #    b. check_frame_counts = false:
        #       - Single file: skip counting
        #       - Multi-file: skip if skip_nwb_requirements=true, else count (NWB requirement)

        if not context.config.verification.enabled:
            # Master switch OFF - skip all verification including NWB requirements
            logger.debug(f"    Skipping frame count (verification.enabled=False)")
            context.camera_frame_counts[camera_id] = []
            frame_count = 0
            should_count_frames = False

        elif context.config.verification.check_frame_counts:
            # Frame counting explicitly enabled
            timeout = context.options.video_frame_timeout
            frame_counts = [utils.count_video_frames(p, timeout=timeout) for p in video_paths]
            context.camera_frame_counts[camera_id] = frame_counts
            frame_count = sum(frame_counts)
            should_count_frames = True

        elif len(video_paths) > 1 and not context.config.verification.skip_nwb_requirements:
            # Multi-file video: NWB requires frame counts even if check_frame_counts=false
            logger.debug(f"    Counting frames (required for multi-file NWB ImageSeries)")
            timeout = context.options.video_frame_timeout
            frame_counts = [utils.count_video_frames(p, timeout=timeout) for p in video_paths]
            context.camera_frame_counts[camera_id] = frame_counts
            frame_count = sum(frame_counts)
            should_count_frames = True

        elif len(video_paths) > 1 and context.config.verification.skip_nwb_requirements:
            # Multi-file: use TTL pulse count for estimation (much more accurate than FPS)
            ttl_id = camera.get("ttl_id")
            if ttl_id and ttl_id in context.ttl_files and context.ttl_files[ttl_id]:
                # Use TTL pulse count as frame count estimate
                total_pulses = sum(utils.count_ttl_pulses(p) for p in context.ttl_files[ttl_id])
                frames_per_file = total_pulses // len(video_paths)
                frame_counts = [frames_per_file] * len(video_paths)
                # Adjust last file to account for rounding
                frame_counts[-1] = total_pulses - (frames_per_file * (len(video_paths) - 1))
                frame_count = sum(frame_counts)
                logger.info(f"    Camera '{camera_id}': Using TTL-based frame estimation " f"({frame_count} frames from {total_pulses} TTL pulses)")
            else:
                # Fallback to crude FPS estimation if no TTL available
                logger.warning(f"    Camera '{camera_id}': No TTL data available for estimation. " "Using FPS-based estimation - this may cause synchronization issues!")
                fps = camera.get("fps", 30.0)
                estimated_frames_per_file = int(fps * 600)  # Assume 10-minute files
                frame_counts = [estimated_frames_per_file] * len(video_paths)
                frame_count = sum(frame_counts)
                logger.warning(f"    Estimated {frame_count} total frames (may be inaccurate)")

            context.camera_frame_counts[camera_id] = frame_counts
            should_count_frames = False

        else:
            # Single file with check_frame_counts=false: skip counting
            logger.debug(f"    Skipping frame count (verification.check_frame_counts=False)")
            context.camera_frame_counts[camera_id] = []
            frame_count = 0
            should_count_frames = False

        if should_count_frames:
            logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s), {frame_count} frames")
        else:
            logger.info(f"  Camera '{camera_id}': {len(video_paths)} file(s)")
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
            frame_counts=context.camera_frame_counts[camera_id] if context.camera_frame_counts[camera_id] else None,
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
    should_verify = context.config.verification.enabled and context.config.verification.check_sync_mismatch

    if should_verify:
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

            # Get frame count from cache if available, otherwise count now
            if camera_id in context.camera_frame_counts and context.camera_frame_counts[camera_id]:
                frame_count = sum(context.camera_frame_counts[camera_id])
            else:
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
        logger.info("Skipping synchronization verification (verification.check_sync_mismatch=False)")


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
