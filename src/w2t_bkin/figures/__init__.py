"""Figures package: plotting helpers for pipeline diagnostics and analysis.

This package provides utilities for generating diagnostic plots and
profiling visualizations to understand pipeline execution and validate results.
"""

from .pose import plot_pose_keypoints_grid, plot_ttl_detection_from_pose
from .profiling import PhaseProfile, PhaseTimer, PipelineProfile, plot_pipeline_execution, plot_synchronization_stats
from .sync import plot_alignment_example, plot_alignment_grid, plot_sync_recovery, plot_trial_offsets, plot_ttl_timeline

__all__ = [
    # Synchronization plots
    "plot_ttl_timeline",
    "plot_trial_offsets",
    "plot_alignment_example",
    "plot_alignment_grid",
    "plot_sync_recovery",
    # Pose plots
    "plot_ttl_detection_from_pose",
    "plot_pose_keypoints_grid",
    # Profiling
    "PhaseProfile",
    "PhaseTimer",
    "PipelineProfile",
    "plot_pipeline_execution",
    "plot_synchronization_stats",
]
