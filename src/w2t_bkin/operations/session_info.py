"""Pure functions for loading and creating session configuration."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pynwb import NWBFile

from w2t_bkin import utils
from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.models import SessionInfo

logger = logging.getLogger(__name__)


def build_session_info(
    subject_id: str,
    session_id: str,
    session_config: SessionFlowConfig,
) -> SessionInfo:
    """Build SessionInfo from environment variables and configuration.

    Paths are read from environment variables (required):
    - W2T_RAW_ROOT: Raw data root directory
    - W2T_INTERMEDIATE_ROOT: Intermediate processing outputs
    - W2T_OUTPUT_ROOT: Output data root directory
    - W2T_MODELS_ROOT: Pose estimation models directory (optional, defaults to 'models')

    Args:
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")
        session_config: Pipeline configuration

    Returns:
        Immutable SessionInfo with all paths and settings

    Raises:
        EnvironmentError: If required environment variables are missing
        FileNotFoundError: If session directory doesn't exist
    """
    logger.debug(f"Building SessionInfo for {subject_id}/{session_id}")

    # Read paths from environment (fail fast if missing)
    raw_root_str = os.getenv("W2T_RAW_ROOT")
    if not raw_root_str:
        raise EnvironmentError("W2T_RAW_ROOT environment variable not set. " "Set it to your raw data directory (e.g., export W2T_RAW_ROOT=/data/raw)")

    interim_root_str = os.getenv("W2T_INTERMEDIATE_ROOT")
    if not interim_root_str:
        raise EnvironmentError("W2T_INTERMEDIATE_ROOT environment variable not set. " "Set it to your intermediate directory (e.g., export W2T_INTERMEDIATE_ROOT=/data/interim)")

    output_root_str = os.getenv("W2T_OUTPUT_ROOT")
    if not output_root_str:
        raise EnvironmentError("W2T_OUTPUT_ROOT environment variable not set. " "Set it to your output directory (e.g., export W2T_OUTPUT_ROOT=/data/processed)")

    models_root_str = os.getenv("W2T_MODELS_ROOT", "models")

    # Convert to absolute paths
    raw_root = Path(raw_root_str).resolve()
    interim_root = Path(interim_root_str).resolve()
    output_root = Path(output_root_str).resolve()
    models_root = Path(models_root_str).resolve()

    logger.info(f"Paths from environment:")
    logger.info(f"  Raw root: {raw_root}")
    logger.info(f"  Interim root: {interim_root}")
    logger.info(f"  Output root: {output_root}")
    logger.info(f"  Models root: {models_root}")

    # Determine session-specific paths
    session_dir = raw_root / subject_id / session_id
    interim_dir = interim_root / subject_id / session_id
    output_dir = output_root / subject_id / session_id

    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    # Load metadata from session directory
    # Use a minimal config object just for metadata loading
    # TODO: Refactor utils.load_session_metadata to not require Config
    from w2t_bkin.config import Config, PathsConfig, ProjectConfig

    temp_config = Config(
        project=ProjectConfig(name="temp"),
        paths=PathsConfig(
            raw_root=raw_root,
            intermediate_root=interim_root,
            output_root=output_root,
            models_root=models_root,
        ),
        synchronization=session_config.synchronization,
    )

    metadata, _ = utils.load_session_metadata_and_nwb(
        config=temp_config,
        subject_id=subject_id,
        session_id=session_id,
    )

    logger.info(f"SessionInfo built for {subject_id}/{session_id}")

    return SessionInfo(
        subject_id=subject_id,
        session_id=session_id,
        session_config=session_config,
        metadata=metadata,
        session_dir=session_dir,
        interim_dir=interim_dir,
        output_dir=output_dir,
        models_root=models_root,
    )


def create_nwb_file(session_info: SessionInfo) -> NWBFile:
    """Create NWBFile from session information.

    Pure function that creates an in-memory NWBFile object.

    Args:
        session_info: Session information with metadata

    Returns:
        In-memory NWBFile object (not yet written to disk)
    """
    logger.debug(f"Creating NWBFile for {session_info.subject_id}/{session_info.session_id}")

    # Use existing utility to create NWBFile
    # TODO: Refactor utils.load_session_metadata_and_nwb to accept metadata directly
    from w2t_bkin.config import Config, PathsConfig, ProjectConfig

    temp_config = Config(
        project=ProjectConfig(name="temp"),
        paths=PathsConfig(
            raw_root=session_info.session_dir.parent.parent,
            intermediate_root=session_info.interim_dir.parent.parent,
            output_root=session_info.output_dir.parent.parent,
            models_root=session_info.models_root,
        ),
        synchronization=session_info.session_config.synchronization,
    )

    _, nwbfile = utils.load_session_metadata_and_nwb(
        config=temp_config,
        subject_id=session_info.subject_id,
        session_id=session_info.session_id,
    )

    logger.info(f"NWBFile created: identifier='{nwbfile.identifier}'")

    if nwbfile.subject:
        logger.debug(f"  Subject: {nwbfile.subject.subject_id}")

    return nwbfile
