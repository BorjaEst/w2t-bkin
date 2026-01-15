"""Pose processing phase helpers."""

from typing import Dict, List, Optional, Tuple

from pynwb import NWBFile

from w2t_bkin import tasks
from w2t_bkin.models import DiscoveryResult, PoseData, PosePlan, SessionInfo, TTLData


def validate_dlc_generate_mode(session_info: SessionInfo, run_logger):
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
        raise ValueError("DLC mode='generate' requires metadata['pose'] section. Define pose.models and pose.cameras in your metadata.toml")

    models_meta = pose_meta.get("models", {})
    cameras_meta = pose_meta.get("cameras", {})

    if not models_meta:
        raise ValueError(
            "DLC mode='generate' requires at least one model in metadata['pose']['models']. " 'Example:\n[pose.models.my_dlc_model]\nsource = "dlc"\npath = "/path/to/config.yaml"'
        )

    if not cameras_meta:
        raise ValueError(
            "DLC mode='generate' requires camera configuration in metadata['pose']['cameras']. " 'Example:\n[pose.cameras.camera_0]\nsource = "dlc"\nmodel_id = "my_dlc_model"'
        )

    # Validate each camera's model reference
    dlc_cameras = {cid: cfg for cid, cfg in cameras_meta.items() if cfg.get("source") == "dlc"}

    if not dlc_cameras:
        run_logger.warning("DLC enabled but no cameras have source='dlc' in metadata['pose']['cameras']")
        return

    errors = []
    for camera_id, camera_config in dlc_cameras.items():
        model_id = camera_config.get("model_id")
        if not model_id:
            errors.append(f"Camera '{camera_id}' has source='dlc' but no 'model_id' specified")
            continue

        if model_id not in models_meta:
            errors.append(f"Camera '{camera_id}' references model_id='{model_id}' but metadata['pose']['models']['{model_id}'] does not exist")
            continue

        model_config = models_meta[model_id]
        model_path = model_config.get("path")
        if not model_path:
            errors.append(f"Model '{model_id}' (used by camera '{camera_id}') has no 'path' specified")

    if errors:
        raise ValueError("DLC generate mode validation failed:\n" + "\n".join(f"  - {err}" for err in errors))

    run_logger.info(f"✓ DLC generate mode validation passed ({len(dlc_cameras)} cameras configured)")


def resolve_pose_plan(session_info: SessionInfo, run_logger) -> PosePlan:
    """Resolve pose processing execution plan.

    Single source of truth for mode resolution and ingestion strategy.
    Prevents drift between artifact generation (Phase 2) and ingestion (Phase 3).

    Args:
        session_info: Session configuration with metadata
        run_logger: Prefect logger for reporting resolution decisions

    Returns:
        PosePlan with effective modes, ingestion strategy, and reasons
    """
    dlc_config = session_info.config.preprocessing.dlc
    sleap_config = session_info.config.preprocessing.sleap
    pose_metadata = session_info.metadata.get("pose", {})
    has_models = bool(pose_metadata.get("models", {}))
    has_cameras = bool(pose_metadata.get("cameras", {}))
    has_pose_section = bool(pose_metadata)

    # Resolve DLC effective mode
    dlc_mode = dlc_config.mode
    if not dlc_config.enabled:
        dlc_effective, dlc_reason = "off", "disabled in config"
    elif dlc_mode == "off":
        dlc_effective, dlc_reason = "off", "mode='off'"
    elif dlc_mode == "auto":
        if has_models:
            dlc_effective, dlc_reason = "generate", "mode='auto' → 'generate' (metadata.pose.models present)"
        else:
            dlc_effective, dlc_reason = "discover", "mode='auto' → 'discover' (no metadata.pose.models)"
    else:
        dlc_effective, dlc_reason = dlc_mode, f"mode='{dlc_mode}' (explicit)"

    # Resolve SLEAP effective mode
    sleap_mode = sleap_config.mode
    if not sleap_config.enabled:
        sleap_effective, sleap_reason = "off", "disabled in config"
    elif sleap_mode == "off":
        sleap_effective, sleap_reason = "off", "mode='off'"
    elif sleap_mode == "auto":
        sleap_effective, sleap_reason = "discover", "mode='auto' → 'discover' (generate not implemented)"
    elif sleap_mode == "generate":
        run_logger.warning("SLEAP mode='generate' not implemented, coercing to 'discover'")
        sleap_effective, sleap_reason = "discover", "mode='generate' → 'discover' (not implemented)"
    else:
        sleap_effective, sleap_reason = sleap_mode, f"mode='{sleap_mode}' (explicit)"

    # Determine ingestion strategy
    if dlc_effective == "off" and sleap_effective == "off":
        ingestion_strategy, strategy_reason = "none", "both DLC and SLEAP disabled"
    elif has_cameras and (dlc_effective == "discover" or sleap_effective == "discover"):
        ingestion_strategy, strategy_reason = "metadata_stem", "metadata.pose.cameras exists + discover mode active"
    elif dlc_effective == "generate" or sleap_effective == "generate":
        ingestion_strategy, strategy_reason = "artifact_list", "generation mode active (consume Phase 2 artifacts)"
    else:
        ingestion_strategy, strategy_reason = "artifact_list", "discover mode without metadata.pose.cameras (legacy path)"

    plan = PosePlan(
        dlc_mode=dlc_effective,
        sleap_mode=sleap_effective,
        ingestion_strategy=ingestion_strategy,
        should_generate_dlc=(dlc_effective == "generate"),
        should_generate_sleap=(sleap_effective == "generate"),
        has_pose_metadata=has_pose_section,
        reasons={"dlc": dlc_reason, "sleap": sleap_reason, "ingestion_strategy": strategy_reason},
    )

    run_logger.info(f"Pose plan: DLC={dlc_effective}, SLEAP={sleap_effective}, ingestion={ingestion_strategy}")
    return plan


