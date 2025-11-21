"""Synthetic DLC pose H5 generation for W2T-BKIN.

Creates synthetic DeepLabCut H5 files with realistic pose trajectories,
confidence scores, and optional dropout for testing and demos.

Features:
- `PoseH5Params` dataclass for generation parameters
- Smooth circular/sinusoidal trajectories for realistic motion
- Configurable confidence scores with dropout simulation
- Proper DLC MultiIndex structure (scorer, bodyparts, coords)
- Deterministic generation based on seed

Example:
    from synthetic.pose_synth import PoseH5Params, create_dlc_pose_h5

    params = PoseH5Params(
        keypoints=["nose", "left_ear", "right_ear"],
        n_frames=300,
        fps=30.0,
        confidence_mean=0.95,
        confidence_std=0.05,
        dropout_rate=0.02,
        seed=42
    )
    h5_path = create_dlc_pose_h5(Path("output/pose.h5"), params)

CLI:
    python -m synthetic.pose_synth --out output/pose.h5 --n_frames 500
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

import numpy as np
import pandas as pd
from pydantic import Field


@dataclass
class PoseH5Params:
    """Parameters for synthetic DLC H5 generation.

    Attributes:
        keypoints: List of bodypart names (e.g., ["nose", "left_ear"])
        n_frames: Number of frames to generate
        fps: Frame rate (for trajectory smoothness calculation)
        confidence_mean: Mean confidence/likelihood value (0-1)
        confidence_std: Standard deviation of confidence values
        dropout_rate: Fraction of frames with zero confidence (simulates tracking loss)
        seed: Random seed for reproducibility
        scorer_name: DLC scorer name in MultiIndex
        video_width: Video width for trajectory centering (pixels)
        video_height: Video height for trajectory centering (pixels)
        motion_radius: Radius of circular motion pattern (pixels)
    """

    keypoints: List[str]
    n_frames: int = 300
    fps: float = 30.0
    confidence_mean: float = 0.95
    confidence_std: float = 0.05
    dropout_rate: float = 0.02
    seed: int = 42
    scorer_name: str = "DLC_resnet50_demoOct30shuffle1_150000"
    video_width: int = 640
    video_height: int = 480
    motion_radius: float = 50.0


def generate_smooth_trajectory(n_frames: int, center: tuple[float, float], radius: float, seed: int, motion_type: str = "circular") -> tuple[np.ndarray, np.ndarray]:
    """Generate smooth x, y trajectories for a keypoint.

    Args:
        n_frames: Number of frames
        center: (x, y) center point of motion
        radius: Radius of motion pattern
        seed: Random seed
        motion_type: Type of motion ("circular" or "sinusoidal")

    Returns:
        Tuple of (x_coords, y_coords) numpy arrays
    """
    rng = np.random.RandomState(seed)

    if motion_type == "circular":
        # Circular motion with some noise
        theta = np.linspace(0, 4 * np.pi, n_frames)  # 2 full circles
        noise_x = rng.normal(0, radius * 0.05, n_frames)
        noise_y = rng.normal(0, radius * 0.05, n_frames)

        x = center[0] + radius * np.cos(theta) + noise_x
        y = center[1] + radius * np.sin(theta) + noise_y

    elif motion_type == "sinusoidal":
        # Sinusoidal motion
        t = np.linspace(0, 4 * np.pi, n_frames)
        noise_x = rng.normal(0, radius * 0.05, n_frames)
        noise_y = rng.normal(0, radius * 0.05, n_frames)

        x = center[0] + radius * np.sin(t) + noise_x
        y = center[1] + radius * 0.5 * np.sin(2 * t) + noise_y

    else:
        raise ValueError(f"Unknown motion_type: {motion_type}")

    return x, y


def generate_confidence_scores(n_frames: int, mean: float, std: float, dropout_rate: float, seed: int) -> np.ndarray:
    """Generate realistic confidence/likelihood scores.

    Args:
        n_frames: Number of frames
        mean: Mean confidence value (0-1)
        std: Standard deviation
        dropout_rate: Fraction of frames with zero confidence
        seed: Random seed

    Returns:
        Numpy array of confidence values [0, 1]
    """
    rng = np.random.RandomState(seed)

    # Generate base confidence scores
    confidence = rng.normal(mean, std, n_frames)

    # Clip to [0, 1] range
    confidence = np.clip(confidence, 0.0, 1.0)

    # Apply dropout (tracking loss)
    if dropout_rate > 0:
        dropout_mask = rng.random(n_frames) < dropout_rate
        confidence[dropout_mask] = 0.0

    return confidence


def create_dlc_pose_h5(output_path: Union[str, Path], params: PoseH5Params, seed: int | None = None) -> Path:
    """Create a synthetic DLC H5 file with proper MultiIndex structure.

    Args:
        output_path: Where to save the H5 file
        params: Generation parameters
        seed: Optional seed override (uses params.seed if None)

    Returns:
        Path to created H5 file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seed = seed if seed is not None else params.seed
    rng = np.random.RandomState(seed)

    # Build data dictionary for DataFrame
    data = {}

    # Generate trajectories for each keypoint
    for i, keypoint in enumerate(params.keypoints):
        # Each keypoint gets a unique center and motion pattern
        angle = (i / len(params.keypoints)) * 2 * np.pi
        center_x = params.video_width / 2 + params.motion_radius * np.cos(angle)
        center_y = params.video_height / 2 + params.motion_radius * np.sin(angle)

        # Generate trajectory
        motion_type = "circular" if i % 2 == 0 else "sinusoidal"
        x, y = generate_smooth_trajectory(params.n_frames, (center_x, center_y), params.motion_radius * 0.5, seed + i, motion_type)

        # Generate confidence scores
        likelihood = generate_confidence_scores(params.n_frames, params.confidence_mean, params.confidence_std, params.dropout_rate, seed + i + 1000)

        # Store in DLC format: (scorer, bodypart, coords)
        data[(params.scorer_name, keypoint, "x")] = x
        data[(params.scorer_name, keypoint, "y")] = y
        data[(params.scorer_name, keypoint, "likelihood")] = likelihood

    # Create DataFrame with MultiIndex columns
    df = pd.DataFrame(data)

    # Ensure proper MultiIndex structure
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["scorer", "bodyparts", "coords"])

    # Add frame index
    df.index.name = "frame"

    # Save to H5
    df.to_hdf(output_path, key="df_with_missing", mode="w")

    return output_path


