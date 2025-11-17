"""Visualization module for pose estimation data.

Provides plotting functions for:
- Skeleton overlays on video frames
- Per-joint trajectories (2D/3D)
- Pose quality metrics (missing keypoints, confidence)
- Event-aligned pose snippets

All functions consume PoseBundle domain models.
"""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import add_phase_annotation, ensure_output_dir, get_camera_color, make_deterministic_filename, make_figure_grid, make_time_axis, save_figure
from w2t_bkin.domain.pose import PoseBundle, PoseFrame

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_pose_trajectory_2d(
    pose_bundle: PoseBundle,
    keypoint_names: Optional[List[str]] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot 2D trajectories for selected keypoints.

    Args:
        pose_bundle: PoseBundle with pose frames
        keypoint_names: List of keypoint names to plot (all if None)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not pose_bundle.frames:
        ax.text(0.5, 0.5, "No pose data available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Extract keypoint trajectories
    if keypoint_names is None:
        # Get all unique keypoint names from first frame
        keypoint_names = [kp.name for kp in pose_bundle.frames[0].keypoints]

    for kp_name in keypoint_names:
        x_coords = []
        y_coords = []
        for frame in pose_bundle.frames:
            kp = next((k for k in frame.keypoints if k.name == kp_name), None)
            if kp is not None:
                x_coords.append(kp.x)
                y_coords.append(kp.y)
            else:
                x_coords.append(np.nan)
                y_coords.append(np.nan)

        ax.plot(x_coords, y_coords, "-o", label=kp_name, markersize=2, alpha=0.7, linewidth=1)

    # Styling
    ax.set_xlabel("X (pixels)", fontsize=11)
    ax.set_ylabel("Y (pixels)", fontsize=11)
    ax.set_title(f"2D Pose Trajectories\n{pose_bundle.camera_id} | {pose_bundle.skeleton}", fontsize=12, fontweight="bold")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()  # Invert Y to match image coordinates

    add_phase_annotation(ax, f"Mean conf: {pose_bundle.mean_confidence:.2f}", location="top-left")

    return ax


def plot_pose_confidence_distribution(
    pose_bundle: PoseBundle,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot confidence score distribution across all keypoints and frames.

    Args:
        pose_bundle: PoseBundle with pose frames
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not pose_bundle.frames:
        ax.text(0.5, 0.5, "No pose data available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Collect all confidence scores
    all_confidences = []
    for frame in pose_bundle.frames:
        for kp in frame.keypoints:
            all_confidences.append(kp.confidence)

    # Plot histogram
    ax.hist(all_confidences, bins=50, alpha=0.7, color=get_camera_color(pose_bundle.camera_id), edgecolor="black", linewidth=0.5)

    # Add mean line
    mean_conf = np.mean(all_confidences)
    ax.axvline(mean_conf, color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_conf:.3f}")

    # Styling
    ax.set_xlabel("Confidence Score", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title(f"Pose Confidence Distribution\n{pose_bundle.camera_id} | {len(all_confidences):,} keypoints", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_xlim(0, 1)

    return ax


def plot_pose_keypoint_quality(
    pose_bundle: PoseBundle,
    confidence_threshold: float = 0.5,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot per-keypoint quality metrics (presence and mean confidence).

    Args:
        pose_bundle: PoseBundle with pose frames
        confidence_threshold: Threshold for considering a keypoint "present"
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not pose_bundle.frames:
        ax.text(0.5, 0.5, "No pose data available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Get all unique keypoint names
    keypoint_names = [kp.name for kp in pose_bundle.frames[0].keypoints]

    # Calculate metrics per keypoint
    presence_rates = []
    mean_confidences = []

    for kp_name in keypoint_names:
        confidences = []
        for frame in pose_bundle.frames:
            kp = next((k for k in frame.keypoints if k.name == kp_name), None)
            if kp is not None:
                confidences.append(kp.confidence)

        presence_rate = sum(1 for c in confidences if c >= confidence_threshold) / len(confidences) if confidences else 0
        mean_conf = np.mean(confidences) if confidences else 0

        presence_rates.append(presence_rate * 100)  # Convert to percentage
        mean_confidences.append(mean_conf)

    # Plot bars
    x = np.arange(len(keypoint_names))
    width = 0.35

    bars1 = ax.bar(x - width / 2, presence_rates, width, label="Presence %", color="steelblue", alpha=0.8)
    bars2 = ax.bar(x + width / 2, [c * 100 for c in mean_confidences], width, label="Mean Conf %", color="orange", alpha=0.8)

    # Styling
    ax.set_xlabel("Keypoint", fontsize=11)
    ax.set_ylabel("Percentage", fontsize=11)
    ax.set_title(f"Per-Keypoint Quality Metrics\nThreshold: {confidence_threshold}", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(keypoint_names, rotation=45, ha="right", fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0, 105)

    return ax


def plot_pose_temporal_quality(
    pose_bundle: PoseBundle,
    window_size: int = 30,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot temporal quality metrics (rolling mean confidence over time).

    Args:
        pose_bundle: PoseBundle with pose frames
        window_size: Window size for rolling mean (in frames)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="wide")

    if not pose_bundle.frames:
        ax.text(0.5, 0.5, "No pose data available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Calculate mean confidence per frame
    frame_confidences = []
    timestamps = []

    for frame in pose_bundle.frames:
        if frame.keypoints:
            frame_conf = np.mean([kp.confidence for kp in frame.keypoints])
            frame_confidences.append(frame_conf)
            timestamps.append(frame.timestamp)

    if not frame_confidences:
        ax.text(0.5, 0.5, "No confidence data available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Calculate rolling mean
    frame_confidences = np.array(frame_confidences)
    rolling_mean = np.convolve(frame_confidences, np.ones(window_size) / window_size, mode="same")

    # Plot
    ax.plot(timestamps, frame_confidences, alpha=0.3, color="gray", linewidth=0.5, label="Per-frame")
    ax.plot(timestamps, rolling_mean, color=get_camera_color(pose_bundle.camera_id), linewidth=2, label=f"Rolling mean (n={window_size})")

    # Add mean line
    ax.axhline(pose_bundle.mean_confidence, color="red", linestyle="--", linewidth=1, label=f"Overall mean: {pose_bundle.mean_confidence:.3f}")

    # Styling
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Mean Confidence", fontsize=11)
    ax.set_title(f"Pose Quality Over Time\n{pose_bundle.camera_id}", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1)

    return ax


def plot_pose_summary_panel(
    pose_bundle: PoseBundle,
    confidence_threshold: float = 0.5,
) -> plt.Figure:
    """Create multi-panel pose summary figure.

    Creates a 2x2 panel with:
    - Top-left: 2D trajectories
    - Top-right: Confidence distribution
    - Bottom-left: Per-keypoint quality
    - Bottom-right: Temporal quality

    Args:
        pose_bundle: PoseBundle with pose frames
        confidence_threshold: Threshold for quality metrics

    Returns:
        Matplotlib Figure object
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: 2D trajectories
    plot_pose_trajectory_2d(pose_bundle, ax=axes[0, 0])

    # Top-right: Confidence distribution
    plot_pose_confidence_distribution(pose_bundle, ax=axes[0, 1])

    # Bottom-left: Per-keypoint quality
    plot_pose_keypoint_quality(pose_bundle, confidence_threshold, ax=axes[1, 0])

    # Bottom-right: Temporal quality
    plot_pose_temporal_quality(pose_bundle, ax=axes[1, 1])

    fig.suptitle(f"Pose Estimation Summary — {pose_bundle.session_id} / {pose_bundle.camera_id}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_pose_figures(
    pose_bundle: Union[PoseBundle, str, Path],
    output_dir: Union[str, Path],
    session_id: str = "unknown",
    confidence_threshold: float = 0.5,
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all pose estimation figures.

    Creates:
    - Multi-panel pose summary (trajectories, confidence, quality, temporal)
    - Individual component figures

    Args:
        pose_bundle: PoseBundle object or path to pose data JSON
        output_dir: Output directory for figures
        session_id: Session identifier for deterministic filenames
        confidence_threshold: Threshold for quality metrics
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Example:
        >>> paths = render_pose_figures(
        ...     pose_bundle='data/interim/pose_bundle.json',
        ...     output_dir='reports/figures/pose',
        ...     session_id='SNA-145518'
        ... )
    """
    # Load object if path provided
    if isinstance(pose_bundle, (str, Path)):
        import json

        with open(pose_bundle, "r") as f:
            pose_bundle = PoseBundle(**json.load(f))

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # Use session_id from bundle if available
    if hasattr(pose_bundle, "session_id"):
        session_id = pose_bundle.session_id

    # 1. Multi-panel summary
    fig_summary = plot_pose_summary_panel(pose_bundle, confidence_threshold)
    filename_summary = make_deterministic_filename(session_id, "pose", "summary", camera_id=pose_bundle.camera_id, ext=formats[0])
    paths_summary = save_figure(fig_summary, output_dir, filename_summary, formats=formats)
    saved_paths.extend(paths_summary)

    # 2. Individual 2D trajectory (larger)
    fig_traj, ax_traj = make_figure_grid(1, 1, figsize="large")
    plot_pose_trajectory_2d(pose_bundle, ax=ax_traj)
    filename_traj = make_deterministic_filename(session_id, "pose", "trajectory", camera_id=pose_bundle.camera_id, ext=formats[0])
    paths_traj = save_figure(fig_traj, output_dir, filename_traj, formats=formats)
    saved_paths.extend(paths_traj)

    return saved_paths
