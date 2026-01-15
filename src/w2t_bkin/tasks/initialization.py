"""Prefect tasks for configuration and initialization."""

import logging
import os
from pathlib import Path

from prefect import task

from w2t_bkin.config import SessionConfig
from w2t_bkin.core.session import build_metadata_paths, load_metadata
from w2t_bkin.models import SessionInfo

logger = logging.getLogger(__name__)


@task(
    name="Setup Session",
    description="Build SessionInfo from environment variables and configuration",
    tags=["config", "initialization"],
    retries=1,
)
def setup_flow_session_task(
    subject_dir: str,
    session_dir: str,
    session_config: SessionConfig,
) -> SessionInfo:
    logger.debug(f"Building SessionInfo for {subject_dir}/{session_dir}")

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
    session_dir = raw_root / subject_dir / session_dir
    interim_dir = interim_root / subject_dir / session_dir
    output_dir = output_root / subject_dir / session_dir

    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    # Load metadata from session directory using core.session primitives
    # Support optional global metadata via W2T_ROOT_METADATA env var
    root_metadata_str = os.getenv("W2T_ROOT_METADATA")
    root_metadata = Path(root_metadata_str).resolve() if root_metadata_str else None

    # Build hierarchical metadata paths
    metadata_paths = build_metadata_paths(
        raw_root=raw_root,
        subject_dir=subject_dir,
        session_dir=session_dir,
        root_metadata=root_metadata,
    )

    if not metadata_paths:
        raise ValueError(
            f"No metadata files found for {subject_dir}/{session_dir}. "
            f"Expected at least one of: root_metadata, raw_root/metadata.toml, "
            f"raw_root/{subject_dir}/subject.toml, raw_root/{subject_dir}/{session_dir}/session.toml"
        )

    # Load and merge metadata hierarchically
    metadata = load_metadata(metadata_paths)

    logger.info(f"SessionInfo built for {subject_dir}/{session_dir}")

    return SessionInfo(
        subject_dir=subject_dir,
        session_dir=session_dir,
        metadata=metadata,
        session_dir=session_dir,
        interim_dir=interim_dir,
        output_dir=output_dir,
        models_root=models_root,
    )
