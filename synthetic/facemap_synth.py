"""Synthetic facemap data generation for testing.

This module creates synthetic facemap outputs for testing the W2T-BKIN facemap
processing pipeline.

Features:
---------
- **Motion Energy**: Realistic motion energy time series
- **Pupil Tracking**: Area and center-of-mass (COM) tracking data
- **Deterministic**: Same seed produces identical outputs
- **Numpy Format**: Standard .npy format matching facemap output

Example:
--------
>>> from pathlib import Path
>>> from synthetic.facemap_synth import create_facemap_output, FacemapParams
>>>
>>> # Create facemap data
>>> params = FacemapParams(
...     n_frames=100,
...     motion_frequency=2.0,
...     pupil_size_range=(50, 150)
... )
>>> facemap_path = create_facemap_output(
...     output_path=Path("facemap_output.npy"),
...     params=params,
...     seed=42
... )
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


@dataclass
class FacemapParams:
    """Parameters for synthetic facemap generation.

    Attributes:
        n_frames: Number of frames to generate
        motion_frequency: Dominant frequency of motion energy (Hz)
        motion_amplitude: Amplitude of motion energy signal
        pupil_size_range: (min, max) pupil area in pixels
        pupil_motion_speed: Speed of pupil movement
        image_width: Video width for pupil COM bounds
        image_height: Video height for pupil COM bounds
        sample_rate: Sampling rate (fps)
    """

    n_frames: int = 100
    motion_frequency: float = 2.0
    motion_amplitude: float = 50.0
    pupil_size_range: Tuple[float, float] = (50.0, 150.0)
    pupil_motion_speed: float = 5.0
    image_width: int = 640
    image_height: int = 480
    sample_rate: float = 30.0


def generate_motion_energy(
    n_frames: int,
    frequency: float = 2.0,
    amplitude: float = 50.0,
    sample_rate: float = 30.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate realistic motion energy time series.

    Creates a signal with dominant frequency plus noise to simulate
    facial motion energy computed from video frames.

    Args:
        n_frames: Number of frames
        frequency: Dominant frequency in Hz
        amplitude: Signal amplitude
        sample_rate: Sampling rate (fps)
        seed: Random seed

    Returns:
        Array of shape (n_frames,) with motion energy values
    """
    if seed is not None:
        np.random.seed(seed)

    t = np.arange(n_frames) / sample_rate

    # Base signal: sine wave at dominant frequency
    signal = amplitude * np.sin(2 * np.pi * frequency * t)

    # Add harmonics for realism
    signal += (amplitude * 0.3) * np.sin(2 * np.pi * frequency * 2 * t + 1.2)
    signal += (amplitude * 0.15) * np.sin(2 * np.pi * frequency * 0.5 * t + 0.5)

    # Add noise
    noise = np.random.randn(n_frames) * (amplitude * 0.2)
    signal += noise

    # Make positive (motion energy is always >= 0)
    signal = np.abs(signal)

    return signal


