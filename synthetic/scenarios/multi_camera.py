"""Multi-camera scenario: Multiple cameras with different TTL channels.

This scenario tests the pipeline's ability to handle multiple cameras,
each with its own TTL synchronization channel.

Use this scenario for:
- Testing multi-camera sessions
- Verifying TTL cross-reference validation
- Testing independent camera timing
"""

from pathlib import Path
from typing import List, Optional

from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
from synthetic.session_synth import SyntheticSession, create_session


def make_session(
    root: Path,
    session_id: str = "multi-camera-001",
    n_cameras: int = 3,
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a multi-camera session with separate TTL channels.

    Creates a session where each camera has its own TTL channel for
    independent synchronization.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_cameras: Number of cameras
        n_frames: Number of frames per camera
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with multiple cameras and TTLs

    Example:
        >>> from pathlib import Path
        >>> from synthetic.scenarios import multi_camera
        >>> session = multi_camera.make_session(
        ...     Path("temp/test"),
        ...     n_cameras=3
        ... )
        >>> # Session should have 3 cameras and 3 TTL channels
    """
    cameras: List[SyntheticCamera] = []
    ttls: List[SyntheticTTL] = []

    for i in range(n_cameras):
        camera_id = f"cam{i}"
        ttl_id = f"cam{i}_ttl"

        cameras.append(
            SyntheticCamera(
                camera_id=camera_id,
                ttl_id=ttl_id,
                frame_count=n_frames,
                fps=30.0,
                resolution=(320, 240),
            )
        )

        ttls.append(
            SyntheticTTL(
                ttl_id=ttl_id,
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0001,
            )
        )

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="multi-cam-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=cameras,
        ttls=ttls,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_session_shared_ttl(
    root: Path,
    session_id: str = "multi-camera-shared-001",
    n_cameras: int = 3,
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a multi-camera session with one shared TTL channel.

    Creates a session where all cameras share a single TTL channel for
    common synchronization.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_cameras: Number of cameras
        n_frames: Number of frames per camera
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with multiple cameras sharing one TTL
    """
    cameras: List[SyntheticCamera] = []

    for i in range(n_cameras):
        cameras.append(
            SyntheticCamera(
                camera_id=f"cam{i}",
                ttl_id="shared_ttl",  # All cameras use same TTL
                frame_count=n_frames,
                fps=30.0,
                resolution=(320, 240),
            )
        )

    # Only one TTL for all cameras
    ttls = [
        SyntheticTTL(
            ttl_id="shared_ttl",
            pulse_count=n_frames,
            start_time_s=0.0,
            period_s=1.0 / 30.0,
            jitter_s=0.0001,
        )
    ]

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="multi-cam-shared-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=cameras,
        ttls=ttls,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)
