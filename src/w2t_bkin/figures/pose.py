"""Plotting helpers for pose analysis examples.

These functions are intentionally lightweight, with graceful fallbacks
if matplotlib is not installed (the example remains runnable without plots).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

try:  # Optional dependency for examples
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - optional
    plt = None  # type: ignore


def _ensure_parent(path: Path) -> Path:
    """Ensure parent directory exists for the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def plot_ttl_detection_from_pose(
    h5_path: Path,
    bodypart: str,
    threshold: float,
    timestamps: List[float],
    *,
    fps: float = 30.0,
    transition_type: str = "rising",
    min_duration: int = 1,
    out_path: Optional[Path] = None,
    display: bool = False,
) -> Optional[Path]:
    """Generate visualization of DLC likelihood and detected TTL events.

    Args:
        h5_path: Path to DeepLabCut H5 file
        bodypart: Name of body part to analyze
        threshold: Likelihood threshold for detection
        timestamps: List of detected TTL event timestamps (seconds)
        fps: Frames per second for time axis conversion
        transition_type: Type of transition detected ('rising', 'falling', or 'both')
        min_duration: Minimum duration in frames for valid events
        out_path: Path where plot should be saved (required if display=False)
        display: If True, display plot interactively; if False, save to out_path

    Returns:
        Path to saved plot, or None if display=True or matplotlib is unavailable

    Raises:
        ValueError: If display=False but out_path is None
    """
    if plt is None:  # pragma: no cover
        return None

    # Validate arguments
    if not display and out_path is None:
        raise ValueError("out_path is required when display=False")

    # Import here to avoid hard dependency
    from w2t_bkin.sync.ttl_mock import load_dlc_likelihood_series

    if out_path is not None and not display:
        _ensure_parent(out_path)

    # Load data
    likelihood = load_dlc_likelihood_series(h5_path, bodypart)
    signal = likelihood >= threshold
    time_axis = likelihood.index / fps

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Plot 1: Likelihood time series
    ax1.plot(time_axis, likelihood, label="Likelihood", alpha=0.7, linewidth=1)
    ax1.axhline(threshold, color="r", linestyle="--", label=f"Threshold ({threshold})", alpha=0.7)
    ax1.fill_between(time_axis, 0, 1, where=signal, alpha=0.2, color="green", label="Above threshold")
    ax1.set_ylabel("Likelihood", fontsize=11)
    ax1.set_title(f"TTL Detection from DLC Pose: {bodypart}", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-0.05, 1.05)

    # Plot 2: Detected events
    ax2.fill_between(time_axis, 0, signal.astype(int), alpha=0.3, color="blue", label="Signal ON")
    for i, ts in enumerate(timestamps):
        color = "red" if transition_type == "rising" else "orange"
        alpha = 0.8 if i < 10 else 0.4  # Fade later events for clarity
        ax2.axvline(ts, color=color, alpha=alpha, linewidth=2, linestyle="-")

    ax2.set_xlabel("Time (s)", fontsize=11)
    ax2.set_ylabel("Signal State", fontsize=11)
    ax2.set_title(f"Detected Events (n={len(timestamps)})", fontsize=12)
    ax2.set_ylim(-0.1, 1.2)
    ax2.grid(True, alpha=0.3)

    # Add text annotation
    ax2.text(
        0.02,
        0.95,
        f"Transition: {transition_type}\nMin duration: {min_duration} frames\nFPS: {fps} Hz",
        transform=ax2.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.tight_layout()

    # Save or display figure
    if display:
        plt.show()
        return None
    else:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()
        return out_path


def plot_pose_keypoints_grid(
    bundle,  # PoseBundle type
    video_path: Path,
    out_path: Path,
    frame_indices: Optional[List[int]] = None,
) -> Optional[Path]:
    """Generate grid visualization of pose keypoints on video frames.

    Shows 3 frames (first, middle, last) with keypoint overlays to visualize
    pose tracking quality and spatial distribution.

    Args:
        bundle: PoseBundle with pose data
        video_path: Path to video file for frame extraction
        out_path: Path where plot should be saved
        frame_indices: Optional list of frame indices to plot (default: [0, n//2, -1])

    Returns:
        Path to saved plot, or None if matplotlib/cv2 is unavailable
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_pose_keypoints_grid: matplotlib not available")
        return None

    try:
        import cv2
    except ImportError:  # pragma: no cover
        logger.info("plot_pose_keypoints_grid: cv2 (OpenCV) not available")
        return None

    _ensure_parent(out_path)

    # Determine which frames to plot
    n_frames = len(bundle.frames)
    if frame_indices is None:
        frame_indices = [0, n_frames // 2, n_frames - 1]

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.info(f"plot_pose_keypoints_grid: cannot open video: {video_path}")
        return None

    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    for idx, frame_idx in enumerate(frame_indices):
        if frame_idx < 0:
            frame_idx = n_frames + frame_idx

        # Seek to frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            continue

        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Plot frame
        ax = axes[idx]
        ax.imshow(frame_rgb)

        # Overlay keypoints
        pose_frame = bundle.frames[frame_idx]
        for keypoint in pose_frame.keypoints:
            x = keypoint.x
            y = keypoint.y
            confidence = keypoint.confidence

            # Color by confidence (green=high, red=low)
            color = plt.cm.RdYlGn(confidence)

            # Plot keypoint
            ax.plot(x, y, "o", color=color, markersize=10, markeredgecolor="white", markeredgewidth=2)

            # Add label
            ax.text(
                x,
                y - 10,
                keypoint.name,
                color="white",
                fontsize=8,
                ha="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.7),
            )

        # Set title
        ax.set_title(f"Frame {frame_idx} (t={pose_frame.timestamp:.2f}s)", fontsize=11)
        ax.axis("off")

    cap.release()

    # Overall title
    fig.suptitle(
        f"Pose Keypoints: {bundle.session_id} - {bundle.camera_id}\n" f"Model: {bundle.model_name} | Mean Confidence: {bundle.mean_confidence:.3f}",
        fontsize=13,
        fontweight="bold",
    )

    plt.tight_layout()

    # Save figure
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()

    return out_path
