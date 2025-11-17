"""Orchestrate complete synthetic session generation.

This module provides high-level functions to generate complete synthetic session
directory trees that can be used for end-to-end testing of the W2T-BKIN pipeline.

Features:
---------
- Generate complete session directory structure
- Create all required files (videos, TTLs, configs)
- Support for optional modalities (Bpod, pose, facemap)
- Return typed session paths for easy test access

Requirements Coverage:
----------------------
- FR-1/2/3: Complete session structure for ingest testing
- NFR-4: Fast session generation for tests
"""

from pathlib import Path
from typing import Optional

from synthetic.config_synth import create_config_toml, create_session_toml
from synthetic.models import SyntheticCamera, SyntheticSession, SyntheticSessionParams
from synthetic.ttl_synth import create_ttl_file
from synthetic.video_synth import check_ffmpeg_available, create_stub_video_file, create_video_file


def create_session(
    root: Path,
    params: SyntheticSessionParams,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a complete synthetic session with all files.

    This is the main entry point for generating synthetic test sessions.
    It creates:
    - Directory structure matching raw data layout
    - config.toml and session.toml
    - Video files for each camera
    - TTL files for each TTL channel
    - Optional: Bpod, pose, facemap files

    Args:
        root: Root directory where session should be created
        params: Session generation parameters
        use_ffmpeg: Whether to use ffmpeg for video generation
                   (None = auto-detect, True = require, False = use stubs)

    Returns:
        SyntheticSession with paths to all generated files

    Example:
        >>> from pathlib import Path
        >>> from synthetic.models import SyntheticSessionParams, SyntheticCamera, SyntheticTTL
        >>> params = SyntheticSessionParams(
        ...     session_id="test-001",
        ...     cameras=[SyntheticCamera(camera_id="cam0", ttl_id="cam0_ttl")],
        ...     ttls=[SyntheticTTL(ttl_id="cam0_ttl", pulse_count=100)],
        ...     seed=42
        ... )
        >>> session = create_session(Path("temp/test_sessions"), params)
        >>> print(session.config_path)
        >>> print(session.camera_video_paths)
    """
    # Determine video generation strategy
    if use_ffmpeg is None:
        use_ffmpeg = check_ffmpeg_available()
    elif use_ffmpeg and not check_ffmpeg_available():
        raise RuntimeError("ffmpeg is required but not available on system")

    # Create directory structure
    root.mkdir(parents=True, exist_ok=True)
    raw_dir = root / "raw" / params.session_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    processed_dir = root / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = root / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for different data types
    video_dir = raw_dir / "Video"
    video_dir.mkdir(parents=True, exist_ok=True)

    ttl_dir = raw_dir / "TTLs"
    ttl_dir.mkdir(parents=True, exist_ok=True)

    bpod_dir = raw_dir / "Bpod"
    if params.with_bpod:
        bpod_dir.mkdir(parents=True, exist_ok=True)

    # Initialize result
    session = SyntheticSession(
        root_dir=root,
        raw_dir=raw_dir,
        config_path=root / "config.toml",
        session_path=raw_dir / "session.toml",
    )

    # Generate video files for each camera
    video_files_per_camera = {}
    for camera in params.cameras:
        video_filename = f"{camera.camera_id}_test_video.mp4"
        video_path = video_dir / video_filename

        if use_ffmpeg:
            create_video_file(video_path, camera, seed=params.seed)
        else:
            create_stub_video_file(video_path, frame_count=camera.frame_count)

        session.camera_video_paths[camera.camera_id] = [video_path]
        video_files_per_camera[camera.camera_id] = [f"Video/{video_filename}"]

    # Generate TTL files
    ttl_files_per_ttl = {}
    bpod_sync_timestamps = None  # Will hold Bpod sync pulse times if Bpod is present

    # Generate Bpod files first if requested, so we can get sync pulse times
    bpod_files = None
    if params.with_bpod:
        from synthetic.bpod_synth import create_bpod_mat_file

        bpod_filename = f"{params.session_id}_bpod_data.mat"
        bpod_path = bpod_dir / bpod_filename

        # Create actual Bpod .mat file and get sync pulse timestamps
        _, bpod_sync_timestamps = create_bpod_mat_file(
            bpod_path,
            n_trials=params.bpod_trial_count,
            seed=params.seed,
        )

        session.bpod_path = bpod_path
        bpod_files = [f"Bpod/{bpod_filename}"]

    # Now generate TTL files (including Bpod sync TTL if we have timestamps)
    for ttl in params.ttls:
        ttl_filename = f"{ttl.ttl_id}.txt"
        ttl_path = ttl_dir / ttl_filename

        # Special handling for Bpod sync TTL: use actual Bpod sync times
        if ttl.ttl_id == "bpod_d1_ttl" and bpod_sync_timestamps:
            from synthetic.ttl_synth import create_ttl_file_from_timestamps

            create_ttl_file_from_timestamps(ttl_path, bpod_sync_timestamps)
        else:
            create_ttl_file(ttl_path, ttl, seed=params.seed)

        session.ttl_paths[ttl.ttl_id] = ttl_path
        ttl_files_per_ttl[ttl.ttl_id] = f"TTLs/{ttl_filename}"

    # Generate pose files if requested
    if params.with_pose:
        from synthetic.pose_synth import PoseParams, create_dlc_pose_csv

        pose_dir = raw_dir / "Pose"
        pose_dir.mkdir(parents=True, exist_ok=True)

        # Get frame count from first camera
        n_frames = params.cameras[0].frame_count if params.cameras else 100

        # Use provided keypoints or defaults
        keypoints = params.pose_keypoints or ["nose", "left_ear", "right_ear"]

        pose_params = PoseParams(
            keypoints=keypoints,
            n_frames=n_frames,
            image_width=params.cameras[0].resolution[0] if params.cameras else 640,
            image_height=params.cameras[0].resolution[1] if params.cameras else 480,
        )

        pose_filename = f"{params.session_id}_pose.csv"
        pose_path = pose_dir / pose_filename

        create_dlc_pose_csv(pose_path, pose_params, seed=params.seed)

        session.pose_path = pose_path

    # Generate facemap files if requested
    if params.with_facemap:
        from synthetic.facemap_synth import FacemapParams, create_facemap_output

        facemap_dir = raw_dir / "Facemap"
        facemap_dir.mkdir(parents=True, exist_ok=True)

        # Get frame count and resolution from first camera
        n_frames = params.cameras[0].frame_count if params.cameras else 100
        fps = params.cameras[0].fps if params.cameras else 30.0

        facemap_params = FacemapParams(
            n_frames=n_frames,
            image_width=params.cameras[0].resolution[0] if params.cameras else 640,
            image_height=params.cameras[0].resolution[1] if params.cameras else 480,
            sample_rate=fps,
        )

        facemap_filename = f"{params.session_id}_facemap.npy"
        facemap_path = facemap_dir / facemap_filename

        create_facemap_output(facemap_path, facemap_params, seed=params.seed)

        session.facemap_path = facemap_path

    # Determine timebase configuration
    timebase_ttl_id = None
    if params.ttls:
        # Use first TTL as timebase by default
        timebase_ttl_id = params.ttls[0].ttl_id

    # Create config.toml
    create_config_toml(
        session.config_path,
        raw_root=raw_dir.parent,
        processed_root=processed_dir,
        temp_root=temp_dir,
        timebase_source="ttl" if timebase_ttl_id else "nominal_rate",
        timebase_mapping="nearest",
        timebase_ttl_id=timebase_ttl_id,
        jitter_budget_s=0.005,
    )

    # Create session.toml
    create_session_toml(
        session.session_path,
        params=params,
        cameras=params.cameras,
        ttls=params.ttls,
        video_files_per_camera=video_files_per_camera,
        ttl_files_per_ttl=ttl_files_per_ttl,
        bpod_files=bpod_files,
    )

    return session


def create_minimal_session(
    root: Path,
    session_id: str = "test-minimal",
    n_frames: int = 64,
    seed: int = 42,
) -> SyntheticSession:
    """Create a minimal synthetic session for quick tests.

    This is a convenience function that creates a single-camera session
    with matching TTL, suitable for basic pipeline testing.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        seed: Random seed

    Returns:
        SyntheticSession with paths to all generated files

    Example:
        >>> from pathlib import Path
        >>> session = create_minimal_session(Path("temp/test"), n_frames=100)
    """
    from synthetic.models import SyntheticTTL

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="test-subject",
        experimenter="test-experimenter",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,
                period_s=1.0 / 30.0,
            )
        ],
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=False)
