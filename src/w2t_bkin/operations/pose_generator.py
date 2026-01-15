"""Operations for discovering and generating pose estimation artifacts.

This module bridges metadata + discovered videos to concrete intermediate pose
artifacts stored under the session interim directory.

Supported sources:
        - DeepLabCut (DLC) via `w2t_bkin.processors.dlc`
        - SLEAP discovery only (generation TODO)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from w2t_bkin.config import ArtifactsConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.metadata import Metadata
from w2t_bkin.models import ArtifactsResult, DiscoveryResult, SessionInfo
from w2t_bkin.processors import dlc

logger = logging.getLogger(__name__)


def _get_metadata(info: SessionInfo) -> Metadata:
    try:
        return Metadata.model_validate(info.metadata)
    except Exception as e:
        raise IngestError(
            message="Failed to validate merged metadata for pose artifacts",
            context={"error": str(e)},
            hint="Fix metadata TOML structure under [pose] and session required fields.",
        )


def _camera_is_optional(meta: Metadata, camera_id: str) -> bool:
    for cam in meta.cameras:
        if cam.id == camera_id:
            return bool(cam.optional)
    return False


def resolve_artifact_subdir(meta: Metadata, camera_id: str) -> str:
    """Resolve artifact subdirectory name for a pose camera."""

    pose_cam = meta.pose.cameras.get(camera_id)
    if pose_cam is None:
        raise IngestError(
            message="Pose camera not configured",
            context={"camera_id": camera_id},
            hint="Add [pose.cameras.<camera_id>] to metadata.toml.",
        )

    if pose_cam.artifacts:
        return pose_cam.artifacts

    if pose_cam.model_id:
        model = meta.pose.models.get(pose_cam.model_id)
        if model and getattr(model, "artifacts", None):
            return str(model.artifacts)

    # Fallback by source
    return "dlc-pose" if pose_cam.source == "dlc" else "sleap-pose"


def _expected_pose_globs(source: str, video_stem: str) -> Tuple[str, Optional[str]]:
    """Return (h5_glob, csv_glob) for a given source and video stem."""
    if source == "dlc":
        return f"{video_stem}DLC_*.h5", f"{video_stem}DLC_*.csv"
    # SLEAP naming varies; keep discovery permissive
    return f"{video_stem}*.h5", f"{video_stem}*.csv"


def discover_pose_artifacts(discovery: DiscoveryResult, info: SessionInfo) -> ArtifactsResult:
    meta = _get_metadata(info)

    pose_h5_by_camera: Dict[str, List[Path]] = {}
    pose_csv_by_camera: Dict[str, List[Path]] = {}
    status_by_camera: Dict[str, Dict] = {}

    for camera_id, pose_cam in meta.pose.cameras.items():
        artifact_subdir = resolve_artifact_subdir(meta, camera_id)
        camera_dir = info.interim_dir / artifact_subdir / camera_id

        videos = discovery.camera_files.get(camera_id, [])
        h5_paths: List[Path] = []
        csv_paths: List[Path] = []
        missing_for_all_videos = True

        for video_path in videos:
            h5_glob, csv_glob = _expected_pose_globs(pose_cam.source, video_path.stem)
            found_h5 = sorted(camera_dir.glob(h5_glob))
            found_csv = sorted(camera_dir.glob(csv_glob)) if csv_glob else []
            if found_h5:
                missing_for_all_videos = False
            h5_paths.extend(found_h5)
            csv_paths.extend(found_csv)

        pose_h5_by_camera[camera_id] = h5_paths
        pose_csv_by_camera[camera_id] = csv_paths

        status_by_camera[camera_id] = {
            "mode": "discover",
            "artifact_subdir": artifact_subdir,
            "videos": [str(p) for p in videos],
            "h5_count": len(h5_paths),
            "csv_count": len(csv_paths),
        }

        if (not videos) and not _camera_is_optional(meta, camera_id):
            raise IngestError(
                message="No video files discovered for pose camera",
                context={"camera_id": camera_id, "interim_dir": str(info.interim_dir)},
                hint="Ensure [cameras] includes this camera and raw videos exist for the session.",
            )

        if missing_for_all_videos and not _camera_is_optional(meta, camera_id):
            h5_glob, _ = _expected_pose_globs(pose_cam.source, "<video_stem>")
            raise IngestError(
                message="Missing required pose artifacts in discover mode",
                context={"camera_id": camera_id, "search_dir": str(camera_dir), "expected_glob": h5_glob},
                hint="Generate pose outputs under interim artifacts or switch artifacts.mode to 'generate' or 'auto'.",
            )

    return ArtifactsResult(
        pose_h5_by_camera=pose_h5_by_camera,
        pose_csv_by_camera=pose_csv_by_camera,
        status_by_camera=status_by_camera,
    )


def _generate_dlc_for_camera(
    *,
    camera_id: str,
    video_paths: List[Path],
    model_config_path: Path,
    output_dir: Path,
    artifacts_config: ArtifactsConfig,
) -> Tuple[List[Path], List[Path], Dict]:
    options = dlc.DLCInferenceOptions(gputouse=artifacts_config.gpu, save_as_csv=artifacts_config.save_csv)
    results = dlc.run_dlc_inference_batch(
        video_paths=video_paths,
        model_config_path=model_config_path,
        output_dir=output_dir,
        options=options,
    )

    h5_paths: List[Path] = []
    csv_paths: List[Path] = []
    errors: List[Dict] = []
    for r in results:
        if r.success and r.h5_output_path:
            h5_paths.append(r.h5_output_path)
            if r.csv_output_path:
                csv_paths.append(r.csv_output_path)
        else:
            errors.append({"video": str(r.video_path), "error": r.error_message})

    status = {
        "mode": "generate",
        "camera_id": camera_id,
        "model_config": str(model_config_path),
        "output_dir": str(output_dir),
        "generated_h5": len(h5_paths),
        "generated_csv": len(csv_paths),
        "errors": errors,
    }
    return h5_paths, csv_paths, status


def generate_pose_artifacts(discovery: DiscoveryResult, info: SessionInfo, artifacts_config: ArtifactsConfig) -> ArtifactsResult:
    meta = _get_metadata(info)

    pose_h5_by_camera: Dict[str, List[Path]] = {}
    pose_csv_by_camera: Dict[str, List[Path]] = {}
    status_by_camera: Dict[str, Dict] = {}

    for camera_id, pose_cam in meta.pose.cameras.items():
        videos = discovery.camera_files.get(camera_id, [])
        if (not videos) and not _camera_is_optional(meta, camera_id):
            raise IngestError(
                message="No video files discovered for pose camera; cannot generate pose artifacts",
                context={"camera_id": camera_id},
                hint="Ensure raw videos exist and [cameras] metadata includes correct paths.",
            )

        if pose_cam.source != "dlc":
            raise IngestError(
                message="Pose artifact generation not supported for this source",
                context={"camera_id": camera_id, "source": pose_cam.source},
                hint="Use artifacts.mode='discover' for SLEAP until generation is implemented.",
            )

        if not pose_cam.model_id:
            raise IngestError(
                message="Pose camera missing model_id; cannot generate",
                context={"camera_id": camera_id},
                hint="Set model_id under [pose.cameras.<camera_id>] in metadata.toml.",
            )

        model = meta.pose.models.get(pose_cam.model_id)
        if model is None:
            raise IngestError(
                message="Pose model not found in metadata",
                context={"camera_id": camera_id, "model_id": pose_cam.model_id},
                hint="Define [pose.models.<model_id>] in metadata.toml.",
            )

        model_config_path = (info.models_dir / model.path).resolve()
        if not model_config_path.exists():
            raise IngestError(
                message="Pose model config file not found",
                context={"camera_id": camera_id, "model_config_path": str(model_config_path)},
                hint="Check W2T_MODELS_ROOT and pose.models.<model_id>.path.",
            )

        artifact_subdir = resolve_artifact_subdir(meta, camera_id)
        output_dir = info.interim_dir / artifact_subdir / camera_id
        output_dir.mkdir(parents=True, exist_ok=True)

        h5_paths, csv_paths, status = _generate_dlc_for_camera(
            camera_id=camera_id,
            video_paths=videos,
            model_config_path=model_config_path,
            output_dir=output_dir,
            artifacts_config=artifacts_config,
        )

        pose_h5_by_camera[camera_id] = h5_paths
        pose_csv_by_camera[camera_id] = csv_paths
        status_by_camera[camera_id] = status

        if (not h5_paths) and not _camera_is_optional(meta, camera_id):
            raise IngestError(
                message="Pose artifact generation completed but produced no H5 outputs",
                context={"camera_id": camera_id, "output_dir": str(output_dir), "status": status},
                hint="Inspect logs for DLC inference errors and ensure DeepLabCut is installed in the runtime environment.",
            )

    return ArtifactsResult(
        pose_h5_by_camera=pose_h5_by_camera,
        pose_csv_by_camera=pose_csv_by_camera,
        status_by_camera=status_by_camera,
    )


def auto_pose_artifacts(discovery: DiscoveryResult, info: SessionInfo, artifacts_config: ArtifactsConfig) -> ArtifactsResult:
    """Auto mode: discover first; generate when missing and model is available."""

    meta = _get_metadata(info)

    # First attempt: discover for all cameras
    try:
        discovered = discover_pose_artifacts(discovery, info)
        # If discovery succeeded for required cameras, return.
        return discovered
    except IngestError as discover_error:
        logger.info(f"Auto artifacts: discovery failed; attempting generation. Reason: {discover_error}")

    # Generation path: only DLC supported
    return generate_pose_artifacts(discovery, info, artifacts_config)
