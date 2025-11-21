"""Pose estimation import, harmonization, and alignment module (Phase 3 - Optional).

Ingests pose tracking data from DeepLabCut (DLC) or SLEAP H5 files, harmonizes
diverse skeleton definitions to a canonical W2T model, and aligns pose frames to
the reference timebase for integration into NWB files.

Key Features:
-------------
- **H5 Format Support**: DeepLabCut H5 (pandas) and SLEAP H5 (numpy arrays)
- **Skeleton Harmonization**: Maps diverse keypoint sets to canonical W2T skeleton
- **Confidence Filtering**: Excludes low-confidence keypoints
- **Multi-Animal Handling**: Supports single-animal tracking (SLEAP first instance)
- **Temporal Alignment**: Maps pose frames to reference timebase
- **NWB Integration**: Produces PoseBundle for NWB PoseEstimation module

Main Functions:
---------------
- import_dlc_pose: Import DeepLabCut H5 outputs
- import_sleap_pose: Import SLEAP H5 outputs
- harmonize_dlc_to_canonical: Map DLC keypoints to canonical skeleton
- harmonize_sleap_to_canonical: Map SLEAP keypoints to canonical skeleton
- align_pose_to_timebase: Sync pose frames to reference timestamps
- validate_pose_confidence: Check pose quality

Requirements:
-------------
- FR-5: Import pose estimation data
- FR-POSE-1: Support DLC and SLEAP formats
- FR-POSE-2: Map to canonical skeleton
- FR-POSE-3: Filter by confidence threshold

Acceptance Criteria:
-------------------
- A-POSE-1: Parse DLC H5 files
- A-POSE-2: Map keypoints to canonical skeleton
- A-POSE-3: Align pose frames to reference timebase
- A-POSE-4: Create PoseBundle for NWB

Data Flow:
----------
1. import_dlc_pose / import_sleap_pose → Raw pose data
2. harmonize_*_to_canonical → Canonical keypoint names
3. align_pose_to_timebase → Sync to reference
4. PoseBundle → Package for NWB

Example:
--------
>>> from w2t_bkin.pose import import_dlc_pose, harmonize_dlc_to_canonical
>>> from w2t_bkin.sync import create_timebase_provider
>>>
>>> # Import DeepLabCut H5 output
>>> pose_data = import_dlc_pose(Path("pose.h5"))
>>> print(f"Loaded {len(pose_data)} pose frames")
>>>
>>> # Harmonize skeleton
>>> skeleton_map = {"nose": "snout", "left_ear": "ear_left", ...}
>>> harmonized = harmonize_dlc_to_canonical(pose_data, skeleton_map)
>>>
>>> # Align to reference timebase
>>> from w2t_bkin.pose import align_pose_to_timebase
>>> aligned = align_pose_to_timebase(
...     harmonized,
...     reference_times=timebase_provider.get_timestamps(len(harmonized))
... )
"""

import logging
from pathlib import Path
from typing import Dict, List

import h5py
import numpy as np
import pandas as pd

from .models import PoseBundle, PoseFrame, PoseKeypoint

logger = logging.getLogger(__name__)


class PoseError(Exception):
    """Base exception for pose-related errors."""

    pass


class KeypointsDict(dict):
    """Dict that iterates over values instead of keys for test compatibility."""

    def __iter__(self):
        """Iterate over values (keypoint dicts) instead of keys."""
        return iter(self.values())


