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


def _build_data_streams(
    bpod_data: Optional[BpodData],
    ttl_data: Optional[Dict[str, TTLData]],
    pose_data: Optional[Dict[str, List[PoseData]]],
    trial_alignment: Optional[TrialAlignment],
) -> Optional[Dict[str, List[bool]]]:
    """Build per-trial data availability dictionary.

    Args:
        bpod_data: Bpod behavioral data
        ttl_data: TTL pulse data by channel
        pose_data: Pose estimation data by camera
        trial_alignment: Trial alignment result

    Returns:
        Dict mapping stream names to per-trial boolean availability
        Example: {"Bpod": [True, True, ...], "ttl_camera": [True, False, ...]}
        Returns None if no data available to track
    """
    if not bpod_data:
        return None

    n_trials = bpod_data.n_trials
    data_streams = {}

    # Bpod availability: trial has alignment offset
    if trial_alignment:
        bpod_available = [(i + 1) in trial_alignment.trial_offsets for i in range(n_trials)]
        data_streams["Bpod"] = bpod_available

    # TTL availability by channel
    # For now, mark all trials as available if TTL data exists
    # Could be enhanced to check per-trial pulse presence
    if ttl_data:
        for ttl_id in ttl_data.keys():
            data_streams[ttl_id] = [True] * n_trials

    # Pose availability by camera
    # Check if pose data exists for each trial (assuming sequential mapping)
    if pose_data:
        for camera_id, poses in pose_data.items():
            # Mark trials as having pose data if corresponding video was processed
            data_streams[f"pose_{camera_id}"] = [i < len(poses) for i in range(n_trials)]

    return data_streams if data_streams else None


@task(
    name="Generate Figures",
    description="Generate diagnostic figures for the session",
    tags=["figures", "visualization"],
    retries=0,
)
def generate_figures_task(
    output_dir: Path,
    alignment_stats: Optional[Dict[str, Any]] = None,
    trial_alignment: Optional[TrialAlignment] = None,
    bpod_data: Optional[BpodData] = None,
    ttl_data: Optional[Dict[str, TTLData]] = None,
    pose_data: Optional[Dict[str, List[PoseData]]] = None,
) -> List[Path]:
    """Generate diagnostic figures for the session.

    Args:
        output_dir: Directory to save figures
        alignment_stats: Alignment statistics dictionary
        trial_alignment: Trial alignment result
        bpod_data: Bpod behavioral data
        ttl_data: TTL pulse data
        pose_data: Pose estimation data

    Returns:
        List of generated figure paths
    """
    # Configure matplotlib for non-interactive backend (worker scope)
    from w2t_bkin.figures import configure_matplotlib_backend

    configure_matplotlib_backend("Agg")

    logger.info("Generating diagnostic figures")

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    # 1. Synchronization Stats
    if alignment_stats:
        try:
            path = plot_synchronization_stats(alignment_stats, figures_dir / "synchronization_stats.png")
            if path:
                generated_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to plot synchronization stats: {e}")

    # 3. TTL Timeline
    if ttl_data:
        try:
            # Convert TTLData objects to dict of timestamps
            ttl_pulses = {k: v.timestamps for k, v in ttl_data.items()}
            path = plot_ttl_timeline(ttl_pulses=ttl_pulses, out_path=figures_dir / "ttl_timeline.png")
            if path:
                generated_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to plot TTL timeline: {e}")

        # TTL Inter-pulse intervals
        try:
            # Convert TTLData objects to dict of timestamps
            ttl_pulses = {k: v.timestamps for k, v in ttl_data.items()}
            # TODO: Extract expected_fps from camera config for better diagnostics
            path = plot_ttl_inter_pulse_intervals(ttl_pulses, None, figures_dir / "ttl_inter_pulse_intervals.png")
            if path:
                generated_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to plot TTL inter-pulse intervals: {e}")

    # 4. Trial Offsets
    if trial_alignment:
        try:
            path = plot_trial_offsets(trial_alignment.trial_offsets, out_path=figures_dir / "trial_offsets.png")
            if path:
                generated_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to plot trial offsets: {e}")

    # 5. Alignment Grid/Example
    if trial_alignment and bpod_data and ttl_data:
        try:
            ttl_pulses = {k: v.timestamps for k, v in ttl_data.items()}
            # Note: plot_alignment_grid requires trials_info list which is complex to build here.
            # Skipping for now to avoid complexity, relying on sync_quality_and_completeness
            pass
        except Exception as e:
            logger.warning(f"Failed to plot alignment grid: {e}")

    # 6. Sync Quality and Completeness
    if trial_alignment and bpod_data:
        try:
            # Build per-trial data availability tracking
            data_streams = _build_data_streams(bpod_data, ttl_data, pose_data, trial_alignment)
            path = plot_sync_quality_and_completeness(
                trial_alignment.trial_offsets,
                data_streams,
                figures_dir / "sync_quality_and_completeness.png",
                csv_output_dir=figures_dir,
            )
            if path:
                generated_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to plot sync quality: {e}")

    # 7. Pose Keypoints
    if pose_data:
        for camera_id, poses in pose_data.items():
            for i, pose in enumerate(poses):
                try:
                    # Assuming pose is PoseData
                    path = plot_pose_keypoints_grid(bundle=pose, video_path=pose.video_path, out_path=figures_dir / f"pose_keypoints_{camera_id}_{i}.png")
                    if path:
                        generated_files.append(path)
                except Exception as e:
                    logger.warning(f"Failed to plot pose keypoints for {camera_id}: {e}")

    return generated_files
