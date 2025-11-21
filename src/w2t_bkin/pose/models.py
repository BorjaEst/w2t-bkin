"""Pose module models - NWB-first re-exports.

This module re-exports ndx-pose types for convenience. The legacy PoseBundle,
PoseFrame, and PoseKeypoint models have been removed in favor of NWB-native
data structures.

For NWB-first pose workflow:
    from w2t_bkin.pose import build_pose_estimation, align_pose_to_timebase
    # Or import directly from ndx_pose:
    from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton

See docs/MIGRATION.md for migration guidance from legacy models.
"""

from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton

__all__ = ["PoseEstimation", "PoseEstimationSeries", "Skeleton"]