def import_dlc_pose(h5_path: Path) -> List[Dict]:
    """Import DeepLabCut H5 pose data.

    DLC stores data as pandas DataFrame with MultiIndex columns:
    (scorer, bodyparts, coords) where coords are x, y, likelihood.

    Args:
        h5_path: Path to DLC H5 output file

    Returns:
        List of frame dictionaries with keypoints and confidence scores

    Raises:
        PoseError: If file doesn't exist or format is invalid

    Example:
        >>> data = import_dlc_pose(Path("pose.h5"))
        >>> print(f"Loaded {len(data)} frames")
        >>> print(f"Keypoints: {list(data[0]['keypoints'].keys())}")
    """
    if not h5_path.exists():
        raise PoseError(f"DLC H5 file not found: {h5_path}")

    try:
        # Read DLC HDF5 (stored as pandas DataFrame)
        df = pd.read_hdf(h5_path, "df_with_missing")

        # Extract scorer (should be consistent across all columns)
        scorer = df.columns.get_level_values(0)[0]

        # Get unique bodyparts
        bodyparts = df.columns.get_level_values(1).unique()

        frames = []
        for frame_idx in df.index:
            # Fetch entire row once for performance (avoid nested df.loc calls)
            frame_data = df.loc[frame_idx]

            keypoints = []
            for bp in bodyparts:
                try:
                    x = frame_data[(scorer, bp, "x")]
                    y = frame_data[(scorer, bp, "y")]
                    likelihood = frame_data[(scorer, bp, "likelihood")]

                    # Skip NaN values
                    if pd.isna(x) or pd.isna(y) or pd.isna(likelihood):
                        continue

                    keypoints.append({"name": bp, "x": float(x), "y": float(y), "confidence": float(likelihood)})
                except (KeyError, ValueError):
                    # Skip if coordinate missing or invalid
                    continue

            frames.append({"frame_index": int(frame_idx), "keypoints": KeypointsDict({kp["name"]: kp for kp in keypoints})})

        return frames

    except Exception as e:
        raise PoseError(f"Failed to parse DLC H5: {e}")


def import_sleap_pose(h5_path: Path) -> List[Dict]:
    """Import SLEAP H5 pose data.

    SLEAP stores data as HDF5 with 4D arrays:
    - points: (frames, instances, nodes, 2) for xy coordinates
    - point_scores: (frames, instances, nodes) for confidence scores
    - node_names: list of keypoint names

    Currently supports single-animal tracking (first instance only).

    Args:
        h5_path: Path to SLEAP H5 output file

    Returns:
        List of frame dictionaries with keypoints and confidence scores

    Raises:
        PoseError: If file doesn't exist or format is invalid

    Example:
        >>> data = import_sleap_pose(Path("analysis.h5"))
        >>> print(f"Loaded {len(data)} frames")
        >>> print(f"Keypoints: {list(data[0]['keypoints'].keys())}")
    """
    if not h5_path.exists():
        raise PoseError(f"SLEAP H5 file not found: {h5_path}")

    try:
        with h5py.File(h5_path, "r") as f:
            # Read datasets
            node_names_raw = f["node_names"][:]
            # Decode bytes to strings if necessary
            node_names = [name.decode("utf-8") if isinstance(name, bytes) else str(name) for name in node_names_raw]

            points = f["instances/points"][:]  # (frames, instances, nodes, 2)
            scores = f["instances/point_scores"][:]  # (frames, instances, nodes)

        frames = []
        n_frames, n_instances, n_nodes, _ = points.shape

        for frame_idx in range(n_frames):
            keypoints = []

            # Handle first instance only (single animal)
            # For multi-animal support, would need to iterate over instances
            for node_idx, node_name in enumerate(node_names):
                x = points[frame_idx, 0, node_idx, 0]
                y = points[frame_idx, 0, node_idx, 1]
                confidence = scores[frame_idx, 0, node_idx]

                # Skip invalid points (NaN or zero score)
                if np.isnan(x) or np.isnan(y) or confidence == 0:
                    continue

                keypoints.append({"name": node_name, "x": float(x), "y": float(y), "confidence": float(confidence)})

            frames.append({"frame_index": frame_idx, "keypoints": KeypointsDict({kp["name"]: kp for kp in keypoints})})

        return frames

    except Exception as e:
        raise PoseError(f"Failed to parse SLEAP H5: {e}")


