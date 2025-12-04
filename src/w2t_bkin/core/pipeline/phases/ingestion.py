"""Phase 3: Ingestion."""

import logging
from typing import Optional

from rich.progress import Progress, TaskID

from .... import sync, utils
from ....ingest import bpod, pose, ttl
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_3(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Ingest Bpod, Pose, and TTL data."""
    logger.info("Processing Bpod, Pose, and TTL data...")

    total_steps = 4
    if progress and task_id is not None:
        progress.update(task_id, total=total_steps)

    _ingest_bpod(context, progress, task_id)
    _ingest_pose(context, progress, task_id)
    _ingest_ttl(context, progress, task_id)
    _compute_trial_offsets(context, progress, task_id)


def _ingest_bpod(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if not context.options.skip_bpod and context.bpod_files:
        bpod_config = context.metadata.get("bpod", {})
        logger.debug(f"Parsing Bpod data (order={bpod_config.get('order')}, continuous={bpod_config.get('continuous_time')})")

        context.bpod_data = bpod.parse_bpod(
            session_dir=context.session_dir,
            pattern=bpod_config["path"],
            order=bpod_config.get("order", "time_asc"),
            continuous_time=bpod_config.get("continuous_time", False),
        )

        session_data = utils.convert_matlab_struct(context.bpod_data.get("SessionData", {}))
        raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
        trials = raw_events.get("Trial", [])
        n_trials = len(trials) if trials is not None else 0
        logger.info(f"  Bpod: {n_trials} trials")
        logger.debug(f"    SessionData keys: {list(session_data.keys())}")
    elif context.options.skip_bpod:
        logger.info("Skipping Bpod processing (requested by options)")

    if progress and task_id is not None:
        progress.advance(task_id)


def _ingest_pose(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    # Process Pose (DLC)
    if not context.options.skip_pose and context.config.preprocessing.dlc.enabled:
        logger.debug("Ingesting DLC pose estimation data...")
        interim_dlc_dir = context.config.paths.intermediate_root / context.subject_id / context.session_id / "dlc"

        for camera_id, video_paths in context.camera_files.items():
            camera_pose_data = []
            for video_path in video_paths:
                video_stem = video_path.stem
                # Pattern from DLCPoseTask: f"{video_stem}DLC_*.h5"
                dlc_files = list(interim_dlc_dir.glob(f"{video_stem}DLC_*.h5"))

                if dlc_files:
                    dlc_path = dlc_files[0]  # Take the first match
                    logger.debug(f"  Found DLC output for '{camera_id}': {dlc_path.name}")

                    try:
                        frames, metadata = pose.import_dlc_pose(dlc_path)
                        camera_pose_data.append({"video_path": video_path, "frames": frames, "metadata": metadata})
                    except Exception as e:
                        logger.warning(f"  Failed to import DLC pose for {video_path.name}: {e}")
                else:
                    logger.debug(f"  No DLC output found for '{camera_id}' video: {video_path.name}")

            if camera_pose_data:
                context.pose_data[camera_id] = camera_pose_data
                logger.info(f"  Pose '{camera_id}': Loaded data for {len(camera_pose_data)} video(s)")

    # Process Pose (SLEAP)
    if not context.options.skip_pose and context.config.preprocessing.sleap.enabled:
        logger.debug("Ingesting SLEAP pose estimation data...")
        interim_sleap_dir = context.config.paths.intermediate_root / context.subject_id / context.session_id / "sleap"

        for camera_id, video_paths in context.camera_files.items():
            camera_pose_data = []
            for video_path in video_paths:
                video_stem = video_path.stem
                # Pattern from SLEAPPoseTask: f"{video_stem}.sleap.h5"
                sleap_files = list(interim_sleap_dir.glob(f"{video_stem}.sleap.h5"))

                if sleap_files:
                    sleap_path = sleap_files[0]
                    logger.debug(f"  Found SLEAP output for '{camera_id}': {sleap_path.name}")

                    try:
                        frames, metadata = pose.import_sleap_pose(sleap_path)
                        camera_pose_data.append({"video_path": video_path, "frames": frames, "metadata": metadata})
                    except Exception as e:
                        logger.warning(f"  Failed to import SLEAP pose for {video_path.name}: {e}")
                else:
                    logger.debug(f"  No SLEAP output found for '{camera_id}' video: {video_path.name}")

            if camera_pose_data:
                # Merge with existing pose data if any (e.g. from DLC)
                if camera_id in context.pose_data:
                    logger.warning(f"  Overwriting existing pose data for '{camera_id}' with SLEAP data")
                context.pose_data[camera_id] = camera_pose_data
                logger.info(f"  Pose '{camera_id}': Loaded SLEAP data for {len(camera_pose_data)} video(s)")

    elif context.options.skip_pose:
        logger.info("Skipping pose processing (requested by options)")

    if progress and task_id is not None:
        progress.advance(task_id)


def _ingest_ttl(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    ttl_patterns = {ttl_id: context.metadata["TTLs"][i]["paths"] for i, ttl_id in enumerate(context.ttl_files.keys()) if i < len(context.metadata.get("TTLs", []))}

    context.ttl_pulses = ttl.get_ttl_pulses(context.session_dir, ttl_patterns)
    for ttl_id, timestamps in context.ttl_pulses.items():
        if timestamps:
            logger.info(f"  TTL '{ttl_id}': {len(timestamps)} pulses, " f"range=[{timestamps[0]:.3f}, {timestamps[-1]:.3f}] s")
            if len(timestamps) > 0:
                logger.debug(f"    First 5 timestamps: {timestamps[:5]}")
        else:
            logger.warning(f"  TTL '{ttl_id}': No pulses extracted")

    if progress and task_id is not None:
        progress.advance(task_id)


def _compute_trial_offsets(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if context.bpod_data and context.config.bpod.sync.trial_types:
        logger.debug("Aligning Bpod trials to TTL pulses...")
        context.trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
            trial_type_configs=context.config.bpod.sync.trial_types,
            bpod_data=context.bpod_data,
            ttl_pulses=context.ttl_pulses,
        )
        logger.info(f"  Aligned {len(context.trial_offsets)} trials")
        if warnings:
            logger.warning(f"  {len(warnings)} alignment warnings")
            for w in warnings[:5]:  # Show first 5 warnings
                logger.debug(f"    Warning: {w}")
            if len(warnings) > 5:
                logger.debug(f"    ... and {len(warnings) - 5} more")
    else:
        logger.debug("Skipping trial alignment (missing Bpod data or sync config)")

    if progress and task_id is not None:
        progress.advance(task_id)
