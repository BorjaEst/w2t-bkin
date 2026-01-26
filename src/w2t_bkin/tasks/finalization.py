"""Prefect tasks for NWB finalization (writing, validation)."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from prefect import get_run_logger, task
from pynwb import NWBFile

from w2t_bkin.config import FinalizationConfig, SessionConfig
from w2t_bkin.figures import plot_synchronization_stats, plot_trial_offsets, plot_ttl_inter_pulse_intervals, plot_ttl_timeline
from w2t_bkin.models import SessionInfo, TTLData
from w2t_bkin.operations.finalization import create_provenance_data, validate_nwb_file, write_nwb_file
from w2t_bkin.utils import write_json

logger = logging.getLogger(__name__)


@dataclass
class WriteNWBFileResult:
    """Result of writing NWB file to disk.

    Attributes:
        nwb_path: Path to the written NWB file
        sidecar_paths: Optional list of sidecar file paths (e.g., provenance.json)
    """

    nwb_path: Path
    sidecar_paths: Optional[List[Path]] = None


@task(
    name="Write NWB File",
    description="Write NWB file to disk with session context",
    tags=["finalization", "nwb", "io"],
    retries=2,
    retry_delay_seconds=10,
    timeout_seconds=600,
)
def write_nwb_file_task(
    nwbfile: NWBFile,
    info: SessionInfo,
    finalization_config: FinalizationConfig,
) -> WriteNWBFileResult:
    """Write NWB file to disk using session info.

    Args:
        nwbfile: NWB file object to write
        info: Session information with output paths
        finalization_config: Finalization configuration

    Returns:
        WriteNWBFileResult with nwb_path

    Raises:
        IOError: If writing fails
    """
    run_logger = get_run_logger()

    # Compute output path from session info
    output_path = info.processed_dir / f"{info.session_id}.nwb"

    run_logger.info(f"Writing NWB file to {output_path}")

    # Write NWB file using operations primitive
    written_path = write_nwb_file(nwbfile=nwbfile, output_path=output_path, provenance=None)

    run_logger.info(f"NWB file written: {written_path.name}")

    return WriteNWBFileResult(nwb_path=written_path)


@task(
    name="Compute Alignment Statistics",
    description="Calculate trial-TTL alignment quality metrics for QC",
    tags=["sync", "statistics", "qc"],
    retries=1,
)
def compute_alignment_stats_task(
    offsets: Dict[int, float],
    ttl_data: Dict[str, TTLData],
    offset_labels: Optional[Dict[str, str]] = None,
    robust_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute alignment quality statistics from trial offsets.

    Builds the nested structure expected by QC plotting functions.

    Args:
        offsets: Dict mapping trial_number → absolute time offset (seconds)
        ttl_data: Dict mapping ttl_id → TTLData with pulse timestamps

    Returns:
        Dict with structure:
            - trial_offsets: {trial_num: offset_s, ...}
            - ttl_channels: {ttl_id: pulse_count, ...}
            - statistics: {n_trials_aligned, offset_mean_s, offset_std_s, ...}
            - offset_labels: Optional label map for matched/interpolated trials
            - robust_stats: Optional robust alignment summary
    """
    run_logger = get_run_logger()
    run_logger.info("Computing alignment statistics for QC")

    if not offsets:
        run_logger.warning("No trial offsets available for statistics")
        return {
            "trial_offsets": {},
            "ttl_channels": {ttl_id: ttl.pulse_count for ttl_id, ttl in ttl_data.items()} if ttl_data else {},
            "statistics": {
                "n_trials_aligned": 0,
                "offset_mean_s": 0.0,
                "offset_std_s": 0.0,
                "offset_min_s": 0.0,
                "offset_max_s": 0.0,
            },
            "offset_labels": offset_labels or {},
            "robust_stats": robust_stats or {},
        }

    # Compute offset statistics
    offsets_array = np.array(list(offsets.values()))
    mean_offset = float(np.mean(offsets_array))
    std_offset = float(np.std(offsets_array))

    # Compute jitter metrics (deviation from mean)
    jitter = np.abs(offsets_array - mean_offset)
    max_jitter = float(np.max(jitter))
    p95_jitter = float(np.percentile(jitter, 95))

    statistics = {
        "n_trials_aligned": len(offsets),
        "offset_mean_s": mean_offset,
        "offset_std_s": std_offset,
        "offset_min_s": float(np.min(offsets_array)),
        "offset_max_s": float(np.max(offsets_array)),
        "max_jitter_s": max_jitter,
        "p95_jitter_s": p95_jitter,
    }

    result = {
        "trial_offsets": offsets,
        "ttl_channels": {ttl_id: ttl.pulse_count for ttl_id, ttl in ttl_data.items()} if ttl_data else {},
        "statistics": statistics,
        "offset_labels": offset_labels or {},
        "robust_stats": robust_stats or {},
    }

    run_logger.info(f"Alignment stats: {statistics['n_trials_aligned']} trials, " f"offset={statistics['offset_mean_s']:.4f}±{statistics['offset_std_s']:.4f}s")

    return result