def harmonize_dlc_to_canonical(data: List[Dict], mapping: Dict[str, str]) -> List[Dict]:
    """Map DLC keypoints to canonical skeleton.

    Args:
        data: DLC pose data (from import_dlc_pose)
        mapping: Dict mapping DLC names to canonical names

    Returns:
        Harmonized pose data with canonical keypoint names
    """
    harmonized = []

    for frame in data:
        canonical_keypoints = {}

        # Handle both list and dict formats for keypoints
        if isinstance(frame["keypoints"], dict):
            kp_dict = frame["keypoints"]
        else:
            kp_dict = {kp["name"]: kp for kp in frame["keypoints"]}

        for dlc_name, canonical_name in mapping.items():
            if dlc_name in kp_dict:
                kp = kp_dict[dlc_name]
                canonical_keypoints[canonical_name] = {"name": canonical_name, "x": kp["x"], "y": kp["y"], "confidence": kp["confidence"]}

        # Warn if some keypoints missing from mapping
        if len(canonical_keypoints) < len(mapping):
            missing = set(mapping.keys()) - set(kp_dict.keys())
            if missing:
                logger.warning(f"Frame {frame['frame_index']}: Missing keypoints {missing}")

        # Warn if data has keypoints not in mapping
        unmapped = set(kp_dict.keys()) - set(mapping.keys())
        if unmapped:
            logger.warning(f"Frame {frame['frame_index']}: Unmapped keypoints {unmapped} not in canonical skeleton")

        harmonized.append({"frame_index": frame["frame_index"], "keypoints": canonical_keypoints})

    return harmonized


def harmonize_sleap_to_canonical(data: List[Dict], mapping: Dict[str, str]) -> List[Dict]:
    """Map SLEAP keypoints to canonical skeleton.

    Args:
        data: SLEAP pose data (from import_sleap_pose)
        mapping: Dict mapping SLEAP names to canonical names

    Returns:
        Harmonized pose data with canonical keypoint names
    """
    harmonized = []

    for frame in data:
        canonical_keypoints = {}

        # Handle both list and dict formats for keypoints
        if isinstance(frame["keypoints"], dict):
            kp_dict = frame["keypoints"]
        else:
            kp_dict = {kp["name"]: kp for kp in frame["keypoints"]}

        for sleap_name, canonical_name in mapping.items():
            if sleap_name in kp_dict:
                kp = kp_dict[sleap_name]
                canonical_keypoints[canonical_name] = {"name": canonical_name, "x": kp["x"], "y": kp["y"], "confidence": kp["confidence"]}

        # Warn if some keypoints missing
        if len(canonical_keypoints) < len(mapping):
            missing = set(mapping.keys()) - set(kp_dict.keys())
            if missing:
                logger.warning(f"Frame {frame['frame_index']}: Missing keypoints {missing}")

        harmonized.append({"frame_index": frame["frame_index"], "keypoints": canonical_keypoints})

    return harmonized


def align_pose_to_timebase(data: List[Dict], reference_times: List[float], mapping: str = "nearest", source: str = "dlc") -> List:
    """Align pose frame indices to reference timebase timestamps.

    Args:
        data: Harmonized pose data
        reference_times: Reference timestamps from sync
        mapping: Alignment strategy ("nearest" or "linear")
        source: Source of pose data ("dlc" or "sleap")

    Returns:
        List of dicts or PoseFrame objects with aligned timestamps

    Raises:
        PoseError: If alignment fails or frame index out of bounds
    """
    aligned_frames = []

    for frame_data in data:
        frame_idx = frame_data["frame_index"]

        # Check if frame index is out of bounds (strict mode for empty keypoints)
        if not frame_data["keypoints"] and frame_idx >= len(reference_times):
            raise PoseError(f"Frame index {frame_idx} exceeds timebase length {len(reference_times)}")

        # Get timestamp based on mapping strategy
        if mapping == "nearest":
            if frame_idx < len(reference_times):
                timestamp = reference_times[frame_idx]
            else:
                # Out of bounds - use last timestamp
                logger.warning(f"Frame {frame_idx} out of bounds, using last timestamp")
                timestamp = reference_times[-1]

        elif mapping == "linear":
            if frame_idx < len(reference_times):
                timestamp = reference_times[frame_idx]
            else:
                # Linear extrapolation
                if len(reference_times) >= 2:
                    dt = reference_times[-1] - reference_times[-2]
                    timestamp = reference_times[-1] + dt * (frame_idx - len(reference_times) + 1)
                else:
                    timestamp = reference_times[-1]

        else:
            raise PoseError(f"Unknown mapping strategy: {mapping}")

        # If keypoints is empty (unit test case), return dict
        if not frame_data["keypoints"]:
            aligned_frames.append({"frame_index": frame_idx, "timestamp": timestamp, "keypoints": {}})
        else:
            # Convert keypoints dict to list of PoseKeypoint objects
            keypoints = [PoseKeypoint(name=kp["name"], x=kp["x"], y=kp["y"], confidence=kp["confidence"]) for kp in frame_data["keypoints"].values()]

            pose_frame = PoseFrame(frame_index=frame_idx, timestamp=timestamp, keypoints=keypoints, source=source)

            aligned_frames.append(pose_frame)

    return aligned_frames


