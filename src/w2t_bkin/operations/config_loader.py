"""Pure functions for loading and creating session configuration."""

import logging
from pathlib import Path
from typing import Optional

from pynwb import NWBFile

from w2t_bkin import config as config_pkg
from w2t_bkin import utils
from w2t_bkin.models import SessionConfig

logger = logging.getLogger(__name__)


def load_session_config(
    base_config_path: Optional[Path] = None,
    project_config_path: Optional[Path] = None,
    subject_id: str = ...,
    session_id: str = ...,
) -> SessionConfig:
    """Load complete session configuration using 2-layer config hierarchy.

    This is a pure function that loads all configuration and metadata
    without any side effects. Returns an immutable SessionConfig object.

    The configuration system uses a 2-layer hierarchy:
    - Base: Package defaults (if not provided, uses built-in standard.toml)
    - Project: User/experiment settings (optional, from 'w2t-bkin data init')

    Runtime overrides are handled via flow parameters rather than a third config file.

    Args:
        base_config_path: Base configuration file (package defaults, optional).
                         If None, uses built-in configs/standard.toml.
        project_config_path: Project-specific configuration (optional).
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")

    Returns:
        Immutable SessionConfig with all paths and settings

    Raises:
        FileNotFoundError: If config or metadata files not found
        ValueError: If configuration is invalid
    """
    logger.debug("Loading configuration hierarchy")

    # Get package root for default base config
    if base_config_path is None:
        package_root = Path(__file__).parent.parent.parent.absolute()
        base_config_path = package_root / "configs" / "standard.toml"
        logger.debug(f"Using default base config: {base_config_path}")

    # Load hierarchical configuration (2 layers)
    # If W2T_RUNTIME_CONFIG_JSON is set, use it (baked config)
    # Otherwise, fall back to file loading (legacy/local dev)
    import json
    import os

    config_json = os.getenv("W2T_RUNTIME_CONFIG_JSON")
    if config_json:
        logger.info("Loading configuration from environment (baked deployment config)")
        config_dict = json.loads(config_json)
        config = config_pkg.load_config_from_dict(config_dict)
    else:
        logger.info("Loading configuration from files (legacy/local mode)")
        config = config_pkg.load_config_hierarchy(
            base_config=base_config_path,
            project_config=project_config_path,
            runtime_config=None,  # Not used in 2-layer system
        )

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

    # Store the effective config path for tracking (use base as primary reference)
    effective_config_path = base_config_path

    return SessionConfig(
        config_path=effective_config_path,
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