@task(
    name="Create Provenance Data",
    description="Create and persist provenance metadata to JSON",
    tags=["finalization", "metadata", "provenance"],
    retries=1,
)
def create_provenance_data_task(
    info: SessionInfo,
    data: Dict[str, Any],
    config: SessionConfig,
) -> Dict[str, Any]:
    """Create provenance metadata and write to provenance.json.

    Args:
        info: Session information with paths
        data: Ingestion results (for manifest counts)
        config: Pipeline configuration

    Returns:
        Dictionary containing provenance metadata
    """
    run_logger = get_run_logger()
    run_logger.info("Creating provenance metadata")

    # Convert config to dict
    config_dict = config.model_dump()

    # Build lightweight data manifest
    manifest = {
        "n_ttl_channels": len(data.get("ttl", {})),
        "n_cameras": len(data.get("video", {})),
        "bpod_present": data.get("bpod") is not None,
        "pose_present": data.get("pose") is not None,
    }

    # Create provenance data (without alignment stats for now)
    provenance = create_provenance_data(
        config_dict=config_dict,
        alignment_stats=None,
        pipeline_version="v2",
    )

    # Add manifest
    provenance["manifest"] = manifest

    # Write to provenance.json
    provenance_path = info.processed_dir / "provenance.json"
    write_json(provenance, provenance_path)
    run_logger.info(f"Provenance written to {provenance_path.name}")

    return provenance


@task(
    name="Validate NWB File",
    description="Validate NWB file with nwbinspector",
    tags=["finalization", "validation"],
    retries=1,
    timeout_seconds=300,
)
def validate_nwb_file_task(
    nwb_path: Path,
    skip_validation: bool = False,
) -> Optional[List[Dict[str, Any]]]:
    """Validate NWB file with nwbinspector.

    Args:
        nwb_path: Path to NWB file to validate
        skip_validation: If True, skip validation and return None

    Returns:
        List of validation issue dictionaries, or None if skipped/passed
    """
    run_logger = get_run_logger()

    if skip_validation:
        run_logger.info("Skipping NWB validation (requested)")
        return None

    run_logger.info("Validating NWB file with nwbinspector")

    return validate_nwb_file(nwb_path=nwb_path, skip_validation=skip_validation)


