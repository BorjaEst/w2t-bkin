"""Pure functions for assembling NWB data structures."""

import logging
from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
from pynwb import NWBFile

from w2t_bkin.ingest import behavior, pose
from w2t_bkin.models import BpodData, PoseData, TTLData

logger = logging.getLogger(__name__)


def assemble_behavior_tables(nwbfile: NWBFile, bpod_data: BpodData, trial_offsets: Dict[int, float]) -> Tuple[Any, Any, Any]:
    """Assemble behavior tables (states, events, actions) and add to NWB file.

    Pure function that extracts behavioral data and builds NWB structures.
    Modifies nwbfile in place by adding trials, task_recording, and task.

    Args:
        nwbfile: NWB file object to modify
        bpod_data: Parsed Bpod data
        trial_offsets: Dict mapping trial_number -> absolute time offset

    Returns:
        Tuple of (trials_table, task_recording, task) objects

    Raises:
        ValueError: If data extraction fails
    """
    logger.info("Assembling behavior tables")

    # Extract type tables
    logger.debug("Extracting state, event, and action types")
    state_types = behavior.extract_state_types(bpod_data.data)
    event_types = behavior.extract_event_types(bpod_data.data)
    action_types = behavior.extract_action_types(bpod_data.data)

    logger.debug(f"Found {len(state_types)} state types, " f"{len(event_types)} event types, " f"{len(action_types)} action types")

    # Extract data tables
    logger.debug("Extracting trial data")
    states, state_indices = behavior.extract_states(bpod_data.data, state_types, trial_offsets=trial_offsets)
    events, event_indices = behavior.extract_events(bpod_data.data, event_types, trial_offsets=trial_offsets)
    actions, action_indices = behavior.extract_actions(bpod_data.data, action_types, trial_offsets=trial_offsets)

    logger.info(f"States: {len(states)}, Events: {len(events)}, Actions: {len(actions)}")

    # Build NWB tables
    logger.debug("Building NWB tables")

    # Suppress HDMF warnings about DynamicTableRegion ancestry
    # Valid NWB structure but triggers warnings during construction
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*does not share an ancestor.*",
            category=UserWarning,
            module="hdmf.container",
        )

        task_recording = behavior.build_task_recording(states, events, actions)
        trials_table = behavior.build_trials_table(
            bpod_data.data,
            task_recording,
            state_indices,
            event_indices,
            action_indices,
            trial_offsets=trial_offsets,
        )

    task_arguments = behavior.extract_task_arguments(bpod_data.data)
    task = behavior.build_task(state_types, event_types, action_types, task_arguments=task_arguments)

    # Add to NWB file
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*does not share an ancestor.*",
            category=UserWarning,
            module="hdmf.container",
        )

        nwbfile.trials = trials_table
        nwbfile.add_acquisition(task_recording)
        nwbfile.add_lab_meta_data(task)

    logger.info(f"Added TrialsTable ({len(trials_table)} trials), " f"TaskRecording, and Task to NWBFile")

    return trials_table, task_recording, task


