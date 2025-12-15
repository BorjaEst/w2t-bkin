"""Pure functions for loading and creating session configuration."""

import logging
from pathlib import Path

from pynwb import NWBFile

from w2t_bkin import config as config_pkg
from w2t_bkin import utils
from w2t_bkin.models import SessionConfig

logger = logging.getLogger(__name__)


def load_session_config(config_path: Path, subject_id: str, session_id: str) -> SessionConfig:
    """Load complete session configuration.

    This is a pure function that loads all configuration and metadata
    without any side effects. Returns an immutable SessionConfig object.

    Args:
        config_path: Path to configuration TOML file
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")

    Returns:
        Immutable SessionConfig with all paths and settings

    Raises:
        FileNotFoundError: If config or metadata files not found
        ValueError: If configuration is invalid
    """
    logger.debug(f"Loading configuration from {config_path}")

    # Load configuration (paths auto-resolved by Pydantic validators)
    config = config_pkg.load_config(config_path)

    logger.info(f"Configuration loaded: {config.project.name}")
    logger.debug(f"  Raw root: {config.paths.raw_root}")
    logger.debug(f"  Interim root: {config.paths.intermediate_root}")
    logger.debug(f"  Output root: {config.paths.output_root}")

    # Determine session directory
    session_dir = config.paths.raw_root / subject_id / session_id

    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    # Load metadata using existing utility
    # This calls load_session_metadata_and_nwb but we'll only keep metadata part
    metadata, _ = utils.load_session_metadata_and_nwb(config=config, subject_id=subject_id, session_id=session_id)

    # Compute derived paths
    interim_dir = config.paths.intermediate_root / subject_id / session_id
    output_dir = config.paths.output_root / subject_id / session_id

    return SessionConfig(
        config_path=config_path,
        subject_id=subject_id,
        session_id=session_id,
        config=config,
        metadata=metadata,
        session_dir=session_dir,
        interim_dir=interim_dir,
        output_dir=output_dir,
    )


def create_nwb_file(session_config: SessionConfig) -> NWBFile:
    """Create NWBFile from session configuration.

    Pure function that creates an in-memory NWBFile object.

    Args:
        session_config: Session configuration

    Returns:
        In-memory NWBFile object (not yet written to disk)
    """
    logger.debug(f"Creating NWBFile for {session_config.subject_id}/{session_config.session_id}")

    # Use existing utility to create NWBFile
    _, nwbfile = utils.load_session_metadata_and_nwb(config=session_config.config, subject_id=session_config.subject_id, session_id=session_config.session_id)

    logger.info(f"NWBFile created: identifier='{nwbfile.identifier}'")

    if nwbfile.subject:
        logger.debug(f"  Subject: {nwbfile.subject.subject_id}")

    return nwbfile
