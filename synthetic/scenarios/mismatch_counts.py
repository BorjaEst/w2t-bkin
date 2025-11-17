"""Mismatch counts scenario: Frame/TTL count mismatch beyond tolerance.

This scenario tests the verification logic that detects when video frame counts
don't match TTL pulse counts. The mismatch exceeds the configured tolerance,
triggering a verification failure.

Use this scenario for:
- Testing verification error handling
- Verifying abort logic when mismatch > tolerance
- Testing verification summary generation
"""

from pathlib import Path
from typing import Optional

from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
from synthetic.session_synth import SyntheticSession, create_session


def make_session(
    root: Path,
    session_id: str = "mismatch-001",
    n_frames: int = 100,
    n_pulses: int = 95,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a session with frame/TTL count mismatch.

    By default, creates a session where the camera has 100 frames but the TTL
    only has 95 pulses, resulting in a mismatch of 5 frames.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of video frames
        n_pulses: Number of TTL pulses (should differ from n_frames)
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with mismatched frame/pulse counts

    Example:
        >>> from pathlib import Path
        >>> from synthetic.scenarios import mismatch_counts
        >>> session = mismatch_counts.make_session(
        ...     Path("temp/test"),
        ...     n_frames=100,
        ...     n_pulses=95
        ... )
        >>> # Verification should fail with mismatch = 5
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="mismatch-subject",
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
                pulse_count=n_pulses,  # Mismatch!
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0,
            )
        ],
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)


def make_session_within_tolerance(
    root: Path,
    session_id: str = "mismatch-tolerable-001",
    n_frames: int = 100,
    mismatch: int = 2,
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a session with mismatch within tolerance.

    Creates a session where the mismatch is small enough to be within the
    configured tolerance (typically 5 frames). This should generate a warning
    but not fail verification.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of video frames
        mismatch: Number of frames/pulses to differ by (should be < tolerance)
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with small mismatch within tolerance
    """
    n_pulses = n_frames - mismatch

    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="tolerable-subject",
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
                pulse_count=n_pulses,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=0.0,
            )
        ],
        seed=seed,
    )

    return create_session(root, params, use_ffmpeg=use_ffmpeg)