def assemble_pose_estimation(
    nwbfile: NWBFile,
    camera_id: str,
    pose_data_list: List[PoseData],
    camera_config: Dict[str, Any],
    ttl_pulses: Optional[Dict[str, TTLData]],
    skeletons_config: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """Assemble pose estimation data for one camera and add to NWB file.

    Pure function that builds PoseEstimation objects and adds to behavior module.
    Modifies nwbfile in place.

    Multi-video handling: For cameras with multiple video chunks (e.g., buffer rollover),
    each video gets its own PoseEstimation object with synchronized timestamps. This
    effectively concatenates pose data across the session while preserving provenance
    (original_videos field records which video each chunk came from).

    Args:
        nwbfile: NWB file object to modify
        camera_id: Camera identifier
        pose_data_list: List of PoseData for this camera (one per video chunk)
        camera_config: Camera configuration (fps, ttl_id, skeleton_id)
        ttl_pulses: TTL pulse data (optional for timestamp alignment)
        skeletons_config: Skeleton definitions (optional)

    Returns:
        List of created PoseEstimation objects (one per video chunk)

    Raises:
        ValueError: If pose assembly fails
    """
    logger.info(f"Assembling pose estimation for camera '{camera_id}'")

    if not pose_data_list:
        logger.warning(f"No pose data for camera '{camera_id}'")
        return []

    # Ensure behavior processing module exists
    if "behavior" not in nwbfile.processing:
        nwbfile.create_processing_module(name="behavior", description="Behavioral data including pose estimation")

    behavior_module = nwbfile.processing["behavior"]

    # Get camera parameters with type validation
    fps_raw = camera_config.get("fps", 30.0)
    fps = float(fps_raw) if fps_raw is not None else 30.0
    ttl_id = camera_config.get("ttl_id")
    target_skel_id = camera_config.get("skeleton_id")

    # Determine skeleton definition
    first_meta = pose_data_list[0].metadata
    skeleton_nodes = first_meta.bodyparts if hasattr(first_meta, "bodyparts") else []
    skeleton_edges = []
    skeleton_name = f"skeleton_{camera_id}"

    # Override with user-defined skeleton if configured
    if skeletons_config and target_skel_id and target_skel_id in skeletons_config:
        user_skel = skeletons_config[target_skel_id]
        skeleton_nodes = user_skel.get("nodes", skeleton_nodes)
        skeleton_edges = user_skel.get("edges", [])
        skeleton_name = target_skel_id
        logger.debug(f"Using user-defined skeleton '{skeleton_name}' for {camera_id}")

    # Create skeleton object
    try:
        skeleton = pose.create_skeleton(name=skeleton_name, nodes=skeleton_nodes, edges=skeleton_edges)
    except Exception as e:
        logger.error(f"Failed to create skeleton for {camera_id}: {e}")
        raise ValueError(f"Skeleton creation failed: {e}")

    # Process each video's pose data
    pose_estimations = []

    for i, pd in enumerate(pose_data_list):
        frames = pd.frames
        metadata = pd.metadata
        video_path = pd.video_path
        n_frames = len(frames)

        # Compute timestamps
        timestamps = None

        # Strategy 1: TTL alignment
        if ttl_id and ttl_pulses and ttl_id in ttl_pulses:
            pulses = ttl_pulses[ttl_id].timestamps
            if len(pulses) == n_frames:
                timestamps = np.array(pulses)
                logger.info(f"Using TTL timestamps for {camera_id}/{video_path.name} " f"({n_frames} frames)")
            else:
                logger.warning(f"TTL count ({len(pulses)}) != Frame count ({n_frames}) " f"for {camera_id}. Falling back to FPS.")

        # Strategy 2: FPS generation
        if timestamps is None:
            timestamps = np.arange(n_frames) / fps
            logger.info(f"Using FPS timestamps ({fps} Hz) for {camera_id}/{video_path.name}")

        try:
            # Get device if available
            device = nwbfile.devices.get(camera_id)

            # Build pose estimation
            pe = pose.build_pose_estimation(
                data=(frames, metadata),
                reference_times=timestamps,
                skeleton=skeleton,
                original_videos=[str(video_path)],
                labeled_videos=None,
                devices=[device] if device else None,
            )

            # Ensure unique name if multiple videos per camera
            if len(pose_data_list) > 1:
                pe.name = f"{pe.name}_{i}"

            behavior_module.add(pe)
            pose_estimations.append(pe)

            logger.info(f"Added PoseEstimation: {pe.name} ({n_frames} frames)")

        except Exception as e:
            logger.warning(f"Failed to build PoseEstimation for {camera_id} " f"(video {video_path.name}): {e}")

    return pose_estimations


def add_skeletons_container(nwbfile: NWBFile, skeletons: List[Any]) -> Any:
    """Add Skeletons container to NWB file.

    Pure function that creates and adds a Skeletons container.
    Modifies nwbfile in place.

    Args:
        nwbfile: NWB file object to modify
        skeletons: List of Skeleton objects

    Returns:
        Skeletons container object

    Raises:
        ValueError: If skeletons container creation fails
    """
    logger.debug(f"Adding Skeletons container with {len(skeletons)} skeleton(s)")

    if not skeletons:
        logger.warning("No skeletons to add")
        return None

    try:
        # Deduplicate by name
        unique_skeletons = {s.name: s for s in skeletons}.values()

        skeletons_container = pose.create_skeletons_container(name="Skeletons", skeletons=list(unique_skeletons))

        nwbfile.add_lab_meta_data(skeletons_container)

        logger.debug(f"Added Skeletons container with {len(unique_skeletons)} skeletons")
        return skeletons_container

    except Exception as e:
        logger.error(f"Failed to add Skeletons container: {e}")
        raise ValueError(f"Skeletons container creation failed: {e}")
