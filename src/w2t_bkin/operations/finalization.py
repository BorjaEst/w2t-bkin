"""Pure functions for finalizing and writing NWB files."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pynwb import NWBFile

from w2t_bkin import utils
from w2t_bkin.core import session, validate

logger = logging.getLogger(__name__)


def write_nwb_file(nwbfile: NWBFile, output_path: Path, provenance: Optional[Dict[str, Any]] = None) -> Path:
    """Write NWB file to disk.

    Pure function that writes the NWB file and returns the path.

    Args:
        nwbfile: NWB file object to write
        output_path: Path where NWB file will be written
        provenance: Optional provenance metadata (not used in writing)

    Returns:
        Path to written NWB file

    Raises:
        IOError: If writing fails
    """
    logger.info(f"Writing NWB file to {output_path}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write NWB file
    session.write_nwb_file(nwbfile, output_path)

    # Log file size
    nwb_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"NWB file: {output_path.name} ({nwb_size_mb:.1f} MB)")

    return output_path


def create_provenance_data(config_dict: Dict[str, Any], alignment_stats: Optional[Dict[str, Any]] = None, pipeline_version: str = "v2") -> Dict[str, Any]:
    """Create provenance metadata dictionary.

    Pure function that builds provenance information.

    Args:
        config_dict: Pipeline configuration as dictionary
        alignment_stats: Optional alignment statistics
        pipeline_version: Pipeline version string

    Returns:
        Dictionary containing provenance metadata
    """
    logger.debug("Creating provenance data")

    provenance = {"pipeline": "w2t_bkin", "version": pipeline_version, "config_hash": utils.compute_hash(config_dict), "alignment_stats": alignment_stats or {}}

    logger.debug(f"Provenance keys: {list(provenance.keys())}")
    return provenance


def write_sidecar_files(output_dir: Path, alignment_stats: Optional[Dict[str, Any]] = None, provenance: Optional[Dict[str, Any]] = None) -> List[Path]:
    """Write sidecar JSON files (alignment stats, provenance).

    Pure function that writes metadata files alongside NWB file.

    Args:
        output_dir: Directory to write sidecar files
        alignment_stats: Optional alignment statistics
        provenance: Optional provenance metadata

    Returns:
        List of written file paths
    """
    logger.info("Writing sidecar files")

    output_dir.mkdir(parents=True, exist_ok=True)
    written_files = []

    # Write alignment stats
    if alignment_stats:
        stats_path = output_dir / "alignment_stats.json"
        utils.write_json(alignment_stats, stats_path)
        written_files.append(stats_path)
        logger.info(f"Alignment stats: {stats_path.name}")
    else:
        logger.debug("Skipping alignment stats sidecar (empty)")

    # Write provenance
    if provenance:
        provenance_path = output_dir / "provenance.json"
        utils.write_json(provenance, provenance_path)
        written_files.append(provenance_path)
        logger.info(f"Provenance: {provenance_path.name}")

    return written_files


def validate_nwb_file(nwb_path: Path, skip_validation: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Validate NWB file with nwbinspector.

    Pure function that runs validation and returns results.

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

    validation_results = validate.validate_nwb_file(nwb_path)

    if validation_results:
        # Count issues by severity
        critical = sum(1 for r in validation_results if r.get("severity") == "CRITICAL")
        errors = sum(1 for r in validation_results if r.get("severity") == "ERROR")
        warnings = sum(1 for r in validation_results if r.get("severity") == "WARNING")

        if critical > 0 or errors > 0:
            logger.warning(f"Validation issues: {critical} critical, {errors} errors, " f"{warnings} warnings")
            for r in validation_results:
                if r.get("severity") in ["CRITICAL", "ERROR"]:
                    logger.debug(f"  {r.get('severity')}: {r.get('message')}")
        else:
            logger.info(f"Validation passed ({warnings} warnings)")
            if warnings > 0:
                logger.debug(f"{warnings} warnings found (check validation report)")
    else:
        logger.info("Validation passed (no issues)")

    return validation_results


def finalize_session(
    nwbfile: NWBFile, output_dir: Path, session_id: str, config_dict: Dict[str, Any], alignment_stats: Optional[Dict[str, Any]] = None, skip_validation: bool = False
) -> Dict[str, Any]:
    """Finalize session by writing NWB, sidecars, and validating.

    Convenience function that orchestrates all finalization steps.

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

    # Create provenance
    provenance = create_provenance_data(config_dict=config_dict, alignment_stats=alignment_stats)

    # Write NWB file
    nwb_path = output_dir / f"{session_id}.nwb"
    write_nwb_file(nwbfile, nwb_path, provenance)

    # Write sidecars
    sidecar_paths = write_sidecar_files(output_dir=output_dir, alignment_stats=alignment_stats, provenance=provenance)

    # Validate NWB
    validation_results = validate_nwb_file(nwb_path, skip_validation)

    return {"nwb_path": nwb_path, "sidecar_paths": sidecar_paths, "validation_results": validation_results, "provenance": provenance}
