"""Pose estimation processing module.

Provides functions for importing, harmonizing, and building NWB-native
pose estimation data from DeepLabCut and SLEAP.

Key Functions:
--------------
- import_dlc_pose: Import DeepLabCut H5 files
- import_sleap_pose: Import SLEAP H5 files
- harmonize_to_canonical: Map keypoints to canonical skeleton
- build_pose_estimation: Build ndx-pose PoseEstimation objects
- build_pose_estimation_series: Build individual PoseEstimationSeries
- create_skeleton: Create Skeleton objects for pose data

Re-exported ndx-pose classes:
------------------------------
- PoseEstimation: Main container for pose estimation data
- PoseEstimationSeries: Time series for individual keypoints
- Skeleton: Skeleton definition with nodes and edges
- Skeletons: Container for multiple skeletons
"""

# Import ndx-pose classes for re-export
from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons

from ..exceptions import PoseError
from .core import build_pose_estimation, build_pose_estimation_series, validate_pose_confidence
from .io import harmonize_to_canonical, import_dlc_pose, import_sleap_pose
from .skeleton import create_skeleton, create_skeletons_container, validate_skeleton_edges

__all__ = [
    # ndx-pose classes
    "PoseEstimation",
    "PoseEstimationSeries",
    "Skeleton",
    "Skeletons",
    # w2t_bkin functions and classes
    "PoseError",
    "build_pose_estimation",
    "build_pose_estimation_series",
    "create_skeleton",
    "create_skeletons_container",
    "harmonize_to_canonical",
    "import_dlc_pose",
    "import_sleap_pose",
    "validate_pose_confidence",
    "validate_skeleton_edges",
]
