"""Session-level flow orchestration for w2t-bkin pipeline.

This module defines the main Prefect flow for processing a single session.
It orchestrates all 21 atomic tasks in the correct sequence, with parallel
execution for camera-level operations and comprehensive error handling.

Architecture:
    Pure functions (operations/) → Atomic tasks (tasks/) → Flow orchestration (here)

Flow Phases:
    0. Configuration: Load config and create NWB file
    1. Discovery: Find all data files
    2. Artifacts: Generate DLC/SLEAP poses (parallel per camera)
    3. Ingestion: Load Bpod, pose, and TTL data
    4. Synchronization: Compute alignment statistics
    5. Assembly: Build NWB data structures
    6. Finalization: Write, validate, and create sidecars

Example:
    >>> from w2t_bkin.flows import process_session_flow
    >>> result = process_session_flow(
    ...     config_path="config.toml",
    ...     subject_id="subject-001",
    ...     session_id="session-001"
    ... )
    >>> print(f"Success: {result.success}, NWB: {result.nwb_path}")
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional

from prefect import flow, get_run_logger
from prefect.runtime import flow_run as flow_run_runtime
from pynwb import NWBFile

from w2t_bkin import utils
from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.models import SessionInfo, SessionResult
from w2t_bkin.tasks import (
    add_skeletons_task,
    align_trials_task,
    assemble_behavior_task,
    assemble_pose_task,
    compute_alignment_stats_task,
    create_nwb_file_task,
    discover_all_files_task,
    discover_sleap_poses_task,
    finalize_session_task,
    generate_dlc_session_task,
    generate_figures_task,
    ingest_bpod_task,
    ingest_dlc_poses_task,
    ingest_sleap_poses_task,
    ingest_ttl_task,
    setup_flow_session_task,
    verify_session_inputs_task,
)

logger = logging.getLogger(__name__)


@flow(
    name="process-session",
    description="Process single session with atomic task orchestration",
    log_prints=True,
    persist_result=True,
)
def process_session_flow(subject_id: str, session_id: str, config: SessionFlowConfig) -> SessionResult:
    """Process a single session through the complete w2t-bkin pipeline.

    This flow orchestrates all atomic Prefect tasks to transform raw behavioral
    and pose data into a validated NWB file. Paths come from environment variables.

    Args:
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")
        config: Pipeline configuration (baked from configuration.toml at deployment time)

    Returns:
        SessionResult with success status, paths, and metadata
    """
    run_logger = get_run_logger()
    start_time = datetime.now()
    file_handler = None
    file_handler_attached = False
    session_info = None

    try:
        run_logger.info(f"Starting session processing: {subject_id}/{session_id}")

        # =====================================================================
        # Phase 0: Configuration
        # =====================================================================
        run_logger.info("Phase 0: Loading session configuration")

        session_info: SessionInfo = setup_flow_session_task(subject_id, session_id, config)

        # Setup file logging to pipeline.log with Prefect flow-run isolation
        log_file = session_info.output_dir / "pipeline.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Bind handler to current Prefect flow-run context to prevent cross-session contamination
        try:
            flow_run_id = flow_run_runtime.id
            if flow_run_id is None:
                raise RuntimeError("No Prefect flow run context available")
            flow_run_filter = utils.PrefectFlowRunFilter(flow_run_id)
            file_handler.addFilter(flow_run_filter)
            logging.getLogger("w2t_bkin").addHandler(file_handler)
            file_handler_attached = True
            run_logger.info(f"File logging enabled: {log_file} (bound to flow-run {flow_run_id})")
        except Exception as e:
            # Only skip file logging (don't attach unfiltered handler to prevent cross-contamination)
            run_logger.warning(f"File logging disabled - no Prefect context isolation available: {e}")
            file_handler.close()  # Clean up unused handler

        nwbfile = create_nwb_file_task(session_info)

        # =====================================================================
        # Phase 1: Discovery
        # =====================================================================
        run_logger.info("Phase 1: Discovering files")

        discovery = discover_all_files_task(session_info)

        n_cameras = len(discovery.camera_files)
        n_bpod = len(discovery.bpod_files)
        n_ttl = len(discovery.ttl_files)
        run_logger.info(f"Discovered: {n_cameras} cameras, {n_bpod} bpod files, {n_ttl} TTL files")

        # =====================================================================
        # Phase 1.5: Verification (Fail-Fast)
        # =====================================================================
        run_logger.info("Phase 1.5: Verifying session inputs")

        verification_result = verify_session_inputs_task(discovery, session_info)

        if session_info.config.verification.enabled:
            if session_info.config.verification.check_frame_counts:
                total_frames = sum(verification_result.get("frame_counts", {}).values())
                run_logger.info(f"Verified frame counts: {total_frames} total frames across cameras")

            if session_info.config.verification.check_sync_mismatch:
                verified_cameras = verification_result.get("verified_cameras", [])
                run_logger.info(f"Verified synchronization for {len(verified_cameras)} cameras")
        else:
            run_logger.info("Verification skipped (disabled in configuration)")

        # =====================================================================
        # Phase 2: Artifact Generation
        # =====================================================================
        run_logger.info("Phase 2: Generating pose artifacts")
        dlc_artifacts, sleap_artifacts = _process_pose_artifacts(discovery, session_info, run_logger)

        # =====================================================================
        # Phase 3: Ingestion
        # =====================================================================
        run_logger.info("Phase 3: Ingesting data")

        # Ingest Bpod behavioral data
        bpod_data = None
        if session_info.config.bpod.parse and discovery.bpod_files:
            bpod_data = ingest_bpod_task(
                session_dir=session_info.session_dir,
                pattern="Bpod/*.mat",
                order="time_asc",
                continuous_time=False,
            )
            run_logger.info(f"Ingested Bpod data: {bpod_data.n_trials} trials")

        # Ingest pose data
        pose_data = _ingest_pose_data(dlc_artifacts, sleap_artifacts, discovery, session_info, run_logger)

        # Ingest TTL pulses
        ttl_data = {}
        if discovery.ttl_files:
            ttl_configs = session_info.metadata.get("TTLs", [])
            ttl_patterns = {ttl["id"]: ttl["paths"] for ttl in ttl_configs}
            ttl_data = ingest_ttl_task(
                session_dir=session_info.session_dir,
                ttl_patterns=ttl_patterns,
            )
            run_logger.info(f"Ingested TTL data for {len(ttl_data)} channels")

        # Align trials with TTL
        trial_alignment = _align_trials_with_ttl(bpod_data, ttl_data, session_info, run_logger)

        # =====================================================================
        # Phase 4: Synchronization
        # =====================================================================
        run_logger.info("Phase 4: Computing synchronization statistics")
        alignment_stats = _compute_sync_stats(trial_alignment, ttl_data, run_logger)

        # =====================================================================
        # Phase 5: Assembly
        # =====================================================================
        run_logger.info("Phase 5: Assembling NWB data structures")

        # Assemble behavior tables
        if bpod_data:
            trial_offsets = trial_alignment.trial_offsets if trial_alignment else []
            assemble_behavior_task(
                nwbfile=nwbfile,
                bpod_data=bpod_data,
                trial_offsets=trial_offsets,
            )
            run_logger.info("Assembled behavior tables")

        # Assemble pose estimation data
        if pose_data:
            _assemble_pose_data(nwbfile, pose_data, session_info, ttl_data, run_logger)

        # =====================================================================
        # Phase 6: Finalization
        # =====================================================================
        run_logger.info("Phase 6: Writing and validating NWB file")

        # Convert config to dict for finalization
        config_dict = {
            "nwb": session_info.config.nwb.__dict__ if hasattr(session_info.config.nwb, "__dict__") else {},
            "subject": session_info.metadata,
        }

        finalization_result = finalize_session_task(
            nwbfile=nwbfile,
            output_dir=session_info.output_dir,
            session_id=session_id,
            config_dict=config_dict,
            alignment_stats=alignment_stats,
            skip_validation=False,  # Always validate (controlled via config.qc.generate_report if needed)
        )

        # Generate diagnostic figures
        try:
            nwb_path = finalization_result.get("nwb_path")
            pipeline_profile_path = session_info.output_dir / "pipeline_profile.json"

            figure_paths = generate_figures_task(
                output_dir=session_info.output_dir,
                alignment_stats=alignment_stats,
                trial_alignment=trial_alignment,
                bpod_data=bpod_data,
                ttl_data=ttl_data,
                pose_data=pose_data,
                nwb_path=nwb_path,
                pipeline_profile_path=pipeline_profile_path if pipeline_profile_path.exists() else None,
            )
            run_logger.info(f"Generated {len(figure_paths)} diagnostic figures")
        except Exception as e:
            run_logger.warning(f"Figure generation failed: {e}")

        # Build successful result
        result = SessionResult(
            success=True,
            subject_id=subject_id,
            session_id=session_id,
            nwb_path=finalization_result.get("nwb_path"),
            validation=finalization_result.get("validation_results"),
            artifacts={
                "dlc": dlc_artifacts if dlc_artifacts else {},
                "sleap": sleap_artifacts if sleap_artifacts else {},
            },
            duration_seconds=0,  # Will be set below
        )

        # Calculate total duration
        duration = (datetime.now() - start_time).total_seconds()
        result.duration_seconds = duration

        run_logger.info(f"Session processing complete: {subject_id}/{session_id} " f"(duration: {duration:.1f}s)")

        return result

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        run_logger.error(f"Session processing failed: {e}", exc_info=True)

        # Write error profile if possible
        if session_info:
            try:
                profile_path = session_info.output_dir / "pipeline_profile.json"
                profile_data = {
                    "success": False,
                    "error": str(e),
                    "phases": [],
                }
                utils.write_json(profile_data, profile_path)
            except Exception:
                pass  # Ignore errors during error handling

        return SessionResult(
            success=False,
            subject_id=subject_id,
            session_id=session_id,
            error=str(e),
            duration_seconds=duration,
        )
    finally:
        # Clean up file handler to prevent cross-session contamination
        if file_handler_attached:
            logging.getLogger("w2t_bkin").removeHandler(file_handler)
            file_handler.close()


def _process_pose_artifacts(discovery, session_info, run_logger) -> tuple[dict, dict]:
    """Generate and discover pose estimation artifacts.

    Args:
        discovery: File discovery results
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Tuple of (dlc_artifacts, sleap_artifacts)
    """
    dlc_artifacts = {}
    sleap_artifacts = {}

    # Generate or discover DLC artifacts
    dlc_enabled = session_info.config.preprocessing.dlc.enabled
    if dlc_enabled:
        # Generate new DLC artifacts
        force_rerun = session_info.config.preprocessing.force_rerun
        if force_rerun:
            run_logger.info("⚠️  force_rerun=True: Regenerating all DLC poses")
        else:
            run_logger.info("Using cached DLC poses (if available)")

        dlc_artifacts = generate_dlc_session_task(
            session_info=session_info,
            force_rerun=force_rerun,
        )
        run_logger.info(f"Generated DLC artifacts for {len(dlc_artifacts)} cameras")
    else:
        run_logger.info("DLC processing disabled")

    # Discover SLEAP artifacts
    sleap_enabled = session_info.config.preprocessing.sleap.enabled
    if sleap_enabled:
        # Discover existing SLEAP files (SLEAP generation not yet implemented)
        for camera_id, video_paths in discovery.camera_files.items():
            # Camera-specific SLEAP output directory
            camera_sleap_dir = session_info.interim_dir / "sleap-pose" / camera_id
            artifacts = discover_sleap_poses_task(
                video_paths=video_paths,
                sleap_dir=camera_sleap_dir,
                camera_id=camera_id,
            )
            if artifacts:
                sleap_artifacts[camera_id] = artifacts
        if sleap_artifacts:
            run_logger.info(f"Found SLEAP artifacts for {len(sleap_artifacts)} cameras")
    else:
        run_logger.info("SLEAP processing disabled")

    return dlc_artifacts, sleap_artifacts


def _ingest_pose_data(dlc_artifacts, sleap_artifacts, discovery, session_info, run_logger) -> dict:
    """Ingest pose estimation data from DLC and SLEAP.

    Args:
        dlc_artifacts: DLC artifact paths
        sleap_artifacts: SLEAP artifact paths
        discovery: File discovery results
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Dictionary mapping camera_id to list of pose data
    """
    pose_data = {}

    # Ingest DLC poses
    for camera_id, artifacts in dlc_artifacts.items():
        if camera_id in discovery.camera_files:
            video_paths = discovery.camera_files[camera_id]
            # Camera-specific DLC directory
            camera_dlc_dir = session_info.interim_dir / "dlc-pose" / camera_id
            dlc_poses = ingest_dlc_poses_task(
                video_paths=video_paths,
                dlc_dir=camera_dlc_dir,
                camera_id=camera_id,
            )
            if dlc_poses:
                pose_data[camera_id] = dlc_poses

    # Ingest SLEAP poses
    for camera_id, artifacts in sleap_artifacts.items():
        if camera_id in discovery.camera_files:
            video_paths = discovery.camera_files[camera_id]
            # Camera-specific SLEAP directory
            camera_sleap_dir = session_info.interim_dir / "sleap-pose" / camera_id
            sleap_poses = ingest_sleap_poses_task(
                video_paths=video_paths,
                sleap_dir=camera_sleap_dir,
                camera_id=camera_id,
            )
            if sleap_poses:
                # Merge with existing DLC poses if present
                if camera_id in pose_data:
                    pose_data[camera_id].extend(sleap_poses)
                else:
                    pose_data[camera_id] = sleap_poses

    if pose_data:
        run_logger.info(f"Ingested pose data for {len(pose_data)} cameras")

    return pose_data


def _align_trials_with_ttl(bpod_data, ttl_data, session_info, run_logger):
    """Align behavioral trials with TTL pulses.

    Args:
        bpod_data: Bpod behavioral data
        ttl_data: TTL pulse data
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Trial alignment result or None
    """
    if not (bpod_data and ttl_data):
        return None

    # Extract trial_type configs from metadata
    bpod_meta = session_info.metadata.get("bpod", {})
    sync_meta = bpod_meta.get("sync", {}) if isinstance(bpod_meta, dict) else {}
    trial_type_configs = sync_meta.get("trial_types", []) if isinstance(sync_meta, dict) else []

    if not trial_type_configs:
        run_logger.info("Skipping trial alignment (no trial_type configs in metadata)")
        return None

    # Extract TTL pulse timestamps
    ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}

    trial_alignment = align_trials_task(
        trial_type_configs=trial_type_configs,
        bpod_data=bpod_data.data,
        ttl_pulses=ttl_pulses,
    )

    if trial_alignment.warnings:
        for warning in trial_alignment.warnings:
            run_logger.warning(f"Trial alignment: {warning}")

    return trial_alignment


def _compute_sync_stats(trial_alignment, ttl_data, run_logger):
    """Compute synchronization statistics.

    Args:
        trial_alignment: Trial alignment results
        ttl_data: TTL pulse data
        run_logger: Prefect logger

    Returns:
        Alignment statistics or None
    """
    if not (trial_alignment and ttl_data):
        return None

    ttl_channels = {ttl_id: len(ttl.timestamps) for ttl_id, ttl in ttl_data.items()}

    # Convert trial_offsets dict to list of values
    trial_offsets_list = list(trial_alignment.trial_offsets.values()) if isinstance(trial_alignment.trial_offsets, dict) else trial_alignment.trial_offsets

    alignment_stats = compute_alignment_stats_task(
        trial_offsets=trial_offsets_list,
        ttl_channels=ttl_channels,
    )

    run_logger.info("Computed alignment statistics")
    return alignment_stats


def _assemble_pose_data(nwbfile, pose_data, session_info, ttl_data, run_logger):
    """Assemble pose estimation data into NWB file.

    Args:
        nwbfile: NWB file object
        pose_data: Dictionary of pose data by camera
        session_info: Session configuration
        ttl_data: TTL pulse data
        run_logger: Prefect logger
    """
    if not pose_data:
        return

    cameras_meta = session_info.metadata.get("cameras", [])
    camera_configs_dict = {cam["id"]: cam for cam in cameras_meta} if cameras_meta else {}
    skeletons_config = session_info.metadata.get("skeletons", None)

    for camera_id, pose_list in pose_data.items():
        camera_config = camera_configs_dict.get(camera_id, {})
        assemble_pose_task(
            nwbfile=nwbfile,
            camera_id=camera_id,
            pose_data_list=pose_list,
            camera_config=camera_config,
            ttl_pulses=ttl_data if ttl_data else None,
            skeletons_config=skeletons_config,
        )

    run_logger.info(f"Assembled pose data for {len(pose_data)} cameras")
