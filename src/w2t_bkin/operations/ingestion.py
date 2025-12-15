"""Pure functions for ingesting Bpod, pose, and TTL data."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from w2t_bkin import sync, utils
from w2t_bkin.ingest import bpod as bpod_ingest
from w2t_bkin.ingest import pose as pose_ingest
from w2t_bkin.ingest import ttl as ttl_ingest
from w2t_bkin.models import BpodData, PoseData, SessionConfig, TrialAlignment, TTLData

logger = logging.getLogger(__name__)


def ingest_bpod_data(session_dir: Path, pattern: str, order: str = "time_asc", continuous_time: bool = False) -> BpodData:
    """Ingest Bpod behavioral data files.

    Pure function that parses Bpod MAT files and extracts trial data.

    Args:
        session_dir: Path to session directory
        pattern: File pattern for Bpod data files
        order: Trial ordering ("time_asc", "time_desc", "file_order")
        continuous_time: Whether to use continuous time

    Returns:
        BpodData object with parsed data and trial count

    Raises:
        FileNotFoundError: If no Bpod files found
        ValueError: If parsing fails
    """
    logger.info(f"Ingesting Bpod data from {session_dir}")
    logger.debug(f"Pattern: {pattern}, order: {order}, continuous_time: {continuous_time}")

    # Parse Bpod files
    bpod_data = bpod_ingest.parse_bpod(session_dir=session_dir, pattern=pattern, order=order, continuous_time=continuous_time)

    # Extract trial count
    session_data = utils.convert_matlab_struct(bpod_data.get("SessionData", {}))
    raw_events = utils.convert_matlab_struct(session_data.get("RawEvents", {}))
    trials = raw_events.get("Trial", [])
    n_trials = len(trials) if trials is not None else 0

    logger.info(f"Extracted {n_trials} trials from Bpod data")
    logger.debug(f"SessionData keys: {list(session_data.keys())}")

    return BpodData(data=bpod_data, n_trials=n_trials)


def ingest_dlc_poses(video_paths: List[Path], dlc_dir: Path, camera_id: str) -> List[PoseData]:
    """Ingest DLC pose estimation data for video files.

    Pure function that loads DLC H5 files matching video file names.

    Args:
        video_paths: List of video file paths
        dlc_dir: Directory containing DLC H5 outputs
        camera_id: Camera identifier

    Returns:
        List of PoseData objects for successfully loaded poses
    """
    logger.info(f"Ingesting DLC poses for camera '{camera_id}'")

    pose_data = []

    for video_path in video_paths:
        video_stem = video_path.stem

        # Look for DLC output files: {video_stem}DLC_*.h5
        dlc_files = list(dlc_dir.glob(f"{video_stem}DLC_*.h5"))

        if dlc_files:
            dlc_path = dlc_files[0]  # Take first match
            logger.debug(f"Found DLC output: {dlc_path.name}")

            try:
                frames, metadata = pose_ingest.import_dlc_pose(dlc_path)
                pose_data.append(PoseData(video_path=video_path, frames=frames, metadata=metadata))
                logger.debug(f"Loaded DLC data for {video_path.name}")
            except Exception as e:
                logger.warning(f"Failed to import DLC pose for {video_path.name}: {e}")
        else:
            logger.debug(f"No DLC output found for {video_path.name}")

    logger.info(f"Loaded DLC data for {len(pose_data)}/{len(video_paths)} video(s)")
    return pose_data


def ingest_sleap_poses(video_paths: List[Path], sleap_dir: Path, camera_id: str) -> List[PoseData]:
    """Ingest SLEAP pose estimation data for video files.

    Pure function that loads SLEAP H5 files matching video file names.

    Args:
        video_paths: List of video file paths
        sleap_dir: Directory containing SLEAP H5 outputs
        camera_id: Camera identifier

    Returns:
        List of PoseData objects for successfully loaded poses
    """
    logger.info(f"Ingesting SLEAP poses for camera '{camera_id}'")

    pose_data = []

    for video_path in video_paths:
        video_stem = video_path.stem

        # Look for SLEAP output files: {video_stem}.sleap.h5
        sleap_files = list(sleap_dir.glob(f"{video_stem}.sleap.h5"))

        if sleap_files:
            sleap_path = sleap_files[0]
            logger.debug(f"Found SLEAP output: {sleap_path.name}")

            try:
                frames, metadata = pose_ingest.import_sleap_pose(sleap_path)
                pose_data.append(PoseData(video_path=video_path, frames=frames, metadata=metadata))
                logger.debug(f"Loaded SLEAP data for {video_path.name}")
            except Exception as e:
                logger.warning(f"Failed to import SLEAP pose for {video_path.name}: {e}")
        else:
            logger.debug(f"No SLEAP output found for {video_path.name}")

    logger.info(f"Loaded SLEAP data for {len(pose_data)}/{len(video_paths)} video(s)")
    return pose_data


def ingest_ttl_pulses(session_dir: Path, ttl_patterns: Dict[str, str]) -> Dict[str, TTLData]:
    """Ingest TTL pulse timestamps from files.

    Pure function that extracts TTL pulse timestamps for all configured channels.

    Args:
        session_dir: Path to session directory
        ttl_patterns: Dictionary mapping TTL ID to file pattern

    Returns:
        Dictionary mapping TTL ID to TTLData objects
    """
    logger.info(f"Ingesting TTL pulses from {session_dir}")

    # Extract all TTL pulses
    ttl_pulses = ttl_ingest.get_ttl_pulses(session_dir, ttl_patterns)

    # Convert to TTLData objects
    ttl_data = {}
    for ttl_id, timestamps in ttl_pulses.items():
        if timestamps:
            logger.info(f"TTL '{ttl_id}': {len(timestamps)} pulses, " f"range=[{timestamps[0]:.3f}, {timestamps[-1]:.3f}] s")
            logger.debug(f"First 5 timestamps: {timestamps[:5]}")
        else:
            logger.warning(f"TTL '{ttl_id}': No pulses extracted")

        ttl_data[ttl_id] = TTLData(ttl_id=ttl_id, timestamps=timestamps)

    return ttl_data


def align_trials_to_ttl(trial_type_configs: Dict, bpod_data: Dict, ttl_pulses: Dict[str, List[float]]) -> TrialAlignment:
    """Align Bpod trials to TTL pulses for temporal synchronization.

    Pure function that computes trial offsets based on TTL alignment.

    Args:
        trial_type_configs: Trial type synchronization configurations
        bpod_data: Parsed Bpod data structure
        ttl_pulses: TTL pulse timestamps per channel

    Returns:
        TrialAlignment object with offsets and warnings
    """
    logger.info("Aligning Bpod trials to TTL pulses")

    trial_offsets, warnings = sync.align_bpod_trials_to_ttl(trial_type_configs=trial_type_configs, bpod_data=bpod_data, ttl_pulses=ttl_pulses)

    logger.info(f"Aligned {len(trial_offsets)} trials")

    if warnings:
        logger.debug(f"Trial alignment warnings ({len(warnings)} total):")
        for warning in warnings:
            logger.debug(f"  {warning}")
        logger.warning(f"{len(warnings)} alignment warnings")

    return TrialAlignment(trial_offsets=trial_offsets, warnings=warnings)


def ingest_session_data(session_config: SessionConfig, camera_files: Dict[str, List[Path]], skip_bpod: bool = False, skip_pose: bool = False) -> Dict[str, Any]:
    """Ingest all data types for a session.

    Convenience function that orchestrates Bpod, pose, and TTL ingestion.

    Args:
        session_config: Session configuration
        camera_files: Discovered camera video files
        skip_bpod: Skip Bpod ingestion
        skip_pose: Skip pose ingestion

    Returns:
        Dictionary containing ingested data:
        - bpod_data: BpodData or None
        - pose_data: Dict[camera_id, List[PoseData]]
        - ttl_data: Dict[ttl_id, TTLData]
        - trial_alignment: TrialAlignment or None
    """
    logger.info(f"Ingesting session data for {session_config.session_id}")

    result = {"bpod_data": None, "pose_data": {}, "ttl_data": {}, "trial_alignment": None}

    # Ingest Bpod
    if not skip_bpod:
        bpod_config = session_config.metadata.get("bpod", {})
        if bpod_config:
            result["bpod_data"] = ingest_bpod_data(
                session_dir=session_config.session_dir,
                pattern=bpod_config["path"],
                order=bpod_config.get("order", "time_asc"),
                continuous_time=bpod_config.get("continuous_time", False),
            )

    # Ingest pose data
    if not skip_pose:
        # DLC
        if session_config.config.preprocessing.dlc.enabled:
            interim_dlc_dir = session_config.interim_dir / "dlc"

            for camera_id, video_paths in camera_files.items():
                if video_paths:
                    pose_data = ingest_dlc_poses(video_paths=video_paths, dlc_dir=interim_dlc_dir, camera_id=camera_id)
                    if pose_data:
                        result["pose_data"][camera_id] = pose_data

        # SLEAP
        if session_config.config.preprocessing.sleap.enabled:
            interim_sleap_dir = session_config.interim_dir / "sleap"

            for camera_id, video_paths in camera_files.items():
                if video_paths:
                    pose_data = ingest_sleap_poses(video_paths=video_paths, sleap_dir=interim_sleap_dir, camera_id=camera_id)
                    if pose_data:
                        # Merge or replace existing
                        if camera_id in result["pose_data"]:
                            logger.warning(f"Overwriting DLC pose data for '{camera_id}' with SLEAP data")
                        result["pose_data"][camera_id] = pose_data

    # Ingest TTL pulses
    ttl_config = session_config.metadata.get("TTLs", [])
    if ttl_config:
        ttl_patterns = {ttl["id"]: ttl["paths"] for ttl in ttl_config}
        result["ttl_data"] = ingest_ttl_pulses(session_dir=session_config.session_dir, ttl_patterns=ttl_patterns)

    # Align trials to TTL
    if result["bpod_data"] and session_config.config.bpod.sync.trial_types:
        # Convert TTLData to simple dict of timestamps
        ttl_pulses = {ttl_id: data.timestamps for ttl_id, data in result["ttl_data"].items()}

        result["trial_alignment"] = align_trials_to_ttl(trial_type_configs=session_config.config.bpod.sync.trial_types, bpod_data=result["bpod_data"].data, ttl_pulses=ttl_pulses)

    return result
