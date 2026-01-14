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
    discover_dlc_poses_task,
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


def _validate_dlc_generate_mode(session_info, run_logger):
    """Validate metadata configuration for DLC generate mode.

    Ensures that all cameras configured for DLC have valid model references.

    Args:
        session_info: Session configuration with metadata
        run_logger: Prefect logger for reporting validation issues

    Raises:
        ValueError: If metadata configuration is invalid for generate mode
    """
    pose_meta = session_info.metadata.get("pose")

    if not pose_meta:
        raise ValueError("DLC mode='generate' requires metadata['pose'] section. " "Define pose.models and pose.cameras in your metadata.toml")

    models_meta = pose_meta.get("models", {})
    cameras_meta = pose_meta.get("cameras", {})

    if not models_meta:
        raise ValueError(
            "DLC mode='generate' requires at least one model in metadata['pose']['models']. "
            "Example:\n"
            "[pose.models.my_dlc_model]\n"
            'source = "dlc"\n'
            'path = "/path/to/config.yaml"'
        )

    if not cameras_meta:
        raise ValueError(
            "DLC mode='generate' requires camera configuration in metadata['pose']['cameras']. "
            "Example:\n"
            "[pose.cameras.camera_0]\n"
            'source = "dlc"\n'
            'model_id = "my_dlc_model"'
        )

    # Validate each camera's model reference
    dlc_cameras = {cid: cfg for cid, cfg in cameras_meta.items() if cfg.get("source") == "dlc"}

    if not dlc_cameras:
        run_logger.warning("DLC enabled but no cameras have source='dlc' in metadata['pose']['cameras']")
        return

    errors = []
    for camera_id, camera_config in dlc_cameras.items():
        # Check model_id is specified
        model_id = camera_config.get("model_id")
        if not model_id:
            errors.append(f"Camera '{camera_id}' has source='dlc' but no 'model_id' specified")
            continue

        # Check model_id exists in models
        if model_id not in models_meta:
            errors.append(f"Camera '{camera_id}' references model_id='{model_id}' but " f"metadata['pose']['models']['{model_id}'] does not exist")
            continue

        # Check model has a valid path
        model_config = models_meta[model_id]
        model_path = model_config.get("path")
        if not model_path:
            errors.append(f"Model '{model_id}' (used by camera '{camera_id}') has no 'path' specified")

    if errors:
        raise ValueError("DLC generate mode validation failed:\n" + "\n".join(f"  - {err}" for err in errors))

    run_logger.info(f"✓ DLC generate mode validation passed ({len(dlc_cameras)} cameras configured)")


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

    # Determine DLC effective mode
    dlc_config = session_info.config.preprocessing.dlc
    dlc_enabled = dlc_config.enabled
    dlc_mode = dlc_config.mode

    # Auto mode: check if metadata defines pose models for generate capability
    if dlc_mode == "auto":
        # Check if metadata has pose.models section (indicates generate intent)
        pose_metadata = session_info.metadata.get("pose", {})
        has_models = bool(pose_metadata.get("models", {}))
        dlc_mode = "generate" if has_models else "discover"
        run_logger.debug(f"DLC auto mode resolved to '{dlc_mode}' (metadata.pose.models present: {has_models})")

    # Preflight validation for generate mode
    if dlc_enabled and dlc_mode == "generate":
        _validate_dlc_generate_mode(session_info, run_logger)

    if dlc_enabled and dlc_mode != "off":
        if dlc_mode == "generate":
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

        elif dlc_mode == "discover":
            # Discover mode: find pre-existing H5 files via stem-matching
            # Files must exist in interim/dlc-pose/<camera_id>/ with names matching {video_stem}DLC*.h5
            for camera_id, video_paths in discovery.camera_files.items():
                camera_dlc_dir = session_info.interim_dir / "dlc-pose" / camera_id
                artifacts = discover_dlc_poses_task(
                    video_paths=video_paths,
                    dlc_dir=camera_dlc_dir,
                    camera_id=camera_id,
                )
                if artifacts:
                    dlc_artifacts[camera_id] = artifacts
            if dlc_artifacts:
                run_logger.info(f"Found DLC artifacts for {len(dlc_artifacts)} cameras")
    else:
        run_logger.info("DLC processing disabled")

    # Determine SLEAP effective mode
    sleap_config = session_info.config.preprocessing.sleap
    sleap_enabled = sleap_config.enabled
    sleap_mode = sleap_config.mode

    # Auto mode for SLEAP defaults to discover (generate not implemented)
    if sleap_mode == "auto":
        sleap_mode = "discover"

    if sleap_enabled and sleap_mode != "off":
        if sleap_mode == "generate":
            # SLEAP generation not implemented
            run_logger.warning("SLEAP mode='generate' not implemented; skipping")

        elif sleap_mode == "discover":
            # Discover mode: artifacts will be sourced from metadata.pose.cameras
            # Legacy path for backward compatibility (if no metadata)
            for camera_id, video_paths in discovery.camera_files.items():
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
        dlc_artifacts: DLC artifact paths from generation (mode='generate')
        sleap_artifacts: SLEAP artifact paths from discovery
        discovery: File discovery results
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Dictionary mapping camera_id to list of pose data
    """
    pose_data = {}

    # Check if metadata has pose section for discover mode
    pose_metadata = session_info.metadata.get("pose", {})
    pose_cameras = pose_metadata.get("cameras", {})  # Dict keyed by camera_id

    # If discover mode and metadata.pose.cameras exists, use metadata-driven ingestion
    dlc_mode = session_info.config.preprocessing.dlc.mode
    sleap_mode = session_info.config.preprocessing.sleap.mode

    # Auto mode resolution (check metadata.pose.models presence)
    if dlc_mode == "auto":
        has_models = bool(pose_metadata.get("models", {}))
        dlc_mode = "generate" if has_models else "discover"
    if sleap_mode == "auto":
        has_models = bool(pose_metadata.get("models", {}))
        sleap_mode = "generate" if has_models else "discover"

    # Metadata-driven ingestion (discover mode with pose.cameras config)
    # Uses stem-based discovery: matches video files to H5 files by filename stem
    # H5s must be in interim/{dlc-pose|sleap-pose}/<camera_id>/ with appropriate naming:
    #   - DLC: {video_stem}DLC*.h5
    #   - SLEAP: *{video_stem}*.h5
    # Multiple videos per camera (e.g., buffer rollover) → multiple H5s → list of PoseData
    if pose_cameras and (dlc_mode == "discover" or sleap_mode == "discover"):
        run_logger.info(f"Using stem-based pose ingestion for {len(pose_cameras)} camera(s) " f"(H5s in interim/{{dlc|sleap}}-pose/<camera_id>/)")

        # Get optional mappings dict
        mappings_dict = pose_metadata.get("mappings", {})

        # Ingest poses from metadata.pose.cameras (dict keyed by camera_id)
        for camera_id, camera_config in pose_cameras.items():
            source = camera_config.get("source")
            model_id = camera_config.get("model_id")

            # Skip if wrong source for current mode
            if source == "dlc" and dlc_mode != "discover":
                continue
            if source == "sleap" and sleap_mode != "discover":
                continue

            # Stem-based discovery from camera's video files
            if camera_id in discovery.camera_files:
                video_paths = discovery.camera_files[camera_id]

                # Get optional mapping
                mapping = None
                if "mapping_id" in camera_config:
                    mapping_id = camera_config["mapping_id"]
                    if mapping_id in mappings_dict:
                        mapping = mappings_dict[mapping_id]

                # Ingest based on source
                if source == "dlc":
                    camera_dlc_dir = session_info.interim_dir / "dlc-pose" / camera_id
                    dlc_poses = ingest_dlc_poses_task(
                        video_paths=video_paths,
                        dlc_dir=camera_dlc_dir,
                        camera_id=camera_id,
                    )
                    if dlc_poses:
                        # Apply mapping if specified (harmonization deferred to assembly for now)
                        pose_data[camera_id] = dlc_poses
                        run_logger.info(f"Ingested DLC poses for {camera_id} ({len(dlc_poses)} video(s))")

                elif source == "sleap":
                    camera_sleap_dir = session_info.interim_dir / "sleap-pose" / camera_id
                    sleap_poses = ingest_sleap_poses_task(
                        video_paths=video_paths,
                        sleap_dir=camera_sleap_dir,
                        camera_id=camera_id,
                    )
                    if sleap_poses:
                        pose_data[camera_id] = sleap_poses
                        run_logger.info(f"Ingested SLEAP poses for {camera_id} ({len(sleap_poses)} video(s))")

        return pose_data

    # Legacy artifact-based ingestion (generate mode or backward compatibility)
    # Ingest DLC poses from generated artifacts
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

    pose_meta = session_info.metadata.get("pose", {})
    pose_cameras_config = pose_meta.get("cameras", {})

    # Skeleton definitions: prefer pose.skeletons (current templates) and fall back
    # to a legacy top-level 'skeletons' if present.
    skeletons_config = pose_meta.get("skeletons") or session_info.metadata.get("skeletons")

    for camera_id, pose_list in pose_data.items():
        camera_config = camera_configs_dict.get(camera_id, {}).copy()

        # Allow pose metadata to supply skeleton selection per camera.
        # Camera metadata remains the source of fps/ttl_id and file discovery.
        pose_cam_cfg = pose_cameras_config.get(camera_id, {}) if isinstance(pose_cameras_config, dict) else {}
        if isinstance(pose_cam_cfg, dict) and pose_cam_cfg.get("skeleton_id"):
            camera_config["skeleton_id"] = pose_cam_cfg["skeleton_id"]

        assemble_pose_task(
            nwbfile=nwbfile,
            camera_id=camera_id,
            pose_data_list=pose_list,
            camera_config=camera_config,
            ttl_pulses=ttl_data if ttl_data else None,
            skeletons_config=skeletons_config,
        )

    run_logger.info(f"Assembled pose data for {len(pose_data)} cameras")
