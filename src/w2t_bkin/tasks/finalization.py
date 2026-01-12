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
    nwb_path: Optional[Path] = None,
    pipeline_profile_path: Optional[Path] = None,
) -> List[Path]:
    """Generate diagnostic figures for the session.

    Args:
        output_dir: Directory to save figures
        alignment_stats: Alignment statistics dictionary
        trial_alignment: Trial alignment result
        bpod_data: Bpod behavioral data
        ttl_data: TTL pulse data
        pose_data: Pose estimation data
        nwb_path: Optional path to NWB file for ecephys plots
        pipeline_profile_path: Optional path to pipeline_profile.json for execution plot

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
    skip_reasons = []
    attempted_count = 0
    failed_count = 0

    # Helper to validate generated file
    def _validate_figure(path: Optional[Path], name: str) -> bool:
        """Validate that figure was generated successfully."""
        if path is None:
            return False
        if not path.exists():
            logger.warning(f"WARN {name}: returned path but file does not exist: {path}")
            return False
        if path.stat().st_size == 0:
            logger.warning(f"WARN {name}: generated file is empty: {path}")
            return False
        logger.info(f"OK {name}: {path.name} ({path.stat().st_size} bytes)")
        return True

    # ========================================================================
    # 0. Pipeline Execution Profile
    # ========================================================================
    figure_name = "pipeline_execution"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if pipeline_profile_path is None or not pipeline_profile_path.exists():
        reason = f"{figure_name}: pipeline_profile.json not available"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        try:
            from w2t_bkin.figures import PipelineProfile, plot_pipeline_execution
            from w2t_bkin.utils import read_json

            profile_data = read_json(pipeline_profile_path)
            # Reconstruct PipelineProfile from JSON
            from w2t_bkin.figures.profiling import PhaseProfile

            phases = [
                PhaseProfile(
                    phase_id=p["phase_id"],
                    phase_name=p["phase_name"],
                    start_time=p["start_time"],
                    end_time=p["end_time"],
                    duration=p["duration"],
                    success=p["success"],
                    error_message=p.get("error_message"),
                )
                for p in profile_data.get("phases", [])
            ]
            profile = PipelineProfile(
                subject_id=profile_data.get("subject_id", "unknown"),
                session_id=profile_data.get("session_id", "unknown"),
                total_duration=profile_data.get("total_duration", 0.0),
                phases=phases,
            )

            logger.info(f"  profile: {len(phases)} phases, {profile.total_duration:.1f}s total")
            path = plot_pipeline_execution(profile, figures_dir / "pipeline_execution.png")
            if _validate_figure(path, figure_name):
                generated_files.append(path)
            else:
                reason = f"{figure_name}: returned None"
                logger.info(f"SKIP {reason}")
                skip_reasons.append(reason)
        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 1. Synchronization Stats
    # ========================================================================
    figure_name = "synchronization_stats"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if alignment_stats is None:
        reason = f"{figure_name}: alignment_stats is None"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    elif not isinstance(alignment_stats, dict):
        reason = f"{figure_name}: alignment_stats is not a dict (type={type(alignment_stats).__name__})"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        # Log input details
        stats_keys = list(alignment_stats.keys())
        trial_offsets_count = len(alignment_stats.get("trial_offsets", {}))
        ttl_channels_count = len(alignment_stats.get("ttl_channels", {}))
        logger.info(f"  alignment_stats keys: {stats_keys}")
        logger.info(f"  trial_offsets: {trial_offsets_count}, ttl_channels: {ttl_channels_count}")

        if not alignment_stats.get("trial_offsets") and not alignment_stats.get("ttl_channels"):
            reason = f"{figure_name}: alignment_stats has no trial_offsets or ttl_channels"
            logger.info(f"SKIP {reason}")
            skip_reasons.append(reason)
        else:
            try:
                path = plot_synchronization_stats(alignment_stats, figures_dir / "synchronization_stats.png")
                if _validate_figure(path, figure_name):
                    generated_files.append(path)
                else:
                    reason = f"{figure_name}: returned None"
                    logger.info(f"SKIP {reason}")
                    skip_reasons.append(reason)
            except Exception as e:
                failed_count += 1
                logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 2. TTL Timeline
    # ========================================================================
    figure_name = "ttl_timeline"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if ttl_data is None or len(ttl_data) == 0:
        reason = f"{figure_name}: ttl_data is None or empty"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        # Log input details
        ttl_channels = list(ttl_data.keys())
        pulse_counts = {k: len(v.timestamps) for k, v in ttl_data.items()}
        logger.info(f"  ttl_channels: {ttl_channels}")
        logger.info(f"  pulse_counts: {pulse_counts}")

        try:
            ttl_pulses = {k: v.timestamps for k, v in ttl_data.items()}
            path = plot_ttl_timeline(ttl_pulses=ttl_pulses, out_path=figures_dir / "ttl_timeline.png")
            if _validate_figure(path, figure_name):
                generated_files.append(path)
            else:
                reason = f"{figure_name}: returned None"
                logger.info(f"SKIP {reason}")
                skip_reasons.append(reason)
        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 3. TTL Inter-pulse Intervals
    # ========================================================================
    figure_name = "ttl_inter_pulse_intervals"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if ttl_data is None or len(ttl_data) == 0:
        reason = f"{figure_name}: ttl_data is None or empty"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        logger.info(f"  ttl_channels: {list(ttl_data.keys())}")
        try:
            ttl_pulses = {k: v.timestamps for k, v in ttl_data.items()}
            # TODO: Extract expected_fps from camera config for better diagnostics
            path = plot_ttl_inter_pulse_intervals(ttl_pulses, None, figures_dir / "ttl_inter_pulse_intervals.png")
            if _validate_figure(path, figure_name):
                generated_files.append(path)
            else:
                reason = f"{figure_name}: returned None"
                logger.info(f"SKIP {reason}")
                skip_reasons.append(reason)
        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 4. Trial Offsets
    # ========================================================================
    figure_name = "trial_offsets"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if trial_alignment is None:
        reason = f"{figure_name}: trial_alignment is None"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    elif not hasattr(trial_alignment, "trial_offsets") or not trial_alignment.trial_offsets:
        reason = f"{figure_name}: trial_alignment has no trial_offsets"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        # Log input details
        n_offsets = len(trial_alignment.trial_offsets)
        logger.info(f"  trial_offsets: {n_offsets} trials")

        try:
            path = plot_trial_offsets(trial_alignment.trial_offsets, out_path=figures_dir / "trial_offsets.png")
            if _validate_figure(path, figure_name):
                generated_files.append(path)
            else:
                reason = f"{figure_name}: returned None"
                logger.info(f"SKIP {reason}")
                skip_reasons.append(reason)
        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 5. Alignment Grid (Not Implemented)
    # ========================================================================
    figure_name = "alignment_grid"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")
    reason = f"{figure_name}: not implemented (requires complex trials_info construction)"
    logger.info(f"SKIP {reason}")
    skip_reasons.append(reason)

    # ========================================================================
    # 6. Sync Quality and Completeness
    # ========================================================================
    figure_name = "sync_quality_and_completeness"
    attempted_count += 1
    logger.info(f"Attempting {figure_name}")

    if trial_alignment is None:
        reason = f"{figure_name}: trial_alignment is None"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    elif not hasattr(trial_alignment, "trial_offsets") or not trial_alignment.trial_offsets:
        reason = f"{figure_name}: trial_alignment has no trial_offsets"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    elif len(trial_alignment.trial_offsets) < 3:
        reason = f"{figure_name}: insufficient trial_offsets ({len(trial_alignment.trial_offsets)} < 3)"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    elif bpod_data is None:
        reason = f"{figure_name}: bpod_data is None"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        # Log input details
        n_offsets = len(trial_alignment.trial_offsets)
        n_trials_bpod = bpod_data.n_trials
        logger.info(f"  trial_offsets: {n_offsets}, bpod_trials: {n_trials_bpod}")

        try:
            data_streams = _build_data_streams(bpod_data, ttl_data, pose_data, trial_alignment)
            if data_streams:
                logger.info(f"  data_streams: {list(data_streams.keys())}")
            path = plot_sync_quality_and_completeness(
                trial_alignment.trial_offsets,
                data_streams,
                figures_dir / "sync_quality_and_completeness.png",
                csv_output_dir=figures_dir,
            )
            if _validate_figure(path, figure_name):
                generated_files.append(path)
            else:
                reason = f"{figure_name}: returned None"
                logger.info(f"SKIP {reason}")
                skip_reasons.append(reason)
        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 7. Pose Keypoints
    # ========================================================================
    if pose_data is None or len(pose_data) == 0:
        figure_name = "pose_keypoints"
        attempted_count += 1
        logger.info(f"Attempting {figure_name}")
        reason = f"{figure_name}: pose_data is None or empty"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        pose_cameras = list(pose_data.keys())
        logger.info(f"  pose_cameras: {pose_cameras}")

        for camera_id, poses in pose_data.items():
            for i, pose in enumerate(poses):
                figure_name = f"pose_keypoints_{camera_id}_{i}"
                attempted_count += 1
                logger.info(f"Attempting {figure_name}")

                # Preflight checks
                if not hasattr(pose, "video_path"):
                    reason = f"{figure_name}: pose has no video_path attribute"
                    logger.info(f"SKIP {reason}")
                    skip_reasons.append(reason)
                    continue

                video_path = pose.video_path
                if not Path(video_path).exists():
                    reason = f"{figure_name}: video does not exist: {video_path}"
                    logger.info(f"SKIP {reason}")
                    skip_reasons.append(reason)
                    continue

                logger.info(f"  video_path: {video_path}")
                logger.info(f"  frames: {len(pose.frames) if hasattr(pose, 'frames') else 'N/A'}")

                try:
                    path = plot_pose_keypoints_grid(bundle=pose, video_path=pose.video_path, out_path=figures_dir / f"pose_keypoints_{camera_id}_{i}.png")
                    if _validate_figure(path, figure_name):
                        generated_files.append(path)
                    else:
                        reason = f"{figure_name}: returned None (video may not be openable)"
                        logger.info(f"SKIP {reason}")
                        skip_reasons.append(reason)
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

    # ========================================================================
    # 8. Ecephys QC Plots (from NWB)
    # ========================================================================
    if nwb_path is None or not nwb_path.exists():
        figure_name = "ecephys_plots"
        attempted_count += 1
        logger.info(f"Attempting {figure_name}")
        reason = f"{figure_name}: nwb_path not available"
        logger.info(f"SKIP {reason}")
        skip_reasons.append(reason)
    else:
        try:
            from pynwb import NWBHDF5IO

            from w2t_bkin.figures import plot_electrode_locations, plot_firing_rate_distribution, plot_spike_raster, plot_unit_quality_metrics

            logger.info(f"  nwb_path: {nwb_path}")

            with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
                nwbfile_read = io.read()

                # Check for electrodes
                has_electrodes = hasattr(nwbfile_read, "electrodes") and nwbfile_read.electrodes is not None
                # Check for units
                has_units = hasattr(nwbfile_read, "units") and nwbfile_read.units is not None

                logger.info(f"  has_electrodes: {has_electrodes}, has_units: {has_units}")

                # 8a. Electrode locations
                if has_electrodes and len(nwbfile_read.electrodes) > 0:
                    figure_name = "electrode_locations"
                    attempted_count += 1
                    logger.info(f"Attempting {figure_name}")

                    try:
                        electrodes_df = nwbfile_read.electrodes.to_dataframe()
                        logger.info(f"  electrodes: {len(electrodes_df)} channels")

                        # Check required columns
                        if "x" in electrodes_df.columns and "y" in electrodes_df.columns:
                            path = plot_electrode_locations(electrodes_df, out_path=figures_dir / "electrode_locations.png")
                            if _validate_figure(path, figure_name):
                                generated_files.append(path)
                            else:
                                reason = f"{figure_name}: returned None"
                                logger.info(f"SKIP {reason}")
                                skip_reasons.append(reason)
                        else:
                            reason = f"{figure_name}: missing x/y coordinates in electrodes table"
                            logger.info(f"SKIP {reason}")
                            skip_reasons.append(reason)
                    except Exception as e:
                        failed_count += 1
                        logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

                # 8b-d. Unit-based plots
                if has_units and len(nwbfile_read.units) > 0:
                    units_df = nwbfile_read.units.to_dataframe()
                    n_units = len(units_df)
                    logger.info(f"  units: {n_units}")

                    # Check for spike_times column
                    if "spike_times" not in units_df.columns:
                        reason = f"ecephys_units: missing spike_times column"
                        logger.info(f"SKIP {reason}")
                        skip_reasons.append(reason)
                    else:
                        # Get recording duration from session_start_time and timestamps
                        recording_duration = nwbfile_read.session_start_time.timestamp() if hasattr(nwbfile_read, "session_start_time") else 3600.0
                        # Better estimate from actual spike times
                        all_spike_times = []
                        for _, row in units_df.iterrows():
                            if len(row["spike_times"]) > 0:
                                all_spike_times.extend(row["spike_times"])
                        if all_spike_times:
                            recording_duration = max(all_spike_times)

                        logger.info(f"  recording_duration: {recording_duration:.1f}s")

                        # 8b. Spike raster (dynamically limit to first 50 units)
                        figure_name = "spike_raster"
                        attempted_count += 1
                        logger.info(f"Attempting {figure_name}")

                        max_units_raster = min(50, n_units)
                        logger.info(f"  plotting first {max_units_raster} of {n_units} units")

                        try:
                            path = plot_spike_raster(units_df, out_path=figures_dir / "spike_raster.png", max_units=max_units_raster)
                            if _validate_figure(path, figure_name):
                                generated_files.append(path)
                            else:
                                reason = f"{figure_name}: returned None"
                                logger.info(f"SKIP {reason}")
                                skip_reasons.append(reason)
                        except Exception as e:
                            failed_count += 1
                            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

                        # 8c. Firing rate distribution
                        figure_name = "firing_rate_distribution"
                        attempted_count += 1
                        logger.info(f"Attempting {figure_name}")

                        try:
                            path = plot_firing_rate_distribution(units_df, out_path=figures_dir / "firing_rate_distribution.png", recording_duration=recording_duration)
                            if _validate_figure(path, figure_name):
                                generated_files.append(path)
                            else:
                                reason = f"{figure_name}: returned None"
                                logger.info(f"SKIP {reason}")
                                skip_reasons.append(reason)
                        except Exception as e:
                            failed_count += 1
                            logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

                        # 8d. Unit quality metrics (silently skips if columns missing)
                        figure_name = "unit_quality_metrics"
                        attempted_count += 1
                        logger.info(f"Attempting {figure_name}")

                        required_cols = ["contamination_pct", "amplitude"]
                        if not all(col in units_df.columns for col in required_cols):
                            reason = f"{figure_name}: missing required columns {required_cols}"
                            logger.info(f"SKIP {reason}")
                            skip_reasons.append(reason)
                        else:
                            try:
                                path = plot_unit_quality_metrics(units_df, out_path=figures_dir / "unit_quality_metrics.png")
                                if _validate_figure(path, figure_name):
                                    generated_files.append(path)
                                else:
                                    reason = f"{figure_name}: returned None"
                                    logger.info(f"SKIP {reason}")
                                    skip_reasons.append(reason)
                            except Exception as e:
                                failed_count += 1
                                logger.warning(f"FAILED {figure_name}: {e}", exc_info=True)

        except Exception as e:
            failed_count += 1
            logger.warning(f"FAILED ecephys_plots: {e}", exc_info=True)

    # ========================================================================
    # Summary
    # ========================================================================
    generated_count = len(generated_files)
    skipped_count = len(skip_reasons)

    logger.info(f"\n{'='*60}")
    logger.info(f"Figure Generation Summary:")
    logger.info(f"  Attempted: {attempted_count}")
    logger.info(f"  Generated: {generated_count}")
    logger.info(f"  Skipped:   {skipped_count}")
    logger.info(f"  Failed:    {failed_count}")

    if skip_reasons:
        logger.info(f"\nSkip Reasons:")
        for reason in skip_reasons:
            logger.info(f"  - {reason}")

    logger.info(f"{'='*60}\n")

    return generated_files
