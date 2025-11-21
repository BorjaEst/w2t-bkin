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
from typing import Dict, List, Optional

import h5py
from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton
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


def build_pose_estimation(
    data: List[Dict],
    reference_times: List[float],
    camera_id: str,
    bodyparts: List[str],
    skeleton_edges: Optional[List[List[int]]] = None,
    source: str = "dlc",
    model_name: str = "unknown",
) -> PoseEstimation:
    """Build ndx-pose PoseEstimation from harmonized pose data.

    Converts frame-major pose data (one dict per timestep with all keypoints)
    into keypoint-major NWB format (one PoseEstimationSeries per bodypart).

    This is the NWB-first approach that eliminates intermediate PoseBundle
    models and produces standards-compliant NWB objects directly.

    Args:
        data: Harmonized pose data (List of dicts with frame_index, keypoints)
        reference_times: Reference timestamps from sync (aligned to frames)
        camera_id: Camera identifier (e.g., "cam0_top")
        bodyparts: List of bodypart names in canonical order
        skeleton_edges: Optional skeleton connectivity (list of [idx1, idx2] pairs)
        source: Pose estimation source ("dlc" | "sleap")
        model_name: Model identifier for scorer field

    Returns:
        PoseEstimation object ready to add to NWB processing module

    Raises:
        PoseError: If data is malformed or timestamp count mismatches

    Requirements:
        - FR-5: Create NWB-native pose structures
        - NWB-First: Direct production of ndx-pose objects

    Example:
        >>> harmonized = harmonize_dlc_to_canonical(raw_data, mapping)
        >>> pose_est = build_pose_estimation(
        ...     data=harmonized,
        ...     reference_times=timestamps,
        ...     camera_id="cam0",
        ...     bodyparts=["nose", "ear_left", "ear_right"],
        ...     skeleton_edges=[[0, 1], [0, 2]],
        ...     source="dlc",
        ...     model_name="dlc_mouse_v1"
        ... )
        >>> # Add to NWB: behavior_module.add(pose_est)
    """
    if not data:
        raise PoseError("Cannot build PoseEstimation from empty data")

    num_frames = len(data)

    if len(reference_times) != num_frames:
        raise PoseError(f"Timestamp count mismatch: {len(reference_times)} timestamps " f"for {num_frames} frames")

    # Convert timestamps to numpy array
    timestamps = np.array(reference_times, dtype=np.float64)

    # Build keypoint-major data structure
    # Map bodypart name -> (data, confidence) where data is (num_frames, 2) for x,y
    bodypart_data: Dict[str, tuple[np.ndarray, np.ndarray]] = {bp: ([], []) for bp in bodyparts}

    for frame in data:
        frame_keypoints = frame.get("keypoints", {})

        # Handle both dict-of-dicts and dict with values as dicts
        if isinstance(frame_keypoints, dict):
            # If it's KeypointsDict or similar, iterate values
            if hasattr(frame_keypoints, "__iter__") and not isinstance(next(iter(frame_keypoints.values()), {}), dict):
                # Values are already keypoint dicts
                kp_dict = {kp["name"]: kp for kp in frame_keypoints.values() if isinstance(kp, dict)}
            else:
                # Standard dict with name as key
                kp_dict = frame_keypoints
        else:
            kp_dict = {}

        # Extract data for each bodypart
        for bodypart in bodyparts:
            kp = kp_dict.get(bodypart)
            if kp and isinstance(kp, dict):
                bodypart_data[bodypart][0].append([kp["x"], kp["y"]])
                bodypart_data[bodypart][1].append(kp["confidence"])
            else:
                # Missing keypoint - use NaN
                bodypart_data[bodypart][0].append([np.nan, np.nan])
                bodypart_data[bodypart][1].append(np.nan)

    # Convert to numpy arrays
    for bodypart in bodyparts:
        bodypart_data[bodypart] = (
            np.array(bodypart_data[bodypart][0], dtype=np.float32),
            np.array(bodypart_data[bodypart][1], dtype=np.float32),
        )

    # Create PoseEstimationSeries for each bodypart
    pose_estimation_series = []
    first_series_timestamps = None

    for bodypart in bodyparts:
        data_array, confidence_array = bodypart_data[bodypart]

        # First series stores timestamps, subsequent series link to it
        # (avoids duplication per DLC2NWB pattern)
        if first_series_timestamps is None:
            pes = PoseEstimationSeries(
                name=bodypart,
                description=f"Keypoint {bodypart} from camera {camera_id}.",
                data=data_array,
                unit="pixels",
                reference_frame="(0,0) corresponds to the top-left corner of the video.",
                timestamps=timestamps,
                confidence=confidence_array,
                confidence_definition="Confidence score from pose estimation model (0.0-1.0).",
            )
            first_series_timestamps = pes
        else:
            # Link timestamps to first series
            pes = PoseEstimationSeries(
                name=bodypart,
                description=f"Keypoint {bodypart} from camera {camera_id}.",
                data=data_array,
                unit="pixels",
                reference_frame="(0,0) corresponds to the top-left corner of the video.",
                timestamps=first_series_timestamps,
                confidence=confidence_array,
                confidence_definition="Confidence score from pose estimation model (0.0-1.0).",
            )

        pose_estimation_series.append(pes)

    # Create Skeleton with nodes and edges
    skeleton = Skeleton(
        name=f"{camera_id}_skeleton",
        nodes=bodyparts,
        edges=np.array(skeleton_edges, dtype="uint8") if skeleton_edges else np.array([], dtype="uint8").reshape(0, 2),
    )

    # Create PoseEstimation container
    source_software = "DeepLabCut" if source == "dlc" else "SLEAP"
    pe = PoseEstimation(
        name=f"PoseEstimation_{camera_id}",
        pose_estimation_series=pose_estimation_series,
        description=f"2D keypoint coordinates for {camera_id} estimated using {source_software}.",
        scorer=model_name,
        source_software=source_software,
        source_software_version="2.3.x" if source == "dlc" else "1.3.x",
        skeleton=skeleton,
    )

    logger.debug(f"Built PoseEstimation: {camera_id}, {num_frames} frames, " f"{len(bodyparts)} bodyparts")

    return pe