if __name__ == "__main__":
    """CLI for synthetic pose generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic DLC pose H5 file")
    parser.add_argument("--out", type=Path, default=Path("output/synthetic_pose.h5"), help="Output H5 path")
    parser.add_argument("--keypoints", nargs="+", default=["nose", "left_ear", "right_ear"], help="Keypoint names")
    parser.add_argument("--n_frames", type=int, default=300, help="Number of frames")
    parser.add_argument("--fps", type=float, default=30.0, help="Frame rate")
    parser.add_argument("--confidence_mean", type=float, default=0.95, help="Mean confidence")
    parser.add_argument("--confidence_std", type=float, default=0.05, help="Confidence std dev")
    parser.add_argument("--dropout_rate", type=float, default=0.02, help="Dropout rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    params = PoseH5Params(
        keypoints=args.keypoints,
        n_frames=args.n_frames,
        fps=args.fps,
        confidence_mean=args.confidence_mean,
        confidence_std=args.confidence_std,
        dropout_rate=args.dropout_rate,
        seed=args.seed,
    )

    output_path = create_dlc_pose_h5(args.out, params)
    print(f"✓ Created synthetic DLC H5: {output_path}")
    print(f"  Keypoints: {len(params.keypoints)}")
    print(f"  Frames: {params.n_frames}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")
