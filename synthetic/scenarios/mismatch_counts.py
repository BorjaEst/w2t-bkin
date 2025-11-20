"""Mismatch counts scenario: intentional frame/TTL count discrepancy.

Generates a session where video frame count differs from TTL pulse count
to test verification error handling and tolerance mechanisms.

Configuration:
- 1 camera (cam0)
- 1 TTL channel (cam0_ttl)
- Frame count != TTL pulse count (configurable mismatch)
- Tests verification logic and error reporting
"""

from pathlib import Path
from typing import Union

from synthetic import RawSessionBuildResult, build_raw_folder


def make_session(
    root: Union[str, Path],
    *,
    n_frames: int = 100,
    n_pulses: int = 95,
    fps: float = 30.0,
    seed: int = 42,
) -> RawSessionBuildResult:
    """Generate synthetic session with intentional frame/TTL count mismatch.

    Args:
        root: Output directory for session artifacts
        n_frames: Number of video frames
        n_pulses: Number of TTL pulses (typically < n_frames for mismatch)
        fps: Video frame rate
        seed: Random seed for deterministic generation

    Returns:
        RawSessionBuildResult with paths to config, session, videos, TTLs

    Example:
        >>> from synthetic.scenarios import mismatch_counts
        >>> # Generate 100 frames but only 95 TTL pulses
        >>> session = mismatch_counts.make_session(
        ...     "/tmp/test",
        ...     n_frames=100,
        ...     n_pulses=95
        ... )
        >>> # Verification should detect 5-pulse mismatch
    """
    # Calculate TTL rate to generate exact n_pulses
    # Duration = n_frames / fps
    # Rate = n_pulses / duration = n_pulses * fps / n_frames
    duration_s = n_frames / fps
    ttl_rate_hz = n_pulses / duration_s if duration_s > 0 else fps

    return build_raw_folder(
        out_root=root,
        project_name="mismatch-project",
        session_id="Session-Mismatch",
        camera_ids=["cam0"],
        ttl_ids=["cam0_ttl"],
        n_frames=n_frames,
        fps=fps,
        segments_per_camera=1,
        ttl_rate_hz=ttl_rate_hz,  # Adjusted rate for specific pulse count
        n_trials=10,
        camera_start_delay_s=0.0,
        bpod_start_delay_s=0.0,
        bpod_sync_delay_s=0.0,
        bpod_clock_jitter_ppm=0.0,
        seed=seed,
    )
