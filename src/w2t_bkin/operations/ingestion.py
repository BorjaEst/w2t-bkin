"""Pure functions for ingesting Bpod, pose, and TTL data."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from w2t_bkin import sync, utils
from w2t_bkin.ingest import bpod as bpod_ingest
from w2t_bkin.ingest import events as ttl_ingest
from w2t_bkin.ingest import pose as pose_ingest
from w2t_bkin.models import BpodData, DiscoveryResult, PoseData, SessionInfo, TTLData, VideoChunk, VideoData

logger = logging.getLogger(__name__)


def ingest_ttls(discovery: DiscoveryResult, info: SessionInfo) -> Dict[str, TTLData]:
    """Ingest TTL pulse data from discovered files.

    Args:
        discovery: Discovery result containing ttl_files dict
        info: Session information

    Returns:
        Dict mapping ttl_id to TTLData

    Example:
        >>> ttl_data = ingest_ttls(discovery, info)
        >>> ttl_data["ttl_camera"].pulse_count
        510392
    """
    logger.info(f"Ingesting TTL data for session {info.session_id}")

    ttl_data = {}

    for ttl_id, file_paths in discovery.ttl_files.items():
        if not file_paths:
            logger.warning(f"No TTL files found for channel '{ttl_id}'")
            continue

        # Load and merge timestamps from all files
        all_timestamps = []
        for file_path in file_paths:
            timestamps = ttl_ingest.load_ttl_file(file_path)
            all_timestamps.extend(timestamps)
            logger.debug(f"Loaded {len(timestamps)} pulses from {file_path.name}")

        # Sort chronologically
        all_timestamps.sort()

        ttl_data[ttl_id] = TTLData(
            channel_id=ttl_id,
            timestamps=all_timestamps,
            source_files=file_paths,
        )

        logger.info(f"Ingested TTL channel '{ttl_id}': {len(all_timestamps)} pulses from {len(file_paths)} file(s)")

    return ttl_data


def ingest_videos(
    discovery: DiscoveryResult,
    info: SessionInfo,
    ttl_data: Optional[Dict[str, TTLData]],
    enable_loading: bool = True,
    ttl_validation: bool = True,
    ttl_tolerance: int = 0,
    mismatch_warn_only: bool = False,
) -> Dict[str, VideoData]:
    """Ingest video metadata with optional TTL validation.

    Args:
        discovery: Discovery result containing camera_files dict
        info: Session information
        ttl_data: TTL data dict (required if ttl_validation=True)
        enable_loading: If False, returns empty dict
        ttl_validation: If True, verify frame/TTL counts match
        ttl_tolerance: Allowed mismatch in frames
        mismatch_warn_only: If True, warn on mismatch instead of raising

    Returns:
        Dict mapping camera_id to VideoData

    Raises:
        ValueError: If ttl_validation enabled but ttl_data not provided
        MismatchExceedsToleranceError: If frame/TTL mismatch exceeds tolerance (and not warn_only)
    """
    from w2t_bkin.core.validate import verify_sync_counts
    from w2t_bkin.exceptions import MismatchExceedsToleranceError

    if not enable_loading:
        logger.info("Video ingestion disabled (config.ingestion.video.enable_loading=False)")
        return {}

    logger.info(f"Ingesting video data for session {info.session_id}")

    # Extract camera metadata
    cameras_meta = info.metadata.cameras
    camera_meta_by_id = {cam.id: cam for cam in cameras_meta}

    video_data = {}

    for camera_id, file_paths in discovery.camera_files.items():
        if not file_paths:
            logger.warning(f"No video files found for camera '{camera_id}'")
            continue

        # Get camera metadata
        cam_meta = camera_meta_by_id.get(camera_id)
        fps = cam_meta.fps if cam_meta is not None else None
        ttl_id = cam_meta.ttl_id if cam_meta is not None else None

        # Count frames for each video
        video_chunks = []
        total_frames = 0

        for video_path in file_paths:
            frame_count = utils.count_video_frames(video_path)
            video_chunks.append(VideoChunk(path=video_path, frame_count=frame_count))
            total_frames += frame_count
            logger.debug(f"  {camera_id}/{video_path.name}: {frame_count} frames")

        # TTL validation if enabled and camera has TTL sync configured
        if ttl_validation and ttl_id:
            if ttl_data is None:
                raise ValueError(f"TTL validation enabled for camera '{camera_id}' but ttl_data not provided. " "Ensure TTL ingestion runs before video ingestion.")

            if ttl_id not in ttl_data:
                msg = f"Camera '{camera_id}' references TTL channel '{ttl_id}' but it was not ingested"
                if mismatch_warn_only:
                    logger.warning(msg)
                else:
                    raise ValueError(msg)
            else:
                pulse_count = ttl_data[ttl_id].pulse_count

                try:
                    verify_sync_counts(
                        camera_id=camera_id,
                        ttl_id=ttl_id,
                        frame_count=total_frames,
                        pulse_count=pulse_count,
                        tolerance=ttl_tolerance,
                    )
                except MismatchExceedsToleranceError as e:
                    if mismatch_warn_only:
                        logger.warning(f"TTL validation mismatch for '{camera_id}': {e}")
                    else:
                        raise

        video_data[camera_id] = VideoData(
            camera_id=camera_id,
            videos=video_chunks,
            fps=fps,
            ttl_id=ttl_id,
        )

        logger.info(f"Ingested camera '{camera_id}': {total_frames} frames from {len(video_chunks)} file(s)")

    return video_data


def ingest_bpod(
    discovery: DiscoveryResult,
    info: SessionInfo,
    enable_loading: bool = True,
    continuous_time: bool = True,
) -> Optional[BpodData]:
    """Ingest Bpod behavioral data from discovered files.

    Args:
        discovery: Discovery result containing bpod_files dict
        info: Session information
        enable_loading: If False, returns None
        continuous_time: If True, offset timestamps for continuous timeline across files

    Returns:
        BpodData or None if no files or loading disabled

    Example:
        >>> bpod_data = ingest_bpod(discovery, info)
        >>> bpod_data.n_trials
        120
    """
    if not enable_loading:
        logger.info("Bpod ingestion disabled (config.ingestion.bpod.enable_loading=False)")
        return None

    logger.info(f"Ingesting Bpod data for session {info.session_id}")

    # Get Bpod files
    bpod_files = discovery.bpod_files.get("bpod", [])

    if not bpod_files:
        logger.warning("No Bpod files discovered")
        return None

    # Parse and merge Bpod files
    logger.debug(f"Parsing {len(bpod_files)} Bpod file(s) with continuous_time={continuous_time}")
    merged_data = bpod_ingest.parse_bpod_from_files(
        file_paths=bpod_files,
        continuous_time=continuous_time,
    )

    # Extract sync configuration from metadata (for TTL alignment)
    bpod_meta = info.metadata.bpod
    sync_trial_types = []
    if bpod_meta is not None and bpod_meta.sync is not None:
        sync_trial_types = bpod_meta.sync.trial_types

    bpod_data = BpodData(
        data=merged_data,
        source_files=bpod_files,
        sync_trial_types=sync_trial_types,
    )

    logger.info(f"Ingested Bpod data: {bpod_data.n_trials} trials from {len(bpod_files)} file(s)")
    if sync_trial_types:
        logger.debug(f"Loaded {len(sync_trial_types)} trial type sync configuration(s)")

    return bpod_data


def ingest_pose(
    discovery: DiscoveryResult,
    artifacts: Any,  # ArtifactsResult
    info: SessionInfo,
    enable_loading: bool = True,
    file_type: str = "h5",
) -> Dict[str, List[PoseData]]:
    """Ingest pose estimation data from artifacts or discovery.

    Args:
        discovery: Discovery result
        artifacts: Artifacts result containing pose file paths
        info: Session information
        enable_loading: If False, returns empty dict
        file_type: Preferred file type ('h5' or 'csv')

    Returns:
        Dict mapping camera_id to list of PoseData (one per video chunk)

    Example:
        >>> pose_data = ingest_pose(discovery, artifacts, info)
        >>> pose_data["camera_0"][0].frames
        [{'frame_index': 0, 'keypoints': {...}}, ...]
    """
    if not enable_loading:
        logger.info("Pose ingestion disabled (config.ingestion.pose.enable_loading=False)")
        return {}

    logger.info(f"Ingesting pose data for session {info.session_id}")

    pose_data_by_camera = {}

    # Get pose configuration from metadata
    pose_meta = info.metadata.pose
    cameras_config = pose_meta.cameras
    mappings = pose_meta.mappings

    # Determine pose files per camera (from artifacts first, fallback to discovery)
    pose_files_by_camera = {}

    if hasattr(artifacts, "pose_h5_by_camera") and file_type == "h5":
        pose_files_by_camera = artifacts.pose_h5_by_camera
    elif hasattr(artifacts, "pose_csv_by_camera") and file_type == "csv":
        pose_files_by_camera = artifacts.pose_csv_by_camera
    else:
        # Fallback: use discovery (if artifacts generation was skipped)
        logger.debug("No artifacts found, using discovery for pose files")
        pose_files_by_camera = discovery.pose_files

    if not pose_files_by_camera:
        logger.warning("No pose files found in artifacts or discovery")
        return {}

    # Get camera video files for association
    camera_video_files = discovery.camera_files

    for camera_id, pose_paths in pose_files_by_camera.items():
        if not pose_paths:
            continue

        camera_config = cameras_config.get(camera_id)
        source = camera_config.source if camera_config is not None else "dlc"
        mapping_id = camera_config.mapping_id if camera_config is not None else None
        mapping = mappings.get(mapping_id) if mapping_id else None

        pose_data_list = []

        for pose_path in pose_paths:
            # Associate pose file with video file (match by stem or index)
            video_paths = camera_video_files.get(camera_id, [])
            video_path = _match_pose_to_video(pose_path, video_paths)

            if video_path is None:
                logger.warning(f"Could not match pose file {pose_path.name} to a video for camera '{camera_id}'")
                # Use first video as fallback
                video_path = video_paths[0] if video_paths else pose_path.parent / "unknown_video.avi"

            # Import pose data based on source
            try:
                if source == "dlc":
                    frames, metadata = pose_ingest.import_dlc_pose(pose_path, mapping=mapping)
                elif source == "sleap":
                    frames, metadata = pose_ingest.import_sleap_pose(pose_path, mapping=mapping)
                else:
                    logger.error(f"Unknown pose source '{source}' for camera '{camera_id}'")
                    continue

                pose_data_list.append(
                    PoseData(
                        camera_id=camera_id,
                        video_path=video_path,
                        pose_path=pose_path,
                        frames=frames,
                        metadata=metadata,
                    )
                )

                logger.info(f"Ingested pose data for '{camera_id}' from {pose_path.name}: {len(frames)} frames")

            except Exception as e:
                logger.error(f"Failed to import pose data from {pose_path.name}: {e}")

        if pose_data_list:
            pose_data_by_camera[camera_id] = pose_data_list

    return pose_data_by_camera


def _match_pose_to_video(pose_path: Path, video_paths: List[Path]) -> Optional[Path]:
    """Match pose file to corresponding video file by stem.

    Args:
        pose_path: Path to pose estimation file
        video_paths: List of video file paths

    Returns:
        Matching video path or None
    """
    if not video_paths:
        return None

    # Try exact stem match first
    pose_stem = pose_path.stem
    # Remove common DLC/SLEAP suffixes
    pose_stem = pose_stem.replace("DLC", "").replace("_filtered", "").replace("_labeled", "")

    for video_path in video_paths:
        if pose_stem.startswith(video_path.stem) or video_path.stem.startswith(pose_stem):
            return video_path

    # If no match, return first video
    return video_paths[0]