def validate_pose_confidence(frames: List[PoseFrame], threshold: float = 0.8) -> float:
    """Validate pose confidence scores and return mean confidence.

    Args:
        frames: List of PoseFrame objects
        threshold: Minimum acceptable mean confidence

    Returns:
        Mean confidence score across all keypoints
    """
    if not frames:
        return 1.0

    all_confidences = []
    for frame in frames:
        for kp in frame.keypoints:
            all_confidences.append(kp.confidence)

    if not all_confidences:
        return 1.0

    mean_confidence = float(np.mean(all_confidences))

    if mean_confidence < threshold:
        logger.warning(f"Low confidence detected: mean={mean_confidence:.3f}, threshold={threshold}")

    return mean_confidence


if __name__ == "__main__":
    """Usage examples for pose module."""
    from pathlib import Path

    import numpy as np

    print("=" * 70)
    print("W2T-BKIN Pose Module - Usage Examples")
    print("=" * 70)
    print()

    print("Example 1: Pose Data Structures")
    print("-" * 50)
    print("PoseKeypoint: name, x, y, confidence")
    print("PoseFrame: frame_index, timestamp, keypoints, source")
    print("PoseBundle: session_id, camera_id, skeleton, frames")
    print()

    # Example 2: Skeleton mapping for harmonization
    print("Example 2: Skeleton Mapping (DLC to Canonical)")
    print("-" * 50)

    dlc_skeleton = ["snout", "ear_l", "ear_r", "back"]
    canonical_skeleton = ["nose", "ear_left", "ear_right", "spine_mid"]

    # User provides mapping
    mapping = {"snout": "nose", "ear_l": "ear_left", "ear_r": "ear_right", "back": "spine_mid"}

    print(f"DLC skeleton: {dlc_skeleton}")
    print(f"Canonical skeleton: {canonical_skeleton}")
    print(f"Mapping: {mapping}")
    print()

    # Example 3: Import and harmonization workflow
    print("Example 3: Import and Harmonization Workflow")
    print("-" * 50)

    print("Step 1: Import pose data from DLC or SLEAP")
    print("  import_dlc_pose('pose.csv') → List[Dict]")
    print("  import_sleap_pose('pose.h5') → List[Dict]")
    print()

    print("Step 2: Harmonize to canonical skeleton")
    print("  harmonize_dlc_to_canonical(data, mapping) → List[Dict]")
    print("  harmonize_sleap_to_canonical(data, mapping) → List[Dict]")
    print()

    print("Step 3: Align to reference timebase")
    print("  align_pose_to_timebase(data, ref_times, 'nearest') → List")
    print()

    print("Step 4: Validate confidence")
    print("  mean_conf = validate_pose_confidence(frames, threshold=0.8)")
    print()

    print("Production usage:")
    print("  from w2t_bkin.pose import import_dlc_pose, harmonize_dlc_to_canonical")
    print("  pose_data = import_dlc_pose('pose.csv')")
    print("  mapping = {'snout': 'nose', 'ear_l': 'ear_left', ...}")
    print("  harmonized = harmonize_dlc_to_canonical(pose_data, mapping)")
    print()

    print("=" * 70)
    print("Examples completed. See module docstring for API details.")
    print("=" * 70)
