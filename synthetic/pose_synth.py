"""Synthetic pose estimation output generation for testing.

This module creates synthetic pose tracking data in DeepLabCut CSV format
for testing the W2T-BKIN pose processing pipeline.

Features:
---------
- **DeepLabCut CSV Format**: Standard DLC output with scorer, bodyparts, coords rows
- **Configurable Keypoints**: Define custom skeleton with arbitrary keypoint names
- **Realistic Motion**: Smooth trajectories with configurable noise
- **Confidence Scores**: Controllable confidence values per keypoint
- **Deterministic**: Same seed produces identical outputs
- **Missing Data**: Optional random dropouts to simulate tracking failures

Example:
--------
>>> from pathlib import Path
>>> from synthetic.pose_synth import create_dlc_pose_csv, PoseParams
>>>
>>> # Create pose data
>>> params = PoseParams(
...     keypoints=["nose", "left_ear", "right_ear"],
...     n_frames=100,
...     confidence_mean=0.95,
...     confidence_std=0.03
... )
>>> pose_path = create_dlc_pose_csv(
...     output_path=Path("pose_output.csv"),
...     params=params,
...     seed=42
... )
"""

import csv
from dataclasses import dataclass
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class PoseParams:
    """Parameters for synthetic pose generation.

    Attributes:
        keypoints: List of keypoint names (e.g., ["nose", "left_ear", "right_ear"])
        n_frames: Number of frames to generate
        image_width: Video width in pixels (for trajectory bounds)
        image_height: Video height in pixels (for trajectory bounds)
        confidence_mean: Mean confidence score (0.0-1.0)
        confidence_std: Standard deviation of confidence scores
        motion_smoothness: Smoothness factor (higher = smoother motion)
        dropout_rate: Probability of missing keypoints per frame (0.0-1.0)
        scorer: DLC scorer name for CSV header
    """

    keypoints: List[str]
    n_frames: int = 100
    image_width: int = 640
    image_height: int = 480
    confidence_mean: float = 0.95
    confidence_std: float = 0.03
    motion_smoothness: float = 5.0
    dropout_rate: float = 0.0
    scorer: str = "DLC_resnet50"


