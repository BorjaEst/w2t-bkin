"""Prefect tasks for NWB data structure assembly."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prefect import get_run_logger, task
from pynwb import NWBFile

from w2t_bkin.config import AssemblyConfig
from w2t_bkin.core import session as session_core
from w2t_bkin.ingest import events as events_ingest
from w2t_bkin.models import BpodData, PoseData, SessionInfo, TTLData, VideoData
from w2t_bkin.operations import assembly as assembly_ops

logger = logging.getLogger(__name__)


@task(
    name="Create NWB File",
    description="Initialize NWB file from session metadata",
    tags=["nwb", "initialization"],
    retries=1,
)
def create_nwb_file_task(session_info: SessionInfo) -> NWBFile:
    """Create and initialize NWB file object.

    Prefect task wrapper for create_nwb_file operation.

    Args:
        session_info: Session configuration

    Returns:
        Initialized NWBFile object

    Raises:
        ValueError: If metadata is invalid
    """
    logger.info(f"Creating NWB file for session {session_info.session_id}")

    # Create NWBFile directly from metadata using core.session primitive
    nwbfile = session_core.create_nwb_file(session_info.metadata.model_dump(exclude_none=True))

    logger.info(f"NWBFile created: identifier='{nwbfile.identifier}'")

    if nwbfile.subject:
        logger.debug(f"  Subject: {nwbfile.subject.subject_id}")

    return nwbfile


@task(
    name="Assemble Events Table",
    description="Assemble TTL events into NWB file",
    tags=["nwb", "assembly", "ttl"],
    retries=1,
)
def assemble_events_table(nwbfile: NWBFile, ttl_data: Dict[str, TTLData], config: AssemblyConfig) -> None:
    """Assemble TTL pulse data into NWB EventsTable (ndx-events).

    Args:
        nwbfile: NWB file to modify (in-place)
        ttl_data: Dict mapping ttl_id to TTLData
        config: Assembly configuration

    Raises:
        ValueError: If TTL data is invalid
    """
    run_logger = get_run_logger()

    if not ttl_data:
        run_logger.info("No TTL data to assemble (empty dict)")
        return

    run_logger.info(f"Assembling TTL events from {len(ttl_data)} channel(s)")

    # Convert TTLData objects to primitive dict for ingest module
    ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}

    # Build descriptions from TTL metadata (if available)
    descriptions = {}
    sources = {}
    for ttl_id, ttl in ttl_data.items():
        # Use channel_id as description fallback
        descriptions[ttl_id] = f"TTL pulses from {ttl_id}"
        # Build source provenance from file paths
        if ttl.source_files:
            sources[ttl_id] = ", ".join(f.name for f in ttl.source_files[:3])  # Limit to first 3 files
            if len(ttl.source_files) > 3:
                sources[ttl_id] += f" (+{len(ttl.source_files) - 3} more)"

    # Add TTL table to NWB file using ingest module
    events_ingest.add_ttl_table_to_nwb(
        nwbfile=nwbfile,
        ttl_pulses=ttl_pulses,
        descriptions=descriptions,
        sources=sources,
        container_name="TTLEvents",
    )

    total_pulses = sum(len(ttl.timestamps) for ttl in ttl_data.values())
    run_logger.info(f"Added EventsTable with {total_pulses} total pulses to acquisition")


@task(
    name="Assemble Behavior Tables",
    description="Assemble behavioral data into NWB file",
    tags=["nwb", "assembly", "behavior"],
    retries=1,
)
def assemble_behavior_tables(
    nwbfile: NWBFile,
    bpod_data: Optional[BpodData],
    trial_offsets: Dict[int, float],
    config: AssemblyConfig,
) -> Optional[Tuple[Any, Any, Any]]:
    """Assemble Bpod behavioral data into NWB structures (ndx-structured-behavior).

    Args:
        nwbfile: NWB file to modify (in-place)
        bpod_data: Parsed Bpod data (None if no data available)
        trial_offsets: Dict mapping trial_number → absolute time offset
        config: Assembly configuration

    Returns:
        Tuple of (trials_table, task_recording, task) or None if no data

    Raises:
        ValueError: If behavioral data assembly fails
    """
    run_logger = get_run_logger()

    if bpod_data is None:
        run_logger.info("No Bpod data to assemble (None)")
        return None

    run_logger.info(f"Assembling Bpod behavioral data: {bpod_data.n_trials} trials")

    # Delegate to pure operation (modifies nwbfile in-place)
    trials_table, task_recording, task = assembly_ops.assemble_behavior_tables(
        nwbfile=nwbfile,
        bpod_data=bpod_data,
        trial_offsets=trial_offsets,
    )

    run_logger.info(f"Added TrialsTable ({len(trials_table)} trials), " f"TaskRecording, and Task to NWBFile")

    return trials_table, task_recording, task


@task(
    name="Assemble Pose Estimation Data",
    description="Assemble pose estimation data into NWB file",
    tags=["nwb", "assembly", "pose"],
    retries=1,
)
def assemble_pose_estimation(
    nwbfile: NWBFile,
    pose_data: Optional[Dict[str, List[PoseData]]],
    video_data: Dict[str, VideoData],
    ttl_data: Dict[str, TTLData],
    config: AssemblyConfig,
) -> None:
    """Assemble pose estimation data into NWB structures (ndx-pose).

    Uses TTL pulses for timestamp alignment when available, otherwise falls back to FPS.

    Args:
        nwbfile: NWB file to modify (in-place)
        pose_data: Dict mapping camera_id to list of PoseData (one per video chunk)
        video_data: Dict mapping camera_id to VideoData (for fps/ttl_id)
        ttl_data: Dict mapping ttl_id to TTLData (for timestamp alignment)
        config: Assembly configuration

    Raises:
        ValueError: If pose assembly fails
    """
    run_logger = get_run_logger()

    if not pose_data:
        run_logger.info("No pose data to assemble (empty dict or None)")
        return

    run_logger.info(f"Assembling pose estimation for {len(pose_data)} camera(s)")

    # Process each camera's pose data
    all_skeletons = []

    for camera_id, pose_list in pose_data.items():
        if not pose_list:
            run_logger.warning(f"Skipping camera '{camera_id}': no pose data")
            continue

        # Build camera config from video_data
        camera_config = {}
        if camera_id in video_data:
            vid = video_data[camera_id]
            camera_config["fps"] = vid.fps if vid.fps is not None else 30.0
            camera_config["ttl_id"] = vid.ttl_id
        else:
            run_logger.warning(f"Camera '{camera_id}' not in video_data, using default fps=30.0, no TTL sync")
            camera_config["fps"] = 30.0
            camera_config["ttl_id"] = None

        # Assemble pose for this camera
        pose_estimations = assembly_ops.assemble_pose_estimation(
            nwbfile=nwbfile,
            camera_id=camera_id,
            pose_data_list=pose_list,
            camera_config=camera_config,
            ttl_pulses=ttl_data,  # Pass entire dict; function extracts ttl_id channel
            skeletons_config=None,  # TODO: extract from metadata if needed
        )

        # Collect skeletons for global container
        for pe in pose_estimations:
            if hasattr(pe, "skeleton") and pe.skeleton is not None:
                all_skeletons.append(pe.skeleton)

        run_logger.info(f"Added {len(pose_estimations)} PoseEstimation object(s) for camera '{camera_id}'")

    # Add Skeletons container if any skeletons were created
    if all_skeletons:
        assembly_ops.add_skeletons_container(nwbfile, all_skeletons)
        run_logger.info(f"Added Skeletons container with {len(all_skeletons)} skeleton(s)")

    run_logger.info("Pose estimation assembly completed")


@task(
    name="Assemble Video Data",
    description="Assemble video data into NWB file",
    tags=["nwb", "assembly", "video"],
    retries=1,
)
def assemble_videos_into_nwb(
    nwbfile: NWBFile,
    video_data: Dict[str, VideoData],
    config: AssemblyConfig,
) -> None:
    """Assemble video metadata into NWB ImageSeries with external file links.

    Creates ImageSeries objects referencing external video files (not embedded).
    Supports multi-file videos with proper starting_frame indices.

    Args:
        nwbfile: NWB file to modify (in-place)
        video_data: Dict mapping camera_id to VideoData
        config: Assembly configuration

    Raises:
        ValueError: If video assembly fails
    """
    run_logger = get_run_logger()

    if not video_data:
        run_logger.info("No video data to assemble (empty dict)")
        return

    run_logger.info(f"Assembling video metadata for {len(video_data)} camera(s)")

    for camera_id, video in video_data.items():
        # Convert Path objects to strings for NWB
        video_files = [str(p) for p in video.video_paths]
        frame_counts = video.frame_counts
        fps = video.fps if video.fps is not None else 30.0

        # Get device if available
        device = nwbfile.devices.get(camera_id)

        # Add to NWB using core session primitive
        session_core.add_video_acquisition(
            nwbfile=nwbfile,
            camera_id=camera_id,
            video_files=video_files,
            frame_rate=fps,
            device=device,
            frame_counts=frame_counts if len(video_files) > 1 else None,
        )

        run_logger.info(f"Added ImageSeries for camera '{camera_id}': " f"{video.total_frames} frames from {len(video_files)} file(s)")

    run_logger.info("Video assembly completed")
