"""No TTL scenario: camera-only with nominal timebase.

Generates a session with video data but no TTL synchronization signals.
Tests nominal rate timebase provider and camera-only workflows.

Configuration:
- 1 camera (cam0)
- 0 TTL channels
- Nominal timebase provider (config.timebase.source = "nominal_rate")
- Camera references "none" TTL (schema requirement)
"""

from pathlib import Path
from typing import Union

from synthetic import RawSessionBuildResult
from synthetic.config_synth import SynthConfigOptions, write_config_toml
from synthetic.session_synth import SessionSynthOptions, build_session, write_session_toml
from synthetic.video_synth import VideoGenerationOptions, generate_video_files_for_session


def make_session(
    root: Union[str, Path],
    *,
    n_frames: int = 64,
    fps: float = 30.0,
    seed: int = 42,
) -> RawSessionBuildResult:
    """Generate synthetic session with camera but no TTL synchronization.

    Args:
        root: Output directory for session artifacts
        n_frames: Number of video frames
        fps: Video frame rate
        seed: Random seed for deterministic generation

    Returns:
        RawSessionBuildResult with paths to config, session, videos (no TTL files)

    Example:
        >>> from synthetic.scenarios import no_ttl
        >>> session = no_ttl.make_session("/tmp/test", n_frames=100)
        >>> assert len(session.camera_video_paths) == 1
        >>> assert len(session.ttl_paths) == 0  # No TTL files generated
    """
    root = Path(root)
    session_id = "Session-No-TTL"
    session_dir = root / session_id

    # Create config with nominal_rate timebase
    config_opts = SynthConfigOptions(
        project_name="no-ttl-project",
        raw_root=str(root),
        timebase_source="nominal_rate",  # No TTL, use camera FPS
        timebase_mapping="nearest",
    )
    config_path = write_config_toml(root / "config.toml", config_opts)

    # Create session with camera but no TTL reference
    session_opts = SessionSynthOptions(
        session_id=session_id,
        camera_ids=["cam0"],
        ttl_ids=[],  # No TTL channels
        bpod_enabled=False,  # No Bpod for simplicity
    )
    session_model = build_session(options=session_opts)

    # Manually set camera ttl_id to "none" (schema requirement for no TTL)
    session_model = session_model.model_copy(update={"cameras": [camera.model_copy(update={"ttl_id": "none"}) for camera in session_model.cameras]})

    session_path = write_session_toml(session_dir / "session.toml", session_model)

    # Generate video files
    video_opts = VideoGenerationOptions(
        n_frames=n_frames,
        fps=fps,
        width=640,
        height=480,
        seed=seed,
    )
    video_paths = generate_video_files_for_session(
        session_dir=session_dir,
        session=session_model,
        options=video_opts,
    )

    return RawSessionBuildResult(
        root_dir=root,
        session_dir=session_dir,
        config_path=config_path,
        session_path=session_path,
        camera_video_paths=video_paths,
        ttl_paths=[],  # No TTL files
        bpod_paths=[],  # No Bpod files
    )
