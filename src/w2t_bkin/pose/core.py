import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

import h5py
from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton
import numpy as np
import pandas as pd
from pynwb import TimeSeries

from ..exceptions import PoseError
from ..utils import derive_bodyparts_from_data
from .io import PoseMetadata, harmonize_to_canonical, import_dlc_pose, import_sleap_pose
from .skeleton import create_skeleton

logger = logging.getLogger(__name__)


def build_pose_estimation_series(
    bodypart: str,
    pose_data: List[Dict],
    timestamps: Union[np.ndarray, List[float], TimeSeries],
    confidence_definition: Optional[str] = None,
) -> PoseEstimationSeries:
    """Build a PoseEstimationSeries for a single body part.

    Extracts x, y coordinates and confidence values from pose data and creates
    an ndx-pose PoseEstimationSeries object. Handles missing keypoints by
    inserting NaN values.

    Args:
        bodypart: Name of the body part (e.g., "nose", "ear_left")
        pose_data: List of frame dictionaries with keypoints
        timestamps: Timestamps for each frame (array, list, or TimeSeries link)
        confidence_definition: Description of confidence metric (optional)

    Returns:
        PoseEstimationSeries object for the body part

    Example:
        >>> series = build_pose_estimation_series(
        ...     bodypart="nose",
        ...     pose_data=harmonized_data,
        ...     timestamps=np.array([0.0, 0.033, 0.066]),
        ...     confidence_definition="DLC likelihood score"
        ... )
    """
    n_frames = len(pose_data)

    # Preallocate arrays for data (use float32 for memory efficiency)
    data = np.full((n_frames, 2), np.nan, dtype=np.float32)  # (frames, 2) for x, y
    confidence = np.full(n_frames, np.nan, dtype=np.float32)

    # Optimized extraction: Batch collect valid keypoints first
    x_vals = []
    y_vals = []
    conf_vals = []
    valid_indices = []

    # Single pass through data
    for i, frame in enumerate(pose_data):
        kp_dict = frame.get("keypoints", {})

        # Direct dict access (skip normalization if possible)
        if isinstance(kp_dict, dict) and bodypart in kp_dict:
            kp = kp_dict[bodypart]
            valid_indices.append(i)
            x_vals.append(kp["x"])
            y_vals.append(kp["y"])
            conf_vals.append(kp["confidence"])

    # Vectorized assignment (much faster than individual indexing)
    if valid_indices:
        valid_indices = np.array(valid_indices, dtype=np.int32)
        data[valid_indices, 0] = x_vals
        data[valid_indices, 1] = y_vals
        confidence[valid_indices] = conf_vals

    # Create PoseEstimationSeries
    return PoseEstimationSeries(
        name=bodypart,
        description=f"Estimated position of {bodypart} over time.",
        data=data,
        unit="pixels",
        reference_frame="(0,0) corresponds to the top-left corner of the video.",
        timestamps=timestamps,
        confidence=confidence,
        confidence_definition=confidence_definition,
    )


