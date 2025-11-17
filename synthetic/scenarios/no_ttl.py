"""No TTL scenario: Session using nominal rate timebase (no TTL sync).

This scenario tests the pipeline's ability to operate without TTL
synchronization, using only the camera's nominal frame rate for timing.

Use this scenario for:
- Testing nominal_rate timebase mode
- Verifying pipeline works without TTL hardware
- Testing rate-based ImageSeries generation
"""

from pathlib import Path
from typing import Optional

from synthetic.models import SyntheticCamera, SyntheticSessionParams
from synthetic.session_synth import SyntheticSession, create_session


def make_session(
    root: Path,
    session_id: str = "no-ttl-001",
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a session without TTL synchronization.

    This session has cameras but no TTL channels, so it must use
    nominal_rate as the timebase source.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession without TTL files

    Example:
        >>> from pathlib import Path
        >>> from synthetic.scenarios import no_ttl
        >>> session = no_ttl.make_session(Path("temp/test"))
        >>> # Config should have timebase.source = "nominal_rate"
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="no-ttl-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id=None,  # No TTL
                frame_count=n_frames,
                fps=30.0,
                resolution=(320, 240),
            )
        ],
        ttls=[],  # No TTLs
        seed=seed,
    )

    session = create_session(root, params, use_ffmpeg=use_ffmpeg)

    # Update config to use nominal_rate timebase
    from synthetic.config_synth import create_config_toml

    create_config_toml(
        session.config_path,
        raw_root=session.raw_dir.parent,
        processed_root=root / "processed",
        temp_root=root / "temp",
        timebase_source="nominal_rate",  # No TTL sync
        timebase_mapping="nearest",
        timebase_ttl_id=None,
        jitter_budget_s=0.005,
    )

    return session


def make_multi_camera_session(
    root: Path,
    session_id: str = "no-ttl-multi-001",
    n_cameras: int = 3,
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a multi-camera session without TTL synchronization.

    This tests nominal rate timebase with multiple cameras, all using
    their own independent frame rates.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_cameras: Number of cameras
        n_frames: Number of frames per camera
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with multiple cameras, no TTLs
    """
    cameras = [
        SyntheticCamera(
            camera_id=f"cam{i}",
            ttl_id=None,
            frame_count=n_frames,
            fps=30.0,
            resolution=(320, 240),
        )
        for i in range(n_cameras)
    ]

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="no-ttl-multi-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=cameras,
        ttls=[],
        seed=seed,
    )

    session = create_session(root, params, use_ffmpeg=use_ffmpeg)

    # Update config to use nominal_rate timebase
    from synthetic.config_synth import create_config_toml

    create_config_toml(
        session.config_path,
        raw_root=session.raw_dir.parent,
        processed_root=root / "processed",
        temp_root=root / "temp",
        timebase_source="nominal_rate",
        timebase_mapping="nearest",
        timebase_ttl_id=None,
        jitter_budget_s=0.005,
    )

    return session
