"""Mock TTL signal generation from DeepLabCut pose data.

Generates synthetic TTL pulse sequences from pose estimation data by detecting
events in tracked body part movements. Designed for testing, validation, and
synthetic pipeline scenarios where TTL signals need to be derived from behavioral
tracking data.

Features:
---------
- **Likelihood-based detection**: Threshold-based signal generation from keypoint confidence
- **Duration filtering**: Minimum duration requirements for valid signal phases
- **Frame-to-time conversion**: Automatic FPS-based timestamp generation
- **Flexible triggering**: Support for ON/OFF transitions, state changes, and custom predicates
- **TTL file format**: Compatible with w2t_bkin.ttl loader (one timestamp per line)

Use Cases:
----------
1. Generate trial light signals from tracked LED positions
2. Create behavioral event markers from pose kinematics
3. Produce synthetic TTL data for end-to-end pipeline testing
4. Validate synchronization logic with known ground truth

TTL File Format:
----------------
One floating-point timestamp per line (seconds), sorted ascending:

    0.0000
    2.0000
    4.0000
    ...

Example:
--------
>>> from pathlib import Path
>>> from w2t_bkin.sync.ttl_mock import (
...     TTLMockOptions,
...     generate_ttl_from_dlc_likelihood,
...     write_ttl_timestamps
... )
>>>
>>> # Generate TTL pulses from trial_light likelihood
>>> h5_path = Path("pose_output.h5")
>>> options = TTLMockOptions(
...     bodypart="trial_light",
...     likelihood_threshold=0.99,
...     min_duration_frames=301,
...     fps=150.0
... )
>>> timestamps = generate_ttl_from_dlc_likelihood(h5_path, options)
>>> print(f"Generated {len(timestamps)} TTL pulses")
>>>
>>> # Write to TTL file
>>> output_path = Path("TTLs/trial_light.txt")
>>> write_ttl_timestamps(timestamps, output_path)

Integration with Pipeline:
--------------------------
>>> from w2t_bkin.ttl import get_ttl_pulses
>>> from w2t_bkin.config import load_session
>>>
>>> # Generate mock TTL from pose data
>>> generate_and_write_ttl_from_pose(
...     h5_path=session_dir / "pose.h5",
...     output_path=session_dir / "TTLs/ttl_sync.txt",
...     options=TTLMockOptions(bodypart="trial_light", ...)
... )
>>>
>>> # Load in pipeline
>>> session = load_session(session_dir / "metadata.toml")
>>> pulses = get_ttl_pulses(session)
>>> print(len(pulses['ttl_sync']))  # Matches generated count

Requirements:
-------------
- pandas (for HDF5 reading)
- numpy (for numerical operations)
- Python 3.10+

See Also:
---------
- synthetic.ttl_synth: Pure synthetic TTL generation with deterministic RNG
- w2t_bkin.sync.ttl: TTL pulse loading and validation
- w2t_bkin.ttl: TTL file loading and EventsTable conversion
- w2t_bkin.ingest.pose: DLC pose data import
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from w2t_bkin.exceptions import PoseError

logger = logging.getLogger(__name__)


class TTLMockOptions(BaseModel):
    """Configuration for generating mock TTL signals from pose data.

    Attributes:
        bodypart: Name of the body part to track (must match DLC keypoint name)
        likelihood_threshold: Minimum confidence score for signal ON state (0-1)
        min_duration_frames: Minimum number of consecutive frames for valid signal
        fps: Camera frame rate for converting frame indices to timestamps
        transition_type: Type of signal transition to detect
            - 'rising': Detect OFF→ON transitions (signal start)
            - 'falling': Detect ON→OFF transitions (signal end)
            - 'both': Detect both transitions
        start_time_offset_s: Time offset to add to all timestamps (seconds)
        filter_consecutive: If True, only keep first pulse in consecutive groups
    """

    bodypart: str = Field(..., description="DLC body part name to track")
    likelihood_threshold: float = Field(default=0.99, ge=0.0, le=1.0, description="Minimum confidence threshold")
    min_duration_frames: int = Field(default=1, ge=1, description="Minimum frames for valid signal phase")
    fps: float = Field(default=30.0, gt=0.0, description="Camera frame rate (Hz)")
    transition_type: str = Field(default="rising", pattern="^(rising|falling|both)$", description="Transition detection mode")
    start_time_offset_s: float = Field(default=0.0, description="Time offset for all timestamps (s)")
    filter_consecutive: bool = Field(default=False, description="Keep only first pulse in consecutive groups")

    @field_validator("bodypart")
    @classmethod
    def bodypart_not_empty(cls, v: str) -> str:
        """Validate bodypart is not empty."""
        if not v or not v.strip():
            raise ValueError("bodypart must be a non-empty string")
        return v.strip()


def load_dlc_likelihood_series(h5_path: Path, bodypart: str, scorer: Optional[str] = None) -> pd.Series:
    """Load likelihood time series for a specific body part from DLC H5 file.

    Args:
        h5_path: Path to DeepLabCut H5 output file
        bodypart: Name of body part to extract
        scorer: Optional scorer name (auto-detected if None)

    Returns:
        Pandas Series with frame indices and likelihood values

    Raises:
        PoseError: If file not found, format invalid, or bodypart missing
    """
    if not h5_path.exists():
        raise PoseError(f"DLC H5 file not found: {h5_path}")

    try:
        df = pd.read_hdf(h5_path, "df_with_missing")
    except (KeyError, OSError, ValueError) as e:
        raise PoseError(f"Failed to read DLC H5 file {h5_path}: {e}") from e

    # Validate MultiIndex structure
    if not isinstance(df.columns, pd.MultiIndex) or df.columns.nlevels != 3:
        raise PoseError(f"Invalid DLC format: expected 3-level MultiIndex, got {type(df.columns)}")

    # Auto-detect scorer if not provided
    if scorer is None:
        scorer = df.columns.get_level_values(0)[0]
        logger.debug(f"Auto-detected scorer: {scorer}")

    # Check if bodypart exists
    bodyparts = df.columns.get_level_values(1).unique()
    if bodypart not in bodyparts:
        raise PoseError(f"Body part '{bodypart}' not found. Available: {list(bodyparts)}")

    # Extract likelihood column
    try:
        likelihood = df[(scorer, bodypart, "likelihood")]
    except KeyError as e:
        raise PoseError(f"Failed to extract likelihood for '{bodypart}': {e}") from e

    return likelihood


def detect_signal_transitions(
    signal: pd.Series,
    transition_type: str = "rising",
) -> Tuple[List[int], List[int]]:
    """Detect rising and/or falling edge transitions in a boolean signal.

    Args:
        signal: Boolean series indicating signal state (True=ON, False=OFF)
        transition_type: Type of transitions to detect ('rising', 'falling', 'both')

    Returns:
        Tuple of (onsets, offsets) frame index lists
            - onsets: Frame indices where signal transitions OFF→ON
            - offsets: Frame indices where signal transitions ON→OFF

    Example:
        >>> signal = pd.Series([False, False, True, True, False, True])
        >>> onsets, offsets = detect_signal_transitions(signal, 'rising')
        >>> print(onsets)  # [2, 5]
        >>> print(offsets)  # [4]
    """
    # Compute transitions using shift
    prev_signal = signal.shift(1, fill_value=False)

    onsets = []
    offsets = []

    if transition_type in ("rising", "both"):
        # Rising edge: previous=False AND current=True
        rising_mask = (~prev_signal) & signal
        onsets = signal.index[rising_mask].tolist()

    if transition_type in ("falling", "both"):
        # Falling edge: previous=True AND current=False
        falling_mask = prev_signal & (~signal)
        offsets = signal.index[falling_mask].tolist()

    return onsets, offsets


def filter_by_duration(
    onsets: List[int],
    offsets: List[int],
    min_duration_frames: int,
) -> Tuple[List[int], List[int]]:
    """Filter signal phases by minimum duration requirement.

    Args:
        onsets: Frame indices of signal ON transitions
        offsets: Frame indices of signal OFF transitions
        min_duration_frames: Minimum number of frames for valid phase

    Returns:
        Tuple of (filtered_onsets, filtered_offsets) with only valid phases

    Example:
        >>> onsets = [10, 50, 100]
        >>> offsets = [15, 55, 400]  # Durations: 5, 5, 300
        >>> filtered = filter_by_duration(onsets, offsets, min_duration_frames=10)
        >>> print(filtered[0])  # [100]
        >>> print(filtered[1])  # [400]
    """
    if not onsets or not offsets:
        return [], []

    # Ensure we have matching pairs
    min_len = min(len(onsets), len(offsets))
    onsets = onsets[:min_len]
    offsets = offsets[:min_len]

    # Calculate durations
    durations = [off - on for on, off in zip(onsets, offsets)]

    # Filter by minimum duration
    valid_indices = [i for i, dur in enumerate(durations) if dur >= min_duration_frames]
    filtered_onsets = [onsets[i] for i in valid_indices]
    filtered_offsets = [offsets[i] for i in valid_indices]

    return filtered_onsets, filtered_offsets


def frames_to_timestamps(frame_indices: List[int], fps: float, offset_s: float = 0.0) -> List[float]:
    """Convert frame indices to timestamps in seconds.

    Args:
        frame_indices: List of frame indices (0-based)
        fps: Frame rate in frames per second
        offset_s: Time offset to add to all timestamps

    Returns:
        List of timestamps in seconds

    Example:
        >>> frames = [0, 150, 300]
        >>> timestamps = frames_to_timestamps(frames, fps=150.0)
        >>> print(timestamps)  # [0.0, 1.0, 2.0]
    """
    if not frame_indices:
        return []

    timestamps = [frame / fps + offset_s for frame in frame_indices]
    return timestamps


def generate_ttl_from_dlc_likelihood(
    h5_path: Path,
    options: TTLMockOptions,
    scorer: Optional[str] = None,
) -> List[float]:
    """Generate mock TTL timestamps from DLC likelihood data.

    Main entry point for likelihood-based TTL generation. Loads pose data,
    applies threshold and duration filters, and converts to timestamps.

    Args:
        h5_path: Path to DeepLabCut H5 output file
        options: Configuration for TTL generation
        scorer: Optional DLC scorer name (auto-detected if None)

    Returns:
        List of TTL pulse timestamps in seconds (sorted)

    Raises:
        PoseError: If file not found, format invalid, or bodypart missing

    Example:
        >>> options = TTLMockOptions(
        ...     bodypart="trial_light",
        ...     likelihood_threshold=0.99,
        ...     min_duration_frames=301,
        ...     fps=150.0,
        ...     transition_type="rising"
        ... )
        >>> timestamps = generate_ttl_from_dlc_likelihood(Path("pose.h5"), options)
    """
    logger.info(f"Generating TTL from DLC pose data: {h5_path}")
    logger.debug(f"Options: bodypart={options.bodypart}, threshold={options.likelihood_threshold}, " f"min_duration={options.min_duration_frames}, fps={options.fps}")

    # Load likelihood series
    likelihood = load_dlc_likelihood_series(h5_path, options.bodypart, scorer)
    logger.debug(f"Loaded {len(likelihood)} frames, mean likelihood: {likelihood.mean():.3f}")

    # Create boolean signal from threshold
    signal = likelihood >= options.likelihood_threshold
    high_conf_count = signal.sum()
    logger.debug(f"Frames above threshold: {high_conf_count} ({100*high_conf_count/len(signal):.1f}%)")

    # Detect transitions
    # For duration filtering, we always need both onsets and offsets
    if options.min_duration_frames > 1:
        onsets, offsets = detect_signal_transitions(signal, "both")
        logger.debug(f"Detected {len(onsets)} onsets, {len(offsets)} offsets (for duration filtering)")
        onsets, offsets = filter_by_duration(onsets, offsets, options.min_duration_frames)
        logger.debug(f"After duration filter: {len(onsets)} valid phases")
    else:
        onsets, offsets = detect_signal_transitions(signal, options.transition_type)
        logger.debug(f"Detected {len(onsets)} onsets, {len(offsets)} offsets")

    # Select timestamps based on transition type
    if options.transition_type == "rising":
        frame_indices = onsets
    elif options.transition_type == "falling":
        frame_indices = offsets
    else:  # both
        frame_indices = sorted(onsets + offsets)

    # Convert to timestamps
    timestamps = frames_to_timestamps(frame_indices, options.fps, options.start_time_offset_s)

    logger.info(f"Generated {len(timestamps)} TTL pulses from {options.bodypart}")
    if timestamps:
        logger.debug(f"Time range: {timestamps[0]:.3f}s - {timestamps[-1]:.3f}s")

    return timestamps


def generate_ttl_from_custom_predicate(
    h5_path: Path,
    predicate: Callable[[pd.DataFrame], pd.Series],
    options: TTLMockOptions,
) -> List[float]:
    """Generate TTL timestamps using a custom predicate function.

    Advanced API for complex signal generation logic. The predicate receives
    the full DLC DataFrame and returns a boolean Series indicating signal state.

    Args:
        h5_path: Path to DeepLabCut H5 output file
        predicate: Function that takes DataFrame and returns boolean Series
        options: Configuration (fps, transition_type, etc.)

    Returns:
        List of TTL pulse timestamps in seconds

    Example:
        >>> def detect_movement(df):
        ...     # Detect when nose moves > 10 pixels between frames
        ...     scorer = df.columns.get_level_values(0)[0]
        ...     x = df[(scorer, 'nose', 'x')]
        ...     y = df[(scorer, 'nose', 'y')]
        ...     dx = x.diff().abs()
        ...     dy = y.diff().abs()
        ...     return (dx + dy) > 10
        >>>
        >>> options = TTLMockOptions(bodypart="nose", fps=150.0)
        >>> timestamps = generate_ttl_from_custom_predicate(
        ...     Path("pose.h5"), detect_movement, options
        ... )
    """
    if not h5_path.exists():
        raise PoseError(f"DLC H5 file not found: {h5_path}")

    try:
        df = pd.read_hdf(h5_path, "df_with_missing")
    except (KeyError, OSError, ValueError) as e:
        raise PoseError(f"Failed to read DLC H5 file {h5_path}: {e}") from e

    # Apply custom predicate
    signal = predicate(df)

    if not isinstance(signal, pd.Series):
        raise PoseError(f"Predicate must return pd.Series, got {type(signal)}")

    # Detect transitions
    onsets, offsets = detect_signal_transitions(signal, options.transition_type)

    # Filter by minimum duration if needed
    if options.min_duration_frames > 1 and options.transition_type in ("rising", "both"):
        onsets, offsets = filter_by_duration(onsets, offsets, options.min_duration_frames)

    # Select timestamps based on transition type
    if options.transition_type == "rising":
        frame_indices = onsets
    elif options.transition_type == "falling":
        frame_indices = offsets
    else:  # both
        frame_indices = sorted(onsets + offsets)

    # Convert to timestamps
    timestamps = frames_to_timestamps(frame_indices, options.fps, options.start_time_offset_s)

    return timestamps


def write_ttl_timestamps(timestamps: List[float], output_path: Path) -> None:
    """Write TTL timestamps to file in w2t_bkin format.

    Writes one timestamp per line, sorted, with high precision. Creates parent
    directories if needed.

    Args:
        timestamps: List of timestamps in seconds
        output_path: Path to output file

    Example:
        >>> timestamps = [0.0, 1.5, 3.0]
        >>> write_ttl_timestamps(timestamps, Path("TTLs/ttl_sync.txt"))
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort timestamps
    sorted_timestamps = sorted(timestamps)

    # Write with high precision
    with open(output_path, "w") as f:
        for ts in sorted_timestamps:
            f.write(f"{ts:.6f}\n")

    logger.info(f"Wrote {len(timestamps)} TTL timestamps to {output_path}")


def generate_and_write_ttl_from_pose(
    h5_path: Path,
    output_path: Path,
    options: TTLMockOptions,
    scorer: Optional[str] = None,
) -> int:
    """Convenience function to generate and write TTL file in one call.

    Args:
        h5_path: Path to DeepLabCut H5 output file
        output_path: Path to output TTL file
        options: Configuration for TTL generation
        scorer: Optional DLC scorer name

    Returns:
        Number of TTL pulses generated

    Example:
        >>> count = generate_and_write_ttl_from_pose(
        ...     h5_path=Path("pose.h5"),
        ...     output_path=Path("TTLs/trial_light.txt"),
        ...     options=TTLMockOptions(bodypart="trial_light", fps=150.0)
        ... )
        >>> print(f"Generated {count} pulses")
    """
    timestamps = generate_ttl_from_dlc_likelihood(h5_path, options, scorer)
    write_ttl_timestamps(timestamps, output_path)
    return len(timestamps)