def process_pose_artifacts(plan: PosePlan, session_info: SessionInfo, run_logger) -> Tuple[Dict, Dict]:
    """Generate pose estimation artifacts (Phase 2: generation only).

    Args:
        plan: Resolved pose execution plan
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Tuple of (dlc_artifacts, sleap_artifacts)
    """
    dlc_artifacts = {}
    sleap_artifacts = {}

    run_logger.info(f"Phase 2 (Artifacts): DLC={plan.dlc_mode}, SLEAP={plan.sleap_mode}")

    if plan.should_generate_dlc:
        validate_dlc_generate_mode(session_info, run_logger)
        force_rerun = session_info.config.preprocessing.force_rerun
        run_logger.info(f"{'⚠️  Regenerating' if force_rerun else 'Using cached'} DLC poses")
        dlc_artifacts = tasks.generate_dlc_session_task(session_info, force_rerun)
        run_logger.info(f"Generated DLC artifacts for {len(dlc_artifacts)} cameras")
    elif plan.dlc_mode == "discover":
        run_logger.info("DLC discover mode: skipping generation (ingestion in Phase 3)")
    else:
        run_logger.info("DLC disabled")

    if plan.should_generate_sleap:
        run_logger.warning("SLEAP generation requested but not implemented")
    elif plan.sleap_mode == "discover":
        run_logger.info("SLEAP discover mode: skipping generation (ingestion in Phase 3)")
    else:
        run_logger.info("SLEAP disabled")

    return dlc_artifacts, sleap_artifacts


