"""Synthetic data helpers for W2T-BKIN.

Public API to generate minimal, valid synthetic inputs:
- Config TOML (config_synth)
- Session TOML (session_synth)
- TTL pulse files (ttl_synth)
- Video files (video_synth)
- High-level `build_raw_folder` to assemble a complete raw session folder

These utilities are intended for demos, tests, and quick E2E exercises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from .bpod_synth import BpodSynthOptions, write_bpod_mat_files_for_session
from .config_synth import SynthConfigOptions, build_config, write_config_toml
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
    # Bpod
    "BpodSynthOptions",
    "write_bpod_mat_files_for_session",
    # High-level builder
    "build_raw_folder",
]


@dataclass(frozen=True)
class RawSessionBuildResult:
    """Summary of generated synthetic raw session artifacts.

    Attributes
    ----------
    root_dir: Base output directory provided by the user.
    session_dir: Directory containing `session.toml` and raw artifacts.
    config_path: Path to generated `config.toml`.
    session_path: Path to generated `session.toml`.
    camera_video_paths: List of generated video files (all cameras).
    ttl_paths: List of generated TTL files across TTL channels.
    bpod_paths: List of (placeholder) Bpod .mat files.
    """

    root_dir: Path
    session_dir: Path
    config_path: Path
    session_path: Path
    camera_video_paths: List[Path]
    ttl_paths: List[Path]
    bpod_paths: List[Path]


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
) -> RawSessionBuildResult:
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

    Returns a `RawSessionBuildResult` with paths for convenience.
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
    camera_video_paths = [p for files in videos_map.values() for p in files]

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

    return RawSessionBuildResult(
        root_dir=out_root.resolve(),
        session_dir=session_dir.resolve(),
        config_path=config_path,
        session_path=session_path,
        camera_video_paths=[p.resolve() for p in camera_video_paths],
        ttl_paths=[p.resolve() for p in ttl_paths],
        bpod_paths=[p.resolve() for p in bpod_paths],
    )
