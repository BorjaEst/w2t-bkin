"""Happy path scenario: Complete session that should pass all validation.

This scenario represents a typical successful recording session:
- Single camera with matching TTL
- Exact frame/TTL count match
- Minimal jitter within budget
- Valid configuration
- All files present and valid

Use this scenario for:
- End-to-end pipeline testing
- Verifying that the pipeline works correctly
- Baseline performance testing
"""

from pathlib import Path
from typing import Optional

from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
from synthetic.session_synth import SyntheticSession, create_session


def make_session(
    root: Path,
    session_id: str = "happy-path-001",
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a happy path synthetic session.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        seed: Random seed for reproducibility
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with paths to all generated files

    Example:
        >>> from pathlib import Path
        >>> from synthetic.scenarios import happy_path
        >>> session = happy_path.make_session(
        ...     Path("temp/test"),
        ...     n_frames=100,
        ...     seed=42
        ... )
        >>> # Now run the pipeline with session.config_path and session.session_path
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="happy-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
                resolution=(320, 240),
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,  # Exact match
                start_time_s=0.0,
                period_s=1.0 / 30.0,  # 30 Hz
                jitter_s=0.0001,  # Minimal jitter (0.1ms)
            )
        ],
        with_bpod=False,
        with_pose=False,
        with_facemap=False,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_session_with_bpod(
    root: Path,
    session_id: str = "happy-path-bpod-001",
    n_frames: int = 100,
    n_trials: int = 10,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a happy path session with Bpod trial data.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        n_trials: Number of Bpod trials
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with paths to all generated files including Bpod
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="happy-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
                resolution=(320, 240),
            )
        ],
        ttls=[
            # Camera TTL: one pulse per frame
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0001,
            ),
            # Bpod sync TTL: one pulse per trial from Bpod's sync output (e.g., D1)
            # This is a SEPARATE TTL channel that records when Bpod outputs a sync pulse.
            SyntheticTTL(
                ttl_id="bpod_d1_ttl",
                pulse_count=n_trials,
                start_time_s=0.0,  # Will be adjusted to match Bpod trial timing
                period_s=1.0,  # Approximate spacing between trials
                jitter_s=0.001,
            ),
        ],
        with_bpod=True,
        bpod_trial_count=n_trials,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_session_with_pose(
    root: Path,
    session_id: str = "happy-path-pose-001",
    n_frames: int = 100,
    keypoints: Optional[list] = None,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a happy path session with pose tracking data.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        keypoints: List of keypoint names (uses defaults if None)
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with paths to all generated files including pose
    """
    if keypoints is None:
        keypoints = ["nose", "left_ear", "right_ear", "left_eye", "right_eye"]

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="happy-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
                resolution=(640, 480),
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0001,
            )
        ],
        with_pose=True,
        pose_keypoints=keypoints,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_session_with_facemap(
    root: Path,
    session_id: str = "happy-path-facemap-001",
    n_frames: int = 100,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a happy path session with facemap motion tracking.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with paths to all generated files including facemap
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="happy-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
                resolution=(640, 480),
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0001,
            )
        ],
        with_facemap=True,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_complete_session(
    root: Path,
    session_id: str = "happy-path-complete-001",
    n_frames: int = 100,
    n_trials: int = 10,
    keypoints: Optional[list] = None,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a complete happy path session with all modalities.

    Includes: video, TTL, Bpod, pose, and facemap data.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        n_trials: Number of Bpod trials
        keypoints: List of keypoint names (uses defaults if None)
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with paths to all generated files
    """
    if keypoints is None:
        keypoints = ["nose", "left_ear", "right_ear", "left_eye", "right_eye"]

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="happy-subject",
        experimenter="test-experimenter",
        date="2025-01-15",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=n_frames,
                fps=30.0,
                resolution=(640, 480),
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0001,
            )
        ],
        with_bpod=True,
        bpod_trial_count=n_trials,
        with_pose=True,
        pose_keypoints=keypoints,
        with_facemap=True,
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)
