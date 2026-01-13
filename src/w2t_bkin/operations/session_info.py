"""Pure functions for loading and creating session configuration."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pynwb import NWBFile

from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.core.session import build_metadata_paths
from w2t_bkin.core.session import create_nwb_file as core_create_nwb_file
from w2t_bkin.core.session import load_metadata
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

    # Load metadata from session directory using core.session primitives
    # Support optional global metadata via W2T_ROOT_METADATA env var
    root_metadata_str = os.getenv("W2T_ROOT_METADATA")
    root_metadata = Path(root_metadata_str).resolve() if root_metadata_str else None

    # Build hierarchical metadata paths
    metadata_paths = build_metadata_paths(
        raw_root=raw_root,
        subject_id=subject_id,
        session_id=session_id,
        root_metadata=root_metadata,
    )

    if not metadata_paths:
        raise ValueError(
            f"No metadata files found for {subject_id}/{session_id}. "
            f"Expected at least one of: root_metadata, raw_root/metadata.toml, "
            f"raw_root/{subject_id}/subject.toml, raw_root/{subject_id}/{session_id}/session.toml"
        )

    # Load and merge metadata hierarchically
    metadata = load_metadata(metadata_paths)

    logger.info(f"SessionInfo built for {subject_id}/{session_id}")

    return SessionInfo(
        subject_id=subject_id,
        session_id=session_id,
        config=session_config,
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

    # Create NWBFile directly from metadata using core.session primitive
    nwbfile = core_create_nwb_file(session_info.metadata)

    logger.info(f"NWBFile created: identifier='{nwbfile.identifier}'")

    if nwbfile.subject:
        logger.debug(f"  Subject: {nwbfile.subject.subject_id}")

    return nwbfile
