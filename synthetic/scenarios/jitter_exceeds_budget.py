"""Jitter exceeds budget scenario: TTL jitter exceeds configured budget.

This scenario tests the alignment logic that detects when TTL pulse timing
jitter exceeds the configured jitter budget. This should trigger an abort
before NWB assembly as per requirement A17.

Use this scenario for:
- Testing jitter budget enforcement
- Verifying abort logic before NWB assembly
- Testing alignment stats generation
"""

from pathlib import Path
from typing import Optional

from synthetic.models import SyntheticCamera, SyntheticSessionParams, SyntheticTTL
from synthetic.session_synth import SyntheticSession, create_session


def make_session(
    root: Path,
    session_id: str = "jitter-exceeds-001",
    n_frames: int = 100,
    jitter_s: float = 0.010,  # 10ms jitter
    budget_s: float = 0.005,  # 5ms budget
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a session with jitter exceeding the configured budget.

    By default, creates a session where TTL jitter is 10ms but the budget
    is only 5ms, causing a JitterExceedsBudgetError during alignment.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        jitter_s: TTL jitter in seconds (should exceed budget_s)
        budget_s: Configured jitter budget in seconds
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with excessive jitter

    Example:
        >>> from pathlib import Path
        >>> from synthetic.scenarios import jitter_exceeds_budget
        >>> session = jitter_exceeds_budget.make_session(
        ...     Path("temp/test"),
        ...     jitter_s=0.010,  # 10ms
        ...     budget_s=0.005   # 5ms budget
        ... )
        >>> # Alignment should fail with JitterExceedsBudgetError
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="jitter-subject",
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
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=jitter_s,  # Excessive jitter
            )
        ],
        seed=seed,
    )

    # Note: The budget is set in config.toml, not in params
    # This scenario needs to override the config generation
    session = create_session(root, params, use_ffmpeg=use_ffmpeg)

    # Update config.toml to set the stricter budget
    # (re-generate config with custom budget)
    from synthetic.config_synth import create_config_toml

    create_config_toml(
        session.config_path,
        raw_root=session.raw_dir.parent,
        processed_root=root / "processed",
        temp_root=root / "temp",
        timebase_source="ttl",
        timebase_mapping="nearest",
        timebase_ttl_id="cam0_ttl",
        jitter_budget_s=budget_s,  # Strict budget
    )

    return session


def make_session_within_budget(
    root: Path,
    session_id: str = "jitter-ok-001",
    n_frames: int = 100,
    jitter_s: float = 0.002,  # 2ms jitter
    budget_s: float = 0.005,  # 5ms budget
    seed: int = 42,
    use_ffmpeg: Optional[bool] = None,
) -> SyntheticSession:
    """Create a session with jitter within the configured budget.

    This scenario has jitter but stays within the budget, so alignment
    should succeed.

    Args:
        root: Root directory where session should be created
        session_id: Session identifier
        n_frames: Number of frames/pulses
        jitter_s: TTL jitter in seconds (should be < budget_s)
        budget_s: Configured jitter budget in seconds
        seed: Random seed
        use_ffmpeg: Whether to use ffmpeg (None = auto-detect)

    Returns:
        SyntheticSession with acceptable jitter
    """
    params = SyntheticSessionParams(
        session_id=session_id,
        subject_id="jitter-ok-subject",
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
                pulse_count=n_frames,
                start_time_s=0.0,
                period_s=1.0 / 30.0,
                jitter_s=jitter_s,  # Acceptable jitter
            )
        ],
        seed=seed,
    )

    session = create_session(root, params, use_ffmpeg=use_ffmpeg)

    # Update config with specified budget
    from synthetic.config_synth import create_config_toml

    create_config_toml(
        session.config_path,
        raw_root=session.raw_dir.parent,
        processed_root=root / "processed",
        temp_root=root / "temp",
        timebase_source="ttl",
        timebase_mapping="nearest",
        timebase_ttl_id="cam0_ttl",
        jitter_budget_s=budget_s,
    )

    return session