def ingest_pose_data(plan: PosePlan, dlc_artifacts: Dict, sleap_artifacts: Dict, discovery: DiscoveryResult, session_info: SessionInfo, run_logger) -> Dict[str, List[PoseData]]:
    """Ingest pose estimation data from DLC and SLEAP.

    Args:
        plan: Resolved pose execution plan
        dlc_artifacts: DLC artifact paths from Phase 2 generation
        sleap_artifacts: SLEAP artifact paths from Phase 2 generation
        discovery: File discovery results
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Dictionary mapping camera_id to list of pose data
    """
    pose_data = {}

    run_logger.info(f"Phase 3 (Ingestion): strategy={plan.ingestion_strategy}, DLC={plan.dlc_mode}, SLEAP={plan.sleap_mode}")

    if plan.ingestion_strategy == "none":
        run_logger.info("No pose data to ingest (both DLC and SLEAP disabled)")
        return pose_data

    pose_metadata = session_info.metadata.get("pose", {})
    pose_cameras = pose_metadata.get("cameras", {})

    # Strategy 1: Metadata-driven stem-based discovery
    if plan.ingestion_strategy == "metadata_stem":
        if not pose_cameras:
            run_logger.warning("Ingestion strategy is 'metadata_stem' but metadata.pose.cameras is empty")
            return pose_data

        run_logger.info(f"Ingesting via metadata stem-matching for {len(pose_cameras)} camera(s)")

        for camera_id, camera_config in pose_cameras.items():
            source = camera_config.get("source")

            # Skip cameras not matching active modes
            if (source == "dlc" and plan.dlc_mode == "off") or (source == "sleap" and plan.sleap_mode == "off"):
                continue

            if camera_id not in discovery.camera_files:
                continue

            video_paths = discovery.camera_files[camera_id]
            poses = _ingest_camera_poses(camera_id, source, video_paths, session_info)

            if poses:
                pose_data[camera_id] = poses
                run_logger.info(f"Ingested {source.upper()} poses for {camera_id} ({len(poses)} video(s))")

        return pose_data

    # Strategy 2: Artifact-list ingestion (generate mode or legacy discover)
    run_logger.info("Ingesting via artifact list (from Phase 2 generation)")

    for camera_id, artifacts in dlc_artifacts.items():
        if camera_id in discovery.camera_files:
            video_paths = discovery.camera_files[camera_id]
            dlc_poses = _ingest_camera_poses(camera_id, "dlc", video_paths, session_info)
            if dlc_poses:
                pose_data[camera_id] = dlc_poses

    for camera_id, artifacts in sleap_artifacts.items():
        if camera_id in discovery.camera_files:
            video_paths = discovery.camera_files[camera_id]
            sleap_poses = _ingest_camera_poses(camera_id, "sleap", video_paths, session_info)
            if sleap_poses:
                pose_data.setdefault(camera_id, []).extend(sleap_poses)

    if pose_data:
        run_logger.info(f"Ingested pose data for {len(pose_data)} cameras")

    return pose_data


def _ingest_camera_poses(camera_id: str, source: str, video_paths: List, session_info: SessionInfo) -> Optional[List[PoseData]]:
    """Ingest pose data for a single camera.

    Args:
        camera_id: Camera identifier
        source: Pose source ("dlc" or "sleap")
        video_paths: List of video file paths
        session_info: Session configuration

    Returns:
        List of PoseData or None
    """
    source_dir_map = {"dlc": "dlc-pose", "sleap": "sleap-pose"}
    task_map = {"dlc": tasks.ingest_dlc_poses_task, "sleap": tasks.ingest_sleap_poses_task}

    pose_dir = session_info.interim_dir / source_dir_map[source] / camera_id
    ingest_task = task_map[source]

    return ingest_task(video_paths=video_paths, dlc_dir=pose_dir if source == "dlc" else None, sleap_dir=pose_dir if source == "sleap" else None, camera_id=camera_id)


def assemble_pose_data(nwbfile: NWBFile, pose_data: Dict[str, List[PoseData]], session_info: SessionInfo, ttl_data: Dict[str, TTLData], run_logger):
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
    skeletons_config = pose_meta.get("skeletons") or session_info.metadata.get("skeletons")

    for camera_id, pose_list in pose_data.items():
        camera_config = camera_configs_dict.get(camera_id, {}).copy()

        # Allow pose metadata to supply skeleton selection per camera
        pose_cam_cfg = pose_cameras_config.get(camera_id, {}) if isinstance(pose_cameras_config, dict) else {}
        if isinstance(pose_cam_cfg, dict) and pose_cam_cfg.get("skeleton_id"):
            camera_config["skeleton_id"] = pose_cam_cfg["skeleton_id"]

        tasks.assemble_pose_task(
            nwbfile=nwbfile,
            camera_id=camera_id,
            pose_data_list=pose_list,
            camera_config=camera_config,
            ttl_pulses=ttl_data if ttl_data else None,
            skeletons_config=skeletons_config,
        )

    run_logger.info(f"Assembled pose data for {len(pose_data)} cameras")
