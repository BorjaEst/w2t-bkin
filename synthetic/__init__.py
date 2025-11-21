"""Synthetic data helpers for W2T-BKIN.

Public API to generate minimal, valid synthetic inputs:
- Config TOML (config_synth)
- Session TOML (session_synth)
- TTL pulse files (ttl_synth)
- Video files (video_synth)
- High-level `build_raw_folder` to assemble a complete raw session folder
- High-level `build_interim_pose` to generate interim pose data

These utilities are intended for demos, tests, and quick E2E exercises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from .bpod_synth import BpodSynthOptions, write_bpod_mat_files_for_session
from .config_synth import SynthConfigOptions, build_config, write_config_toml
from .pose_synth import PoseH5Params, create_dlc_pose_h5
from .session_synth import SessionSynthOptions, build_session, write_session_toml
from .ttl_synth import TTLGenerationOptions, generate_and_write_ttls_for_session, generate_ttl_pulses, write_ttl_pulse_files
from .video_synth import VideoGenerationOptions, generate_video_files_for_session

__all__ = [
    # Config
    "SynthConfigOptions",
    "build_config",
    "write_config_toml",
    # Session
    "SessionSynthOptions",
    "build_session",
    "write_session_toml",
    # TTLs
    "TTLGenerationOptions",
    "generate_and_write_ttls_for_session",
    "generate_ttl_pulses",
    "write_ttl_pulse_files",
    # Videos
    "VideoGenerationOptions",
    "generate_video_files_for_session",
    # Pose
    "PoseH5Params",
    "create_dlc_pose_h5",
    # Bpod
    "BpodSynthOptions",
    "write_bpod_mat_files_for_session",
    # Result objects
    "RawSessionResult",
    "InterimPoseResult",
    # High-level builders
    "build_raw_folder",
    "build_interim_pose",
]


@dataclass(frozen=True)
class RawSessionResult:
    """Result object for raw session folder generation.

    Contains paths to all raw data artifacts (videos, TTLs, Bpod files).
    Raw data represents unprocessed sensor outputs and experimental metadata.

    Attributes
    ----------
    root_dir : Path
        Base output directory (e.g., "output/raw").
    session_dir : Path
        Session-specific directory containing all raw artifacts.
    config_path : Path
        Path to generated `config.toml`.
    session_path : Path
        Path to generated `session.toml` with session metadata.
    video_paths : List[Path]
        Paths to generated video files (all cameras, all segments).
    ttl_paths : List[Path]
        Paths to TTL timestamp files (all channels).
    bpod_paths : List[Path]
        Paths to Bpod .mat files with trial data.
    """

    root_dir: Path
    session_dir: Path
    config_path: Path
    session_path: Path
    video_paths: List[Path]
    ttl_paths: List[Path]
    bpod_paths: List[Path]


@dataclass(frozen=True)
class InterimPoseResult:
    """Result object for interim pose estimation data generation.

    Contains paths to processed pose estimation outputs (DLC/SLEAP H5 files).
    Interim data represents processed outputs derived from raw data.

    Attributes
    ----------
    root_dir : Path
        Base interim directory (e.g., "output/interim").
    session_dir : Path
        Session-specific directory for interim artifacts.
    pose_paths : List[Path]
        Paths to generated pose H5 files (one per camera).
    """

    root_dir: Path
    session_dir: Path
    pose_paths: List[Path]


def build_raw_folder(
    out_root: Union[str, Path],
    *,
    project_name: str = "synthetic-project",
    session_id: str = "Session-SYNTH-0001",
    camera_ids: Optional[List[str]] = None,
    ttl_ids: Optional[List[str]] = None,
    n_frames: int = 300,
    fps: float = 30.0,
    segments_per_camera: int = 1,
    ttl_rate_hz: Optional[float] = None,
    n_trials: int = 10,
    camera_start_delay_s: float = 0.0,
    bpod_start_delay_s: float = 0.0,
    bpod_sync_delay_s: float = 0.0,
    bpod_clock_jitter_ppm: float = 0.0,
    seed: int = 42,
) -> RawSessionResult:
    """Build a complete raw session folder with videos, TTLs, and Bpod files.

    Creates:
    - `config.toml` at `<out_root>/config.toml`.
    - Session folder `<out_root>/<session_id>/` with:
      - `session.toml`
      - `Video/` with synthetic video files per camera
      - `TTLs/` with TTL timestamp files per TTL channel
      - `Bpod/` with synthetic .mat files

    Timing offsets:
    - camera_start_delay_s: offset for camera TTL pulses (relative to t=0)
    - bpod_start_delay_s: offset for Bpod trial timestamps (relative to t=0)
    - bpod_sync_delay_s: delay of sync state within each Bpod trial
    - bpod_clock_jitter_ppm: clock drift in parts per million (positive = fast, negative = slow)
      Simulates Bpod internal clock running slightly faster/slower than TTL reference clock.
      Drift accumulates over time, causing offsets to change across session.

    Returns
    -------
    RawSessionResult
        Object containing paths to all generated raw artifacts.

    See Also
    --------
    build_interim_pose : Generate interim pose estimation data.

    Notes
    -----
    For interim data (pose estimation), use `build_interim_pose()` separately.
    This maintains proper separation between raw (videos) and interim (processed) data.
    """

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    session_dir = out_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Defaults
    camera_ids = camera_ids or ["cam0", "cam1"]
    ttl_ids = ttl_ids or ["ttl_sync"]

    # 1) Config
    cfg = build_config(
        options=SynthConfigOptions(
            project_name=project_name,
            raw_root=str(out_root),
            intermediate_root=str(out_root / "../interim"),
            output_root=str(out_root / "../processed"),
            metadata_file="session.toml",
            models_root="models",
        )
    )
    config_path = write_config_toml(out_root / "config.toml", cfg)

    # 2) Session (cameras + TTLs + bpod)
    session_opts = SessionSynthOptions(
        session_id=session_id,
        camera_ids=camera_ids,
        ttl_ids=ttl_ids,
        bpod_enabled=True,
        number_of_trial_types=1,
    )
    session_model = build_session(options=session_opts)
    session_path = write_session_toml(session_dir / "session.toml", session_model)

    # 3) Videos
    vid_opts = VideoGenerationOptions(
        frames_per_segment=max(1, int(n_frames)),
        segments_per_camera=max(1, int(segments_per_camera)),
        fps=fps,
        seed=seed,
    )
    videos_map = generate_video_files_for_session(session_model, session_dir, options=vid_opts)
    video_paths = [p for files in videos_map.values() for p in files]

    # 4) TTLs (one pulse per frame for camera TTL; one pulse per trial for Bpod sync TTL)
    ttl_rate = ttl_rate_hz if ttl_rate_hz is not None else fps
    # Camera TTL: starts at camera_start_delay_s
    camera_ttl_opts = TTLGenerationOptions(
        pulses_per_ttl=n_frames,
        rate_hz=ttl_rate,
        start_time_s=camera_start_delay_s,
        seed=seed,
    )
    # Bpod sync TTL: one pulse per trial
    # Must match the Bpod trial interval (default 2.0s in BpodSynthOptions.trial_interval_s)
    # Pulses occur at: bpod_start_delay_s + sync_delay_s, then +trial_interval, +trial_interval, ...
    bpod_trial_interval_s = 2.0  # Must match BpodSynthOptions default
    bpod_ttl_rate_hz = 1.0 / bpod_trial_interval_s  # 0.5 Hz for 2s intervals
    bpod_ttl_opts = TTLGenerationOptions(
        pulses_per_ttl=n_trials,
        rate_hz=bpod_ttl_rate_hz,
        start_time_s=bpod_start_delay_s + bpod_sync_delay_s,
        seed=seed + 1,
    )
    # Generate both: assume first TTL is camera, others are for Bpod sync (simplified)
    # In real scenario, session config defines which TTL is which
    ttl_ids_list = [ttl.id for ttl in session_model.TTLs]
    if len(ttl_ids_list) == 1:
        # Single TTL: assume camera
        ttl_map = generate_and_write_ttls_for_session(session_model, session_dir, options=camera_ttl_opts)
    else:
        # Multiple TTLs: first is camera, rest are Bpod sync
        camera_ttl_id = ttl_ids_list[0]
        bpod_ttl_id = ttl_ids_list[1] if len(ttl_ids_list) > 1 else None
        camera_pulses = generate_ttl_pulses([camera_ttl_id], options=camera_ttl_opts)
        bpod_pulses = generate_ttl_pulses([bpod_ttl_id], options=bpod_ttl_opts) if bpod_ttl_id else {}
        all_pulses = {**camera_pulses, **bpod_pulses}
        ttl_map = write_ttl_pulse_files(session_model, all_pulses, session_dir)
    ttl_paths = [p for files in ttl_map.values() for p in files]

    # 5) Bpod synthetic .mat files
    # Bpod trial timestamps start at bpod_start_delay_s
    # Sync signal occurs at bpod_sync_delay_s within each trial
    # Clock jitter simulates Bpod clock running faster/slower than reference
    bpod_opts = BpodSynthOptions(
        files=1,
        trials_per_file=n_trials,
        start_time_s=bpod_start_delay_s,
        trial_interval_s=2.0,
        trial_duration_s=1.5,
        sync_delay_s=bpod_sync_delay_s,
        clock_jitter_ppm=bpod_clock_jitter_ppm,
        seed=seed,
    )
    bpod_paths = write_bpod_mat_files_for_session(session_model, session_dir, options=bpod_opts)

    return RawSessionResult(
        root_dir=out_root.resolve(),
        session_dir=session_dir.resolve(),
        config_path=config_path.resolve(),
        session_path=session_path.resolve(),
        video_paths=[p.resolve() for p in video_paths],
        ttl_paths=[p.resolve() for p in ttl_paths],
        bpod_paths=[p.resolve() for p in bpod_paths],
    )


def build_interim_pose(
    interim_root: Union[str, Path],
    *,
    session_id: str,
    camera_ids: List[str],
    n_frames: int = 300,
    fps: float = 30.0,
    keypoints: Optional[List[str]] = None,
    confidence_mean: float = 0.95,
    confidence_std: float = 0.05,
    dropout_rate: float = 0.02,
    seed: int = 42,
) -> InterimPoseResult:
    """Build interim pose estimation data (DLC/SLEAP H5 files) for a synthetic session.

    Generates processed pose estimation outputs that would typically be produced
    by running DLC or SLEAP on raw video files. This simulates the interim data
    layer in the processing pipeline: raw → interim → output.

    Directory structure:
        <interim_root>/
        └── <session_id>/
            └── Pose/
                └── <camera_id>/
                    └── pose.h5

    Parameters
    ----------
    interim_root: Base directory for interim data (e.g., "output/interim")
    session_id: Session identifier (must match session in raw folder)
    camera_ids: List of camera IDs to generate pose data for
    n_frames: Number of frames (should match video frame count)
    fps: Frame rate (should match video fps)
    keypoints: List of keypoint names (default: ["nose", "left_ear", "right_ear"])
    confidence_mean: Mean confidence for synthetic pose data
    confidence_std: Standard deviation for confidence values
    dropout_rate: Fraction of keypoints to drop (simulates tracking failures)
    seed: Random seed for reproducible generation

    Returns
    -------
    List[Path]: Paths to generated H5 files (one per camera)
    """

    interim_root = Path(interim_root)
    session_dir = interim_root / session_id
    pose_dir = session_dir / "Pose"
    pose_paths = []

    keypoints = keypoints or ["nose", "left_ear", "right_ear"]

    for cam_id in camera_ids:
        cam_pose_dir = pose_dir / cam_id
        cam_pose_dir.mkdir(parents=True, exist_ok=True)

        # Use per-camera seed for variation across cameras
        cam_seed = seed + hash(cam_id) % 1000

        pose_params = PoseH5Params(
            keypoints=keypoints,
            n_frames=n_frames,
            fps=fps,
            confidence_mean=confidence_mean,
            confidence_std=confidence_std,
            dropout_rate=dropout_rate,
            seed=cam_seed,
        )

        h5_path = create_dlc_pose_h5(cam_pose_dir / "pose.h5", pose_params)
        pose_paths.append(h5_path)

    return InterimPoseResult(
        root_dir=interim_root.resolve(),
        session_dir=session_dir.resolve(),
        pose_paths=[p.resolve() for p in pose_paths],
    )
