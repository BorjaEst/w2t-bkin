"""Prefect tasks for configuration and initialization."""

import logging
from pathlib import Path
from typing import Any, Dict

from prefect import task
from pynwb import NWBFile

from ..models import SessionConfig
from ..operations import create_nwb_file, load_session_config

logger = logging.getLogger(__name__)


@task(
    name="Load Session Config",
    description="Load session configuration and metadata",
    tags=["config", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def load_session_config_task(config_path: Path, subject_id: str, session_id: str) -> SessionConfig:
    """Load session configuration and validate paths.

    Prefect task wrapper for load_session_config operation.

    Args:
        config_path: Path to configuration TOML file
        subject_id: Subject identifier
        session_id: Session identifier

    Returns:
        Immutable SessionConfig object

    Raises:
        FileNotFoundError: If config or session directory not found
        ValueError: If configuration is invalid
    """
    logger.info(f"Loading configuration for {subject_id}/{session_id}")

    return load_session_config(config_path=config_path, subject_id=subject_id, session_id=session_id)


@task(
    name="Create NWB File",
    description="Initialize NWB file from session metadata",
    tags=["nwb", "initialization"],
    retries=1,
)
def create_nwb_file_task(session_config: SessionConfig) -> NWBFile:
    """Create and initialize NWB file object.

    Prefect task wrapper for create_nwb_file operation.

    Args:
        session_config: Session configuration

    Returns:
        Initialized NWBFile object

    Raises:
        ValueError: If metadata is invalid
    """
    logger.info(f"Creating NWB file for session {session_config.session_id}")

    return create_nwb_file(session_config)