def build_pose_estimation(
    data: Tuple[List[Dict], PoseMetadata],
    reference_times: List[float],
    skeleton: Skeleton,
    original_videos: Optional[List[str]] = None,
    labeled_videos: Optional[List[str]] = None,
    dimensions: Optional[np.ndarray] = None,
    devices: Optional[List] = None,
) -> PoseEstimation:
    """Build a PoseEstimation object from pose data and metadata.

    Creates an ndx-pose PoseEstimation container with all PoseEstimationSeries
    for tracked body parts. Accepts data as a tuple (pose_data, metadata) which
    matches the return signature of import_dlc_pose() and import_sleap_pose(),
    simplifying the construction workflow.

    Args:
        data: Tuple of (pose_data, metadata) as returned by import_dlc_pose() or
              import_sleap_pose(). The pose_data contains frame dictionaries with
              keypoints, and metadata contains scorer, confidence_definition, etc.
              Bodyparts are auto-detected from the pose_data.
        reference_times: Timestamps for each frame (must match frame count)
        skeleton: Pre-created Skeleton object with nodes matching bodyparts.
                  Use create_skeleton() to create this. The skeleton name is used
                  to construct the PoseEstimation name and description.
        original_videos: Paths to original video files (can be multiple videos)
        labeled_videos: Paths to labeled video files (can be multiple videos)
        dimensions: Video dimensions array shape (n_videos, 2)
        devices: List of Device objects for cameras/recording devices

    Returns:
        PoseEstimation object ready to add to NWB file

    Raises:
        PoseError: If data is empty, timestamp count mismatches, or validation fails

    Example:
        >>> from w2t_bkin.pose import import_dlc_pose, create_skeleton
        >>>
        >>> # Import data (returns tuple with pose_data and metadata)
        >>> dlc_data = import_dlc_pose(h5_path)
        >>>
        >>> # Create skeleton from metadata bodyparts
        >>> _, metadata = dlc_data
        >>> skeleton = create_skeleton(
        ...     name="mouse_skeleton",
        ...     nodes=metadata.bodyparts,
        ...     edges=[[0, 1], [0, 2]]
        ... )
        >>>
        >>> # Build pose estimation (pass tuple directly)
        >>> pe = build_pose_estimation(
        ...     data=dlc_data,  # Pass entire tuple from import_dlc_pose
        ...     reference_times=[0.0, 0.033, 0.066],
        ...     skeleton=skeleton,
        ...     original_videos=["camera0.mp4"],
        ...     devices=[camera_device]
        ... )
    """
    # Unpack data tuple
    pose_data, metadata = data

    # Validation
    if not pose_data:
        raise PoseError("Cannot build PoseEstimation from empty pose data")

    if len(reference_times) != len(pose_data):
        raise PoseError(f"Timestamp count mismatch: {len(reference_times)} timestamps " f"for {len(pose_data)} frames")

    # Auto-detect bodyparts from pose_data
    bodyparts = derive_bodyparts_from_data(pose_data)
    logger.debug(f"Auto-detected bodyparts: {bodyparts}")

    if not bodyparts:
        raise PoseError("No bodyparts found in pose data")

    # Validate skeleton nodes match bodyparts
    skeleton_nodes = skeleton.nodes
    if not all(bp in skeleton_nodes for bp in bodyparts):
        missing = set(bodyparts) - set(skeleton_nodes)
        raise PoseError(f"Skeleton missing required bodyparts: {missing}")

    # Extract metadata (all required fields from PoseMetadata)
    confidence_definition = metadata.confidence_definition
    scorer = metadata.scorer
    source_software = metadata.source_software
    source_software_version = metadata.source_software_version or "unknown"

    # Convert reference_times to numpy array
    timestamps_array = np.array(reference_times, dtype=float)

    # Build PoseEstimationSeries for each bodypart
    pose_estimation_series = []
    for i, bodypart in enumerate(bodyparts):
        # First series gets timestamps array, subsequent link to first
        if i == 0:
            series_timestamps = timestamps_array
        else:
            # Link to first series' timestamps to avoid duplication
            series_timestamps = pose_estimation_series[0]

        series = build_pose_estimation_series(
            bodypart=bodypart,
            pose_data=pose_data,
            timestamps=series_timestamps,
            confidence_definition=confidence_definition,
        )
        pose_estimation_series.append(series)

    logger.debug(f"Built {len(pose_estimation_series)} PoseEstimationSeries for {skeleton.name}")

    # Create description using skeleton name and metadata
    description = f"Pose estimation using {source_software}. Scorer: {scorer}. Skeleton: {skeleton.name}"

    # Build PoseEstimation container (name derived from skeleton)
    return PoseEstimation(
        name=f"PoseEstimation_{skeleton.name}",
        pose_estimation_series=pose_estimation_series,
        description=description,
        original_videos=original_videos,
        labeled_videos=labeled_videos,
        dimensions=dimensions,
        devices=devices,
        scorer=scorer,
        source_software=source_software,
        source_software_version=source_software_version,
        skeleton=skeleton,
    )


def validate_pose_confidence(*args, **kwargs):
    """Stub function for validate_pose_confidence.

    This function is not yet implemented. It will be added in a future update.
    """
    raise NotImplementedError("validate_pose_confidence is not yet implemented.")
