"""Prefect tasks for configuration and initialization."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from prefect import task
from pynwb import NWBFile

from w2t_bkin.models import SessionConfig
from w2t_bkin.operations import create_nwb_file, load_session_config

logger = logging.getLogger(__name__)


@task(
    name="Load Session Config",
    description="Load session configuration and metadata using 2-layer config hierarchy",
    tags=["config", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def load_session_config_task(
    base_config_path: Optional[Path] = None,
    project_config_path: Optional[Path] = None,
    subject_id: str = ...,
    session_id: str = ...,
) -> SessionConfig:
    """Load session configuration using 2-layer config hierarchy.

    Prefect task wrapper for load_session_config operation.

    The configuration system uses a 2-layer hierarchy:
    - Base: Package defaults (if not provided, uses built-in standard.toml)
    - Project: User/experiment settings (optional, from 'w2t-bkin data init')

    Args:
        base_config_path: Base configuration file (package defaults, optional)
        project_config_path: Project-specific configuration (optional)
        subject_id: Subject identifier
        session_id: Session identifier

    Returns:
        Immutable SessionConfig object

    Raises:
        FileNotFoundError: If config or session directory not found
        ValueError: If configuration is invalid
    """
    logger.info(f"Loading configuration for {subject_id}/{session_id}")

    return load_session_config(
        base_config_path=base_config_path,
        project_config_path=project_config_path,
        subject_id=subject_id,
        session_id=session_id,
    )


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