def generate_pupil_area(
    n_frames: int,
    size_range: Tuple[float, float] = (50.0, 150.0),
    frequency: float = 0.5,
    sample_rate: float = 30.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate pupil area time series.

    Simulates pupil dilation/constriction with slow oscillations.

    Args:
        n_frames: Number of frames
        size_range: (min, max) pupil area in pixels
        frequency: Oscillation frequency in Hz
        sample_rate: Sampling rate (fps)
        seed: Random seed

    Returns:
        Array of shape (n_frames,) with pupil areas
    """
    if seed is not None:
        np.random.seed(seed)

    t = np.arange(n_frames) / sample_rate
    min_size, max_size = size_range
    mid_size = (min_size + max_size) / 2
    amplitude = (max_size - min_size) / 2

    # Slow oscillation
    area = mid_size + amplitude * np.sin(2 * np.pi * frequency * t)

    # Add noise
    noise = np.random.randn(n_frames) * (amplitude * 0.1)
    area += noise

    # Clip to range
    area = np.clip(area, min_size, max_size)

    return area


def generate_pupil_com(
    n_frames: int,
    image_width: int = 640,
    image_height: int = 480,
    speed: float = 5.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate pupil center-of-mass trajectory.

    Simulates smooth eye movement within image bounds.

    Args:
        n_frames: Number of frames
        image_width: Video width
        image_height: Video height
        speed: Movement speed factor
        seed: Random seed

    Returns:
        Array of shape (n_frames, 2) with (x, y) coordinates
    """
    if seed is not None:
        np.random.seed(seed)

    # Start near center
    center_x = image_width / 2
    center_y = image_height / 2

    # Generate smooth trajectory using random walk
    positions = np.zeros((n_frames, 2))
    positions[0] = [center_x, center_y]

    velocity = np.array([0.0, 0.0])
    momentum = 0.9  # High momentum for smooth movement

    for i in range(1, n_frames):
        # Small random acceleration
        acceleration = np.random.randn(2) * (speed * 0.1)

        # Update velocity with high momentum
        velocity = velocity * momentum + acceleration * (1 - momentum)

        # Update position
        new_pos = positions[i - 1] + velocity

        # Bounce off boundaries
        bounds_x = (image_width * 0.3, image_width * 0.7)
        bounds_y = (image_height * 0.3, image_height * 0.7)

        if new_pos[0] < bounds_x[0] or new_pos[0] > bounds_x[1]:
            velocity[0] *= -0.5
            new_pos[0] = np.clip(new_pos[0], bounds_x[0], bounds_x[1])

        if new_pos[1] < bounds_y[0] or new_pos[1] > bounds_y[1]:
            velocity[1] *= -0.5
            new_pos[1] = np.clip(new_pos[1], bounds_y[0], bounds_y[1])

        positions[i] = new_pos

    return positions


def create_facemap_output(output_path: Path, params: Optional[FacemapParams] = None, seed: Optional[int] = None) -> Path:
    """Create synthetic facemap output file.

    Args:
        output_path: Path where facemap file should be written (.npy format)
        params: Facemap generation parameters (uses defaults if None)
        seed: Random seed for reproducibility

    Returns:
        Path to created facemap file

    Example:
        >>> from pathlib import Path
        >>> params = FacemapParams(n_frames=100, motion_frequency=2.0)
        >>> facemap_path = create_facemap_output(Path("facemap.npy"), params, seed=42)
    """
    if params is None:
        params = FacemapParams()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate motion energy
    motion = generate_motion_energy(
        n_frames=params.n_frames,
        frequency=params.motion_frequency,
        amplitude=params.motion_amplitude,
        sample_rate=params.sample_rate,
        seed=seed,
    )

    # Generate pupil data
    pupil_area = generate_pupil_area(
        n_frames=params.n_frames,
        size_range=params.pupil_size_range,
        sample_rate=params.sample_rate,
        seed=seed + 1000 if seed is not None else None,
    )

    pupil_com = generate_pupil_com(
        n_frames=params.n_frames,
        image_width=params.image_width,
        image_height=params.image_height,
        speed=params.pupil_motion_speed,
        seed=seed + 2000 if seed is not None else None,
    )

    # Package as dict (facemap format)
    data = {"motion": motion, "pupil": {"area": pupil_area, "com": pupil_com}}

    # Save to .npy file
    np.save(output_path, data, allow_pickle=True)

    return output_path


def create_simple_facemap(output_path: Path, n_frames: int = 100, seed: Optional[int] = None) -> Path:
    """Create simple synthetic facemap with default parameters.

    Convenience function for quick facemap generation.

    Args:
        output_path: Path where facemap file should be written
        n_frames: Number of frames
        seed: Random seed

    Returns:
        Path to created facemap file
    """
    params = FacemapParams(n_frames=n_frames)
    return create_facemap_output(output_path, params, seed=seed)
