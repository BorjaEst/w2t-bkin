"""Prefect tasks for NWB data structure assembly."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prefect import task
from pynwb import NWBFile

from w2t_bkin.config import SessionConfig
from w2t_bkin.core.session import build_metadata_paths
from w2t_bkin.core.session import create_nwb_file as core_create_nwb_file
from w2t_bkin.core.session import load_metadata
from w2t_bkin.models import BpodData, PoseData, SessionInfo, TTLData
from w2t_bkin.operations import add_skeletons_container, assemble_behavior_tables, assemble_pose_estimation

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
    logger.info(f"Creating NWB file for session {session_info.session_dir}")

    # Create NWBFile directly from metadata using core.session primitive
    nwbfile = core_create_nwb_file(session_info.metadata)

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
def assemble_events_table(nwbfile: NWBFile, ttl_data: TTLData, config: SessionConfig) -> None:
    pass


@task(
    name="Assemble Behavior Tables",
    description="Assemble behavioral data into NWB file",
    tags=["nwb", "assembly", "behavior"],
    retries=1,
)
def assemble_behavior_tables(nwbfile: NWBFile, bpod_data: BpodData, trial_offsets: List[float], config: SessionConfig) -> Tuple[Any, Any, Any]:
    pass


@task(
    name="Assemble Pose Estimation Data",
    description="Assemble pose estimation data into NWB file",
    tags=["nwb", "assembly", "pose"],
    retries=1,
)
def assemble_pose_estimation(nwbfile: NWBFile, pose_data: Optional[List[PoseData]], config: SessionConfig) -> None:
    pass


@task(
    name="Assemble Video Data",
    description="Assemble video data into NWB file",
    tags=["nwb", "assembly", "video"],
    retries=1,
)
def assemble_videos_into_nwb(nwbfile: NWBFile, video_info: Any, config: SessionConfig) -> None:
    pass
