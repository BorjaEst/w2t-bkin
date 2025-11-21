"""Figures package: plotting helpers for examples and docs."""

from .pose import plot_pose_keypoints_grid, plot_ttl_detection_from_pose
from .sync import plot_alignment_example, plot_alignment_grid, plot_trial_offsets, plot_ttl_timeline

__all__ = [
    "plot_ttl_timeline",
    "plot_trial_offsets",
    "plot_alignment_example",
    "plot_alignment_grid",
    "plot_ttl_detection_from_pose",
    "plot_pose_keypoints_grid",
]