def generate_smooth_trajectory(
    n_frames: int,
    start_pos: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    smoothness: float = 5.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate smooth 2D trajectory using random walk with momentum.

    Args:
        n_frames: Number of frames
        start_pos: Starting (x, y) position
        bounds: (min_x, min_y, max_x, max_y) boundaries
        smoothness: Higher = smoother motion (reduces velocity changes)
        seed: Random seed for reproducibility

    Returns:
        Array of shape (n_frames, 2) with x, y coordinates
    """
    if seed is not None:
        np.random.seed(seed)

    positions = np.zeros((n_frames, 2))
    positions[0] = start_pos

    velocity = np.array([0.0, 0.0])
    momentum = 1.0 / smoothness  # Convert smoothness to momentum factor

    for i in range(1, n_frames):
        # Add random acceleration
        acceleration = np.random.randn(2) * 0.5

        # Update velocity with momentum
        velocity = velocity * (1 - momentum) + acceleration * momentum

        # Update position
        new_pos = positions[i - 1] + velocity

        # Bounce off boundaries
        if new_pos[0] < bounds[0] or new_pos[0] > bounds[2]:
            velocity[0] *= -0.8
            new_pos[0] = np.clip(new_pos[0], bounds[0], bounds[2])

        if new_pos[1] < bounds[1] or new_pos[1] > bounds[3]:
            velocity[1] *= -0.8
            new_pos[1] = np.clip(new_pos[1], bounds[1], bounds[3])

        positions[i] = new_pos

    return positions


def generate_confidence_scores(n_frames: int, mean: float = 0.95, std: float = 0.03, seed: Optional[int] = None) -> np.ndarray:
    """Generate confidence scores with realistic distribution.

    Args:
        n_frames: Number of frames
        mean: Mean confidence (0.0-1.0)
        std: Standard deviation
        seed: Random seed

    Returns:
        Array of confidence scores clipped to [0.0, 1.0]
    """
    if seed is not None:
        np.random.seed(seed)

    scores = np.random.normal(mean, std, n_frames)
    return np.clip(scores, 0.0, 1.0)


def create_dlc_pose_csv(output_path: Path, params: PoseParams, seed: Optional[int] = None) -> Path:
    """Create synthetic DeepLabCut pose tracking CSV file.

    Args:
        output_path: Path where CSV file should be written
        params: Pose generation parameters
        seed: Random seed for reproducibility

    Returns:
        Path to created CSV file

    Example:
        >>> from pathlib import Path
        >>> params = PoseParams(
        ...     keypoints=["nose", "left_ear", "right_ear"],
        ...     n_frames=100
        ... )
        >>> csv_path = create_dlc_pose_csv(Path("pose.csv"), params, seed=42)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Set random seeds
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    # Generate trajectories for each keypoint
    bounds = (20, 20, params.image_width - 20, params.image_height - 20)
    trajectories = {}
    confidences = {}

    for idx, keypoint in enumerate(params.keypoints):
        # Random starting position
        start_x = random.uniform(bounds[0], bounds[2])
        start_y = random.uniform(bounds[1], bounds[3])

        # Generate trajectory
        trajectory = generate_smooth_trajectory(
            n_frames=params.n_frames,
            start_pos=(start_x, start_y),
            bounds=bounds,
            smoothness=params.motion_smoothness,
            seed=seed + idx if seed is not None else None,
        )
        trajectories[keypoint] = trajectory

        # Generate confidence scores
        confidence = generate_confidence_scores(
            n_frames=params.n_frames,
            mean=params.confidence_mean,
            std=params.confidence_std,
            seed=seed + idx + 1000 if seed is not None else None,
        )
        confidences[keypoint] = confidence

    # Write DLC CSV format
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)

        # Row 0: Scorer (repeated for each coordinate)
        scorer_row = ["scorer"] + [params.scorer] * (len(params.keypoints) * 3)
        writer.writerow(scorer_row)

        # Row 1: Bodyparts (each keypoint repeated 3 times: x, y, likelihood)
        bodyparts_row = ["bodyparts"]
        for kp in params.keypoints:
            bodyparts_row.extend([kp, kp, kp])
        writer.writerow(bodyparts_row)

        # Row 2: Coords (x, y, likelihood pattern)
        coords_row = ["coords"]
        for _ in params.keypoints:
            coords_row.extend(["x", "y", "likelihood"])
        writer.writerow(coords_row)

        # Data rows: frame_index, x, y, likelihood for each keypoint
        for frame_idx in range(params.n_frames):
            row = [frame_idx]

            for keypoint in params.keypoints:
                # Check for dropout
                if random.random() < params.dropout_rate:
                    # Missing data (low confidence, NaN position)
                    row.extend([0.0, 0.0, 0.0])
                else:
                    x = trajectories[keypoint][frame_idx, 0]
                    y = trajectories[keypoint][frame_idx, 1]
                    confidence = confidences[keypoint][frame_idx]
                    row.extend([f"{x:.6f}", f"{y:.6f}", f"{confidence:.6f}"])

            writer.writerow(row)

    return output_path


def create_simple_pose_csv(
    output_path: Path,
    n_frames: int = 100,
    keypoints: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> Path:
    """Create simple synthetic pose CSV with default parameters.

    Convenience function for quick pose generation with minimal configuration.

    Args:
        output_path: Path where CSV file should be written
        n_frames: Number of frames
        keypoints: Keypoint names (defaults to nose, left_ear, right_ear)
        seed: Random seed

    Returns:
        Path to created CSV file
    """
    if keypoints is None:
        keypoints = ["nose", "left_ear", "right_ear"]

    params = PoseParams(keypoints=keypoints, n_frames=n_frames)
    return create_dlc_pose_csv(output_path, params, seed=seed)


# Legacy compatibility
def create_pose_output(
    output_path: Path,
    n_frames: int = 100,
    n_keypoints: int = 12,
    seed: int = 42,
) -> Path:
    """Create a synthetic pose estimation output file (legacy compatibility).

    Args:
        output_path: Path where pose file should be written
        n_frames: Number of frames
        n_keypoints: Number of keypoints per frame
        seed: Random seed

    Returns:
        Path to created pose file

    Note:
        This is a compatibility wrapper. Use create_dlc_pose_csv for new code.
    """
    default_keypoints = [
        "nose",
        "left_ear",
        "right_ear",
        "left_eye",
        "right_eye",
        "left_shoulder",
        "right_shoulder",
        "left_hip",
        "right_hip",
        "left_paw",
        "right_paw",
        "tail_base",
    ][:n_keypoints]

    return create_simple_pose_csv(output_path, n_frames, default_keypoints, seed)
