"""Prefect tasks for configuration and initialization."""

import logging

from prefect import task
from pynwb import NWBFile

from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.models import SessionInfo
from w2t_bkin.operations import build_session_info, create_nwb_file

logger = logging.getLogger(__name__)


@task(
    name="Setup Session",
    description="Build SessionInfo from environment variables and configuration",
    tags=["config", "initialization"],
    retries=1,
)
def setup_flow_session_task(
    subject_id: str,
    session_id: str,
    session_config: SessionFlowConfig,
) -> SessionInfo:
    """Build SessionInfo from environment and configuration.

    Reads paths from environment variables and combines with config.

    Args:
        subject_id: Subject identifier
        session_id: Session identifier
        session_config: Pipeline configuration

    Returns:
        Immutable SessionInfo object

    Raises:
        EnvironmentError: If required env vars missing
        FileNotFoundError: If session directory not found
    """
    logger.info(f"Setting up session for {subject_id}/{session_id}")

    return build_session_info(
        subject_id=subject_id,
        session_id=session_id,
        session_config=session_config,
    )


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

    return create_nwb_file(session_info)
