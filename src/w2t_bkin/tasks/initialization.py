"""Prefect tasks for configuration and initialization.

This module provides Prefect tasks and pure helper functions for session
initialization, including environment variable loading, metadata merging,
and directory setup.

Architecture:
    Pure functions → Prefect task wrapper

Pure Functions:
    - read_required_env_paths: Read and validate environment variables
    - build_session_paths: Compute session-specific directory paths
    - load_session_metadata: Load and merge hierarchical metadata

Prefect Tasks:
    - setup_flow_session_task: Main initialization task (orchestrates pure functions)
"""

import logging
import os
from pathlib import Path
from typing import Tuple

from prefect import task
from pydantic import ValidationError as PydanticValidationError

from w2t_bkin import utils
from w2t_bkin.config import SessionConfig
from w2t_bkin.core.session import build_metadata_paths, load_metadata
from w2t_bkin.exceptions import SessionError
from w2t_bkin.metadata import Metadata
from w2t_bkin.models import SessionInfo

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
    session_config: SessionConfig,
) -> SessionInfo:
    """Initialize session by loading metadata and setting up directories.

    This task orchestrates the initialization phase:
    1. Read and validate environment variables
    2. Compute session-specific paths
    3. Load and merge hierarchical metadata
    4. Create interim and output directories
    5. Apply logging configuration

    Args:
        subject_id: Subject identifier (e.g., 'subject-001')
        session_id: Session identifier (e.g., 'session-001')
        session_config: Pipeline configuration

    Returns:
        SessionInfo with all paths and merged metadata

    Raises:
        EnvironmentError: If required environment variables are missing
        FileNotFoundError: If raw session directory does not exist
        ValueError: If no metadata files are found
    """
    logger.debug(f"Initializing session: {subject_id}/{session_id}")

    # Read paths from environment
    raw_root, interim_root, output_root, models_root, root_metadata = read_required_env_paths()

    logger.info("Paths from environment:")
    logger.info(f"  Raw root: {raw_root}")
    logger.info(f"  Interim root: {interim_root}")
    logger.info(f"  Output root: {output_root}")
    logger.info(f"  Models root: {models_root}")
    if root_metadata:
        logger.info(f"  Root metadata: {root_metadata}")

    # Compute session-specific paths
    raw_dir, interim_dir, processed_dir = build_session_paths(
        subject_id=subject_id,
        session_id=session_id,
        raw_root=raw_root,
        interim_root=interim_root,
        output_root=output_root,
    )

    logger.debug(f"Session paths:")
    logger.debug(f"  Raw: {raw_dir}")
    logger.debug(f"  Interim: {interim_dir}")
    logger.debug(f"  Processed: {processed_dir}")

    # Load and merge metadata
    metadata = load_session_metadata(
        raw_root=raw_root,
        subject_id=subject_id,
        session_id=session_id,
        root_metadata=root_metadata,
    )

    logger.info(f"Loaded metadata from {len(build_metadata_paths(raw_root, subject_id, session_id, root_metadata))} file(s)")

    # Create interim and output directories with write permission checks
    utils.ensure_directory(interim_dir, check_writable=True)
    utils.ensure_directory(processed_dir, check_writable=True)

    logger.debug(f"Created/verified directories: {interim_dir}, {processed_dir}")

    # Apply logging configuration
    log_level = session_config.logging.level
    logging.getLogger("w2t_bkin").setLevel(getattr(logging, log_level))
    logger.info(f"Applied logging level: {log_level}")

    logger.info(f"SessionInfo initialized for {subject_id}/{session_id}")

    return SessionInfo(
        subject_id=subject_id,
        session_id=session_id,
        metadata=metadata,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
        models_dir=models_root,
    )


def read_required_env_paths() -> Tuple[Path, Path, Path, Path, Path | None]:
    """Read and validate required environment variables for data paths.

    Returns:
        Tuple of (raw_root, interim_root, output_root, models_root, root_metadata)

    Raises:
        EnvironmentError: If required environment variables are missing
    """
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

    # Optional global metadata
    root_metadata_str = os.getenv("W2T_ROOT_METADATA")

    # Convert to absolute paths
    raw_root = Path(raw_root_str).resolve()
    interim_root = Path(interim_root_str).resolve()
    output_root = Path(output_root_str).resolve()
    models_root = Path(models_root_str).resolve()
    root_metadata = Path(root_metadata_str).resolve() if root_metadata_str else None

    return raw_root, interim_root, output_root, models_root, root_metadata


def build_session_paths(
    subject_id: str,
    session_id: str,
    raw_root: Path,
    interim_root: Path,
    output_root: Path,
) -> Tuple[Path, Path, Path]:
    """Compute session-specific directory paths.

    Args:
        subject_id: Subject identifier
        session_id: Session identifier
        raw_root: Raw data root directory
        interim_root: Interim data root directory
        output_root: Output data root directory

    Returns:
        Tuple of (raw_dir, interim_dir, processed_dir)

    Raises:
        FileNotFoundError: If raw session directory does not exist
    """
    raw_dir = raw_root / subject_id / session_id
    interim_dir = interim_root / subject_id / session_id
    processed_dir = output_root / subject_id / session_id

    if not raw_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {raw_dir}")

    return raw_dir, interim_dir, processed_dir


def load_session_metadata(
    raw_root: Path,
    subject_id: str,
    session_id: str,
    root_metadata: Path | None = None,
) -> Metadata:
    """Load and merge hierarchical session metadata.

    Args:
        raw_root: Raw data root directory
        subject_id: Subject identifier
        session_id: Session identifier
        root_metadata: Optional global metadata file path

    Returns:
        Merged metadata dictionary

    Raises:
        ValueError: If no metadata files are found
    """
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
    merged = load_metadata(metadata_paths)

    # Strict schema validation (fail fast on unknown keys)
    try:
        return Metadata.model_validate(merged)
    except PydanticValidationError as e:
        raise SessionError(
            "Invalid metadata.toml (schema validation failed)",
            context={
                "subject_id": subject_id,
                "session_id": session_id,
                "metadata_paths": [str(p) for p in metadata_paths],
                "validation_errors": e.errors(),
            },
            hint="Fix unknown/invalid keys in metadata TOML files (strict schema validation is enabled).",
        )