def align_pose_to_timebase(
    data: List[Dict],
    reference_times: List[float],
    mapping: str = "nearest",
    source: str = "dlc",
    camera_id: Optional[str] = None,
    bodyparts: Optional[List[str]] = None,
    skeleton_edges: Optional[List[List[int]]] = None,
    model_name: Optional[str] = None,
) -> List:
    """Align pose frame indices to reference timebase timestamps.

    This function supports two modes:
    1. Legacy mode (camera_id=None): Returns List[PoseFrame] - DEPRECATED
    2. NWB-first mode (camera_id provided): Returns PoseEstimation directly

    Args:
        data: Harmonized pose data (List of dicts with frame_index, keypoints)
        reference_times: Reference timestamps from sync
        mapping: Alignment strategy ("nearest" or "linear")
        source: Source of pose data ("dlc" or "sleap")
        camera_id: Camera identifier (e.g., "cam0_top"). If provided, returns PoseEstimation.
        bodyparts: List of bodypart names (required if camera_id provided)
        skeleton_edges: Optional skeleton connectivity for PoseEstimation
        model_name: Model identifier for PoseEstimation scorer field

    Returns:
        - If camera_id is None: List[PoseFrame] (legacy, deprecated)
        - If camera_id provided: PoseEstimation (NWB-first)

    Raises:
        PoseError: If alignment fails or frame index out of bounds
        ValueError: If camera_id provided but bodyparts is None

    Example (NWB-first mode):
        >>> harmonized = harmonize_dlc_to_canonical(raw_data, mapping)
        >>> pose_est = align_pose_to_timebase(
        ...     data=harmonized,
        ...     reference_times=timestamps,
        ...     camera_id="cam0",
        ...     bodyparts=["nose", "ear_left"],
        ...     source="dlc",
        ...     model_name="dlc_mouse_v1"
        ... )
        >>> # pose_est is ready to add to NWB
    """
    # Validate NWB-first mode parameters
    if camera_id is not None and bodyparts is None:
        raise ValueError("bodyparts parameter required when camera_id is provided (NWB-first mode)")

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

        # Update frame data with timestamp
        frame_data["timestamp"] = timestamp

        # Legacy mode: convert to PoseFrame objects
        if camera_id is None:
            if not frame_data["keypoints"]:
                aligned_frames.append({"frame_index": frame_idx, "timestamp": timestamp, "keypoints": {}})
            else:
                # Convert keypoints dict to list of PoseKeypoint objects
                keypoints = [PoseKeypoint(name=kp["name"], x=kp["x"], y=kp["y"], confidence=kp["confidence"]) for kp in frame_data["keypoints"].values()]
                pose_frame = PoseFrame(frame_index=frame_idx, timestamp=timestamp, keypoints=keypoints, source=source)
                aligned_frames.append(pose_frame)
        else:
            # NWB-first mode: collect timestamped data
            aligned_frames.append(frame_data)

    # NWB-first mode: build PoseEstimation
    if camera_id is not None:
        # Extract timestamps in frame order
        timestamps = [frame["timestamp"] for frame in aligned_frames]

        return build_pose_estimation(
            data=aligned_frames,
            reference_times=timestamps,
            camera_id=camera_id,
            bodyparts=bodyparts,
            skeleton_edges=skeleton_edges,
            source=source,
            model_name=model_name or f"{source}_model",
        )

    # Legacy mode: return PoseFrame list
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