@task(
    name="Write QC Report",
    description="Generate QC figures and diagnostic plots",
    tags=["finalization", "qc", "figures"],
    retries=1,
    timeout_seconds=300,
)
def write_qc_report_task(
    info: SessionInfo,
    data: Dict[str, Any],
    offsets: Dict[int, float],
) -> Dict[str, Any]:
    """Generate QC figures for the session.

    Creates diagnostic plots under processed_dir/figures/:
    - TTL timeline
    - Trial offsets
    - Synchronization stats
    - TTL inter-pulse intervals

    Args:
        info: Session information with paths
        data: Ingestion results (ttl, video, bpod, pose)
        offsets: Trial offsets from synchronization

    Returns:
        Dict with:
            - figures: List of generated figure paths
            - skipped: Dict of skipped figures with reasons
    """
    run_logger = get_run_logger()
    run_logger.info("Generating QC figures")

    figures_dir = info.processed_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    generated_figures = []
    skipped = {}

    # Get TTL data
    ttl_data = data.get("ttl", {})

    # 1. TTL Timeline
    if ttl_data:
        try:
            ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}
            timeline_path = plot_ttl_timeline(
                ttl_pulses=ttl_pulses,
                channel_order=None,
                out_path=figures_dir / "ttl_timeline.png",
            )
            if timeline_path:
                generated_figures.append(timeline_path)
                run_logger.debug(f"Generated TTL timeline: {timeline_path.name}")
        except Exception as e:
            skipped["ttl_timeline"] = f"Error: {e}"
            run_logger.warning(f"Failed to generate TTL timeline: {e}")
    else:
        skipped["ttl_timeline"] = "No TTL data available"

    # 2. Trial Offsets
    if offsets:
        try:
            offsets_path = plot_trial_offsets(
                trial_offsets=offsets,
                out_path=figures_dir / "trial_offsets.png",
            )
            if offsets_path:
                generated_figures.append(offsets_path)
                run_logger.debug(f"Generated trial offsets: {offsets_path.name}")
        except Exception as e:
            skipped["trial_offsets"] = f"Error: {e}"
            run_logger.warning(f"Failed to generate trial offsets: {e}")
    else:
        skipped["trial_offsets"] = "No trial offsets available"

    # 3. Synchronization Stats (requires alignment_stats structure)
    if offsets and ttl_data:
        try:
            # Compute alignment stats for plotting
            from w2t_bkin.tasks.finalization import compute_alignment_stats_task

            sync_stats = data.get("sync_stats") or {}
            offset_labels = sync_stats.get("offset_labels") if sync_stats else None
            alignment_stats = compute_alignment_stats_task.fn(
                offsets,
                ttl_data,
                offset_labels=offset_labels,
                robust_stats=sync_stats,
            )

            sync_path = plot_synchronization_stats(
                alignment_stats=alignment_stats,
                save_path=figures_dir / "synchronization_stats.png",
            )
            if sync_path:
                generated_figures.append(sync_path)
                run_logger.debug(f"Generated synchronization stats: {sync_path.name}")
        except Exception as e:
            skipped["synchronization_stats"] = f"Error: {e}"
            run_logger.warning(f"Failed to generate synchronization stats: {e}")
    else:
        skipped["synchronization_stats"] = "Missing offsets or TTL data"

    # 4. TTL Inter-Pulse Intervals
    if ttl_data:
        try:
            # Infer expected FPS from metadata
            expected_fps = {}
            for camera in info.metadata.cameras:
                ttl_id = camera.ttl_id
                fps = camera.fps
                if ttl_id and fps:
                    expected_fps[ttl_id] = fps

            ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}
            ipi_path = plot_ttl_inter_pulse_intervals(
                ttl_pulses=ttl_pulses,
                expected_fps=expected_fps if expected_fps else None,
                save_path=figures_dir / "ttl_inter_pulse_intervals.png",
            )
            if ipi_path:
                generated_figures.append(ipi_path)
                run_logger.debug(f"Generated TTL IPI: {ipi_path.name}")
        except Exception as e:
            skipped["ttl_ipi"] = f"Error: {e}"
            run_logger.warning(f"Failed to generate TTL IPI: {e}")
    else:
        skipped["ttl_ipi"] = "No TTL data available"

    run_logger.info(f"QC report: {len(generated_figures)} figures generated, {len(skipped)} skipped")

    return {
        "figures": generated_figures,
        "skipped": skipped,
    }
