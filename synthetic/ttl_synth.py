"""Synthetic TTL pulse generation for testing.

This module generates synthetic TTL (Transistor-Transistor Logic) pulse timing
files that match the format expected by the W2T-BKIN pipeline.

TTL File Format:
----------------
Each line contains a single timestamp (float, in seconds) representing a pulse.
Lines are sorted chronologically.

Example:
    0.0
    0.033
    0.066
    0.100

Features:
---------
- Deterministic generation with random seed
- Configurable pulse count, period, and jitter
- Support for irregular timing (jitter) to test alignment
- Fast generation (no external dependencies)

Requirements Coverage:
----------------------
- FR-15: TTL pulse file generation for testing
- NFR-4: Fast generation for unit tests
"""

from pathlib import Path
import random
from typing import Optional

from synthetic.models import SyntheticTTL


def create_ttl_file(
    output_path: Path,
    ttl: SyntheticTTL,
    seed: Optional[int] = None,
) -> Path:
    """Create a synthetic TTL pulse file.

    Args:
        output_path: Path where TTL file should be written
        ttl: TTL generation parameters
        seed: Random seed for jitter (uses ttl params if None)

    Returns:
        Path to created TTL file

    Example:
        >>> from pathlib import Path
        >>> from synthetic.models import SyntheticTTL
        >>> ttl = SyntheticTTL(
        ...     ttl_id="cam0_ttl",
        ...     pulse_count=100,
        ...     period_s=0.033,
        ...     jitter_s=0.001
        ... )
        >>> path = create_ttl_file(Path("test.ttl"), ttl, seed=42)
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Set random seed for reproducibility
    if seed is not None:
        random.seed(seed)

    # Generate pulse timestamps
    timestamps = []
    current_time = ttl.start_time_s

    for _ in range(ttl.pulse_count):
        # Add jitter if specified
        if ttl.jitter_s > 0:
            jitter = random.uniform(-ttl.jitter_s, ttl.jitter_s)
            current_time += jitter

        timestamps.append(current_time)
        current_time += ttl.period_s

    # Write timestamps to file
    with open(output_path, "w") as f:
        for ts in timestamps:
            f.write(f"{ts:.6f}\n")

    return output_path


def create_ttl_file_with_mismatch(
    output_path: Path,
    expected_count: int,
    actual_count: int,
    period_s: float = 0.033,
    start_time_s: float = 0.0,
    seed: Optional[int] = None,
) -> Path:
    """Create a TTL file with a deliberate count mismatch for testing verification.

    This is a convenience function for creating scenarios where TTL pulse count
    doesn't match video frame count.

    Args:
        output_path: Path where TTL file should be written
        expected_count: The count that should match (for documentation)
        actual_count: The actual pulse count to generate
        period_s: Time between pulses
        start_time_s: Start time
        seed: Random seed

    Returns:
        Path to created TTL file

    Example:
        >>> # Video has 100 frames, but TTL only has 95 pulses
        >>> path = create_ttl_file_with_mismatch(
        ...     Path("test.ttl"),
        ...     expected_count=100,
        ...     actual_count=95
        ... )
    """
    ttl = SyntheticTTL(
        ttl_id="mismatch_test",
        pulse_count=actual_count,
        start_time_s=start_time_s,
        period_s=period_s,
        jitter_s=0.0,
    )
    return create_ttl_file(output_path, ttl, seed=seed)


def create_ttl_file_with_jitter(
    output_path: Path,
    pulse_count: int,
    period_s: float = 0.033,
    jitter_s: float = 0.005,
    seed: Optional[int] = None,
) -> Path:
    """Create a TTL file with high jitter for testing alignment budget.

    This is a convenience function for creating scenarios where jitter exceeds
    the configured alignment budget.

    Args:
        output_path: Path where TTL file should be written
        pulse_count: Number of pulses to generate
        period_s: Nominal time between pulses
        jitter_s: Amount of random jitter (±jitter_s)
        seed: Random seed

    Returns:
        Path to created TTL file

    Example:
        >>> # Create TTL with 10ms jitter (exceeds typical 5ms budget)
        >>> path = create_ttl_file_with_jitter(
        ...     Path("test.ttl"),
        ...     pulse_count=100,
        ...     jitter_s=0.010,
        ...     seed=42
        ... )
    """
    ttl = SyntheticTTL(
        ttl_id="jitter_test",
        pulse_count=pulse_count,
        start_time_s=0.0,
        period_s=period_s,
        jitter_s=jitter_s,
    )
    return create_ttl_file(output_path, ttl, seed=seed)
