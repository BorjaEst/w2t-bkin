"""Multi-camera scenario: multiple synchronized cameras.

Generates a session with N cameras, each with its own TTL channel for
independent synchronization. Tests multi-camera workflows and alignment.

Configuration:
- N cameras (cam0, cam1, ..., camN-1)
- N TTL channels (cam0_ttl, cam1_ttl, ..., camN-1_ttl)
- Each camera perfectly aligned with its corresponding TTL
- Tests multi-camera coordination and parallel processing
"""

from pathlib import Path
from typing import Union

from synthetic import RawSessionBuildResult, build_raw_folder


def make_session(
    root: Union[str, Path],
    *,
    n_cameras: int = 3,
    n_frames: int = 64,
    fps: float = 30.0,
    seed: int = 42,
) -> RawSessionBuildResult:
    """Generate synthetic session with multiple synchronized cameras.

    Args:
        root: Output directory for session artifacts
        n_cameras: Number of cameras (each gets its own TTL channel)
        n_frames: Number of video frames per camera
        fps: Video frame rate (same for all cameras)
        seed: Random seed for deterministic generation

    Returns:
        RawSessionBuildResult with paths to config, session, videos, TTLs

    Example:
        >>> from synthetic.scenarios import multi_camera
        >>> session = multi_camera.make_session(
        ...     "/tmp/test",
        ...     n_cameras=3,
        ...     n_frames=100
        ... )
        >>> assert len(session.camera_video_paths) == 3
        >>> assert len(session.ttl_paths) == 3
    """
    # Generate camera IDs: cam0, cam1, cam2, ...
    camera_ids = [f"cam{i}" for i in range(n_cameras)]

    # Generate TTL IDs: cam0_ttl, cam1_ttl, cam2_ttl, ...
    ttl_ids = [f"cam{i}_ttl" for i in range(n_cameras)]

    return build_raw_folder(
        out_root=root,
        project_name="multi-camera-project",
        session_id="Session-Multi-Camera",
        camera_ids=camera_ids,
        ttl_ids=ttl_ids,
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
