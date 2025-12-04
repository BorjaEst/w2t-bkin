"""Phase 5: Assembly."""

import logging
from typing import Optional

import numpy as np
from rich.progress import Progress, TaskID

from ....ingest import behavior, pose
from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_5(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Assemble NWB objects."""
    logger.info("Building behavior tables and pose estimation...")

    total_steps = 4
    if progress and task_id is not None:
        progress.update(task_id, total=total_steps)

    _assemble_behavior(context, progress, task_id)
    _assemble_pose(context, progress, task_id)


def _assemble_behavior(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if context.bpod_data and context.trial_offsets:
        # Extract type tables
        logger.debug("Extracting state, event, and action types...")
        state_types = behavior.extract_state_types(context.bpod_data)
        event_types = behavior.extract_event_types(context.bpod_data)
        action_types = behavior.extract_action_types(context.bpod_data)
        logger.debug(f"  Found {len(state_types)} state types, {len(event_types)} event types, {len(action_types)} action types")

        if progress and task_id is not None:
            progress.advance(task_id)

        # Extract data tables
        logger.debug("Extracting trial data...")
        states, state_indices = behavior.extract_states(context.bpod_data, state_types, trial_offsets=context.trial_offsets)
        events, event_indices = behavior.extract_events(context.bpod_data, event_types, trial_offsets=context.trial_offsets)
        actions, action_indices = behavior.extract_actions(context.bpod_data, action_types, trial_offsets=context.trial_offsets)

        logger.info(f"  States: {len(states)}, Events: {len(events)}, Actions: {len(actions)}")

        if progress and task_id is not None:
            progress.advance(task_id)

        # Build and add to NWBFile
        logger.debug("Building NWB tables...")
        task_recording = behavior.build_task_recording(states, events, actions)
        trials_table = behavior.build_trials_table(
            context.bpod_data,
            task_recording,
            state_indices,
            event_indices,
            action_indices,
            trial_offsets=context.trial_offsets,
        )

        task_arguments = behavior.extract_task_arguments(context.bpod_data)
        task = behavior.build_task(state_types, event_types, action_types, task_arguments=task_arguments)

        context.nwbfile.trials = trials_table
        context.nwbfile.add_acquisition(task_recording)
        context.nwbfile.add_lab_meta_data(task)

        logger.info(f"  Added TrialsTable ({len(trials_table)} trials), TaskRecording, and Task to NWBFile")

        if progress and task_id is not None:
            progress.advance(task_id)
    else:
        logger.warning("Skipping behavior table assembly (missing Bpod data or trial offsets)")
        if progress and task_id is not None:
            progress.update(task_id, completed=3)


def _assemble_pose(context: PipelineContext, progress: Optional[Progress], task_id: Optional[TaskID]) -> None:
    if context.pose_data:
        logger.debug("Building PoseEstimation objects...")

        # Ensure behavior processing module exists
        if "behavior" not in context.nwbfile.processing:
            context.nwbfile.create_processing_module(name="behavior", description="Behavioral data including pose estimation")

        behavior_module = context.nwbfile.processing["behavior"]

        # Collect skeletons to add to NWB
        skeletons_to_add = []

        for camera_id, video_pose_list in context.pose_data.items():
            if not video_pose_list:
                continue

            # Find camera config
            camera_config = next((c for c in context.metadata.get("cameras", []) if c["id"] == camera_id), None)
            fps = camera_config.get("fps", 30.0) if camera_config else 30.0
            ttl_id = camera_config.get("ttl_id") if camera_config else None
            target_skel_id = camera_config.get("skeleton_id") if camera_config else None

            # Determine Skeleton
            # 1. Default from H5 metadata
            first_meta = video_pose_list[0]["metadata"]
            skeleton_nodes = first_meta.bodyparts
            skeleton_edges = []
            skeleton_name = f"skeleton_{camera_id}"

            # 2. Override from metadata['skeletons'] if configured
            skeletons_config = context.metadata.get("skeletons", {})
            # Handle list format [[skeletons]] -> convert to dict
            if isinstance(skeletons_config, list):
                skeletons_config = {s.get("id", f"skel_{i}"): s for i, s in enumerate(skeletons_config)}

            if target_skel_id and target_skel_id in skeletons_config:
                user_skel = skeletons_config[target_skel_id]
                skeleton_nodes = user_skel.get("nodes", skeleton_nodes)
                skeleton_edges = user_skel.get("edges", [])
                skeleton_name = target_skel_id
                logger.debug(f"  Using user-defined skeleton '{skeleton_name}' for {camera_id}")

            # Create Skeleton object
            try:
                skeleton = pose.create_skeleton(name=skeleton_name, nodes=skeleton_nodes, edges=skeleton_edges)
                skeletons_to_add.append(skeleton)
            except Exception as e:
                logger.warning(f"  Failed to create skeleton for {camera_id}: {e}")
                continue

            # Process each video
            for i, item in enumerate(video_pose_list):
                frames = item["frames"]
                metadata = item["metadata"]
                video_path = item["video_path"]
                n_frames = len(frames)

                # Timestamp Logic
                timestamps = None

                # Strategy 1: TTL Alignment
                if ttl_id and ttl_id in context.ttl_pulses:
                    pulses = context.ttl_pulses[ttl_id]
                    # Exact match check (simple case)
                    if len(pulses) == n_frames:
                        timestamps = np.array(pulses)
                        logger.info(f"  Using TTL timestamps for {camera_id}/{video_path.name} ({n_frames} frames)")
                    else:
                        # TODO: Handle complex cases (split videos, etc.)
                        logger.warning(f"  TTL count ({len(pulses)}) != Frame count ({n_frames}) for {camera_id}. Falling back to FPS.")

                # Strategy 2: FPS Generation
                if timestamps is None:
                    # Generate timestamps based on FPS
                    # Note: This assumes start time is 0.0 relative to session start
                    timestamps = np.arange(n_frames) / fps
                    logger.info(f"  Using FPS timestamps ({fps} Hz) for {camera_id}/{video_path.name}")

                try:
                    # Use device if available
                    device = context.nwbfile.devices.get(camera_id)

                    pe = pose.build_pose_estimation(
                        data=(frames, metadata),
                        reference_times=timestamps,
                        skeleton=skeleton,
                        original_videos=[str(video_path)],
                        labeled_videos=None,
                        devices=[device] if device else None,
                    )

                    # Ensure unique name if multiple videos per camera
                    if len(video_pose_list) > 1:
                        pe.name = f"{pe.name}_{i}"

                    behavior_module.add(pe)
                    logger.info(f"  Added PoseEstimation: {pe.name} ({n_frames} frames)")

                except Exception as e:
                    logger.warning(f"  Failed to build PoseEstimation for {camera_id} (video {video_path.name}): {e}")

        # Add Skeletons container to NWB
        if skeletons_to_add:
            try:
                # Deduplicate skeletons by name
                unique_skeletons = {s.name: s for s in skeletons_to_add}.values()
                skeletons_container = pose.create_skeletons_container(name="Skeletons", skeletons=list(unique_skeletons))
                context.nwbfile.add_lab_meta_data(skeletons_container)
                logger.debug(f"  Added Skeletons container with {len(unique_skeletons)} skeletons")
            except Exception as e:
                logger.warning(f"  Failed to add Skeletons container: {e}")

    if progress and task_id is not None:
        progress.advance(task_id)
