"""Happy path scenario: perfect alignment, minimal configuration.

Generates a single camera with matching TTL pulses for ideal synchronization.
Use this for testing nominal workflows without edge cases.

Configuration:
- 1 camera (cam0)
- 1 TTL channel (cam0_ttl)
- Frame count == TTL pulse count (perfect alignment)
- TTL timebase provider (config.timebase.source = "ttl")
"""

from pathlib import Path
from typing import Union

from synthetic import RawSessionBuildResult, build_raw_folder


def make_session(
    root: Union[str, Path],
    *,
    n_frames: int = 64,
    fps: float = 30.0,
    seed: int = 42,
) -> RawSessionBuildResult:
    """Generate happy path synthetic session with perfect frame/TTL alignment.

    Args:
        root: Output directory for session artifacts
        n_frames: Number of video frames (matches TTL pulse count)
        fps: Video frame rate
        seed: Random seed for deterministic generation

    Returns:
        RawSessionBuildResult with paths to config, session, videos, TTLs

    Example:
        >>> from synthetic.scenarios import happy_path
        >>> session = happy_path.make_session("/tmp/test", n_frames=100)
        >>> assert session.config_path.exists()
        >>> assert len(session.camera_video_paths) == 1
    """
    return build_raw_folder(
        out_root=root,
        project_name="happy-path-project",
        session_id="Session-Happy-Path",
        camera_ids=["cam0"],
        ttl_ids=["cam0_ttl"],
        n_frames=n_frames,
        fps=fps,
        segments_per_camera=1,
        ttl_rate_hz=fps,  # Match TTL rate to video FPS for perfect alignment
        n_trials=10,
        camera_start_delay_s=0.0,
        bpod_start_delay_s=0.0,
        bpod_sync_delay_s=0.0,
        bpod_clock_jitter_ppm=0.0,
        seed=seed,
    )
