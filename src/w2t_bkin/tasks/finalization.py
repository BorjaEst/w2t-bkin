"""Prefect tasks for NWB finalization (writing, validation)."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from prefect import task
from pynwb import NWBFile

from w2t_bkin.operations import create_provenance_data, finalize_session, validate_nwb_file, write_nwb_file, write_sidecar_files

logger = logging.getLogger(__name__)


@task(
    name="Write NWB File",
    description="Write NWB file to disk",
    tags=["finalization", "nwb", "io"],
    retries=2,
    retry_delay_seconds=10,
    timeout_seconds=600,  # 10 minute timeout for large files
)
def write_nwb_task(nwbfile: NWBFile, output_path: Path, provenance: Optional[Dict[str, Any]] = None) -> Path:
    """Write NWB file to disk.

    Prefect task wrapper for write_nwb_file operation.

    Args:
        nwbfile: NWB file object to write
        output_path: Path where NWB file will be written
        provenance: Optional provenance metadata

    Returns:
        Path to written NWB file

    Raises:
        IOError: If writing fails
    """
    logger.info(f"Writing NWB file to {output_path}")

    return write_nwb_file(nwbfile=nwbfile, output_path=output_path, provenance=provenance)


@task(
    name="Write Sidecar Files",
    description="Write JSON sidecar files (alignment stats, provenance)",
    tags=["finalization", "io"],
    retries=2,
    retry_delay_seconds=5,
)
def write_sidecars_task(output_dir: Path, alignment_stats: Optional[Dict[str, Any]] = None, provenance: Optional[Dict[str, Any]] = None) -> List[Path]:
    """Write sidecar JSON files alongside NWB file.

    Prefect task wrapper for write_sidecar_files operation.

    Args:
        output_dir: Directory to write sidecar files
        alignment_stats: Optional alignment statistics
        provenance: Optional provenance metadata

    Returns:
        List of written file paths
    """
    logger.info("Writing sidecar files")

    return write_sidecar_files(output_dir=output_dir, alignment_stats=alignment_stats, provenance=provenance)


@task(
    name="Validate NWB File",
    description="Validate NWB file with nwbinspector",
    tags=["finalization", "validation"],
    retries=1,
    timeout_seconds=300,  # 5 minute timeout
)
def validate_nwb_task(nwb_path: Path, skip_validation: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Validate NWB file with nwbinspector.

    Prefect task wrapper for validate_nwb_file operation.

    Args:
        nwb_path: Path to NWB file to validate
        skip_validation: If True, skip validation and return None

    Returns:
        List of validation issue dictionaries, or None if skipped/passed
    """
    if skip_validation:
        logger.info("Skipping NWB validation (requested)")
        return None

    logger.info("Validating NWB file with nwbinspector")

    return validate_nwb_file(nwb_path=nwb_path, skip_validation=skip_validation)


@task(
    name="Create Provenance Data",
    description="Create provenance metadata dictionary",
    tags=["finalization", "metadata"],
    retries=1,
)
def create_provenance_task(config_dict: Dict[str, Any], alignment_stats: Optional[Dict[str, Any]] = None, pipeline_version: str = "v2") -> Dict[str, Any]:
    """Create provenance metadata dictionary.

    Prefect task wrapper for create_provenance_data operation.

    Args:
        config_dict: Pipeline configuration as dictionary
        alignment_stats: Optional alignment statistics
        pipeline_version: Pipeline version string

    Returns:
        Dictionary containing provenance metadata
    """
    logger.debug("Creating provenance data")

    return create_provenance_data(config_dict=config_dict, alignment_stats=alignment_stats, pipeline_version=pipeline_version)


@task(
    name="Finalize Session",
    description="Complete session finalization (write, sidecars, validate)",
    tags=["finalization", "orchestration"],
    retries=1,
    timeout_seconds=900,  # 15 minute timeout
)
def finalize_session_task(
    nwbfile: NWBFile, output_dir: Path, session_id: str, config_dict: Dict[str, Any], alignment_stats: Optional[Dict[str, Any]] = None, skip_validation: bool = False
) -> Dict[str, Any]:
    """Finalize session by writing NWB, sidecars, and validating.

    Prefect task wrapper for finalize_session operation.
    Convenience task that orchestrates all finalization steps.

    Args:
        nwbfile: NWB file object to write
        output_dir: Directory for output files
        session_id: Session identifier
        config_dict: Pipeline configuration dictionary
        alignment_stats: Optional alignment statistics
        skip_validation: Skip NWB validation if True

    Returns:
        Dictionary containing:
        - nwb_path: Path to written NWB file
        - sidecar_paths: List of sidecar file paths
        - validation_results: Validation results or None
        - provenance: Provenance metadata
    """
    logger.info(f"Finalizing session {session_id}")

    return finalize_session(
        nwbfile=nwbfile, output_dir=output_dir, session_id=session_id, config_dict=config_dict, alignment_stats=alignment_stats, skip_validation=skip_validation
    )
