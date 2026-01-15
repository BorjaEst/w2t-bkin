"""Prefect tasks for NWB finalization (writing, validation)."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from prefect import task
from pynwb import NWBFile

from w2t_bkin.figures import (
    plot_alignment_grid,
    plot_pose_keypoints_grid,
    plot_sync_quality_and_completeness,
    plot_synchronization_stats,
    plot_trial_offsets,
    plot_ttl_inter_pulse_intervals,
    plot_ttl_timeline,
)
from w2t_bkin.models import BpodData, PoseData, TrialAlignment, TTLData
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
    name="Compute Alignment Statistics",
    description="Calculate trial-TTL alignment statistics",
    tags=["sync", "statistics"],
    retries=1,
)
def compute_alignment_stats_task(offsets: OffsetsResults, ttl_data) -> SyncStatistics:

    logger.info("Computing alignment statistics")
    pass  # TODO: implement compute_alignment_statistics_from_result


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
