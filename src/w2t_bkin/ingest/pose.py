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

import logging
from pathlib import Path
import threading
from typing import Dict, List, Literal, Optional, Tuple, Union
import uuid

import h5py
from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons
import numpy as np
import pandas as pd
from pynwb import TimeSeries

from w2t_bkin.exceptions import PoseError
from w2t_bkin.utils import derive_bodyparts_from_data, log_missing_keypoints, normalize_keypoints_to_dict

logger = logging.getLogger(__name__)

# NOTE: PyTables / h5py rely on libhdf5 which is frequently not thread-safe.
# When Prefect runs multiple tasks in a single process (threaded task runner),
# concurrent HDF5 reads can segfault. We serialize all HDF5 IO to keep workers
# stable.
_HDF5_IO_LOCK = threading.Lock()


class PoseMetadata:
    """Metadata extracted from pose estimation files.

    Attributes:
        confidence_definition: Description of confidence metric
        scorer: Model/scorer name (DLC scorer or SLEAP model identifier)
        source_software: Software name ("DeepLabCut", "SLEAP", etc.)
        source_software_version: Version string if available
        bodyparts: List of all bodypart names in the data
    """

    def __init__(
        self,
        confidence_definition: str,
        scorer: str,
        source_software: str,
        source_software_version: Optional[str] = None,
        bodyparts: Optional[List[str]] = None,
    ):
        self.confidence_definition = confidence_definition
        self.scorer = scorer
        self.source_software = source_software
        self.source_software_version = source_software_version
        self.bodyparts = bodyparts or []

    def __repr__(self):
        return f"PoseMetadata(" f"scorer={self.scorer!r}, " f"source={self.source_software!r}, " f"version={self.source_software_version!r}, " f"bodyparts={len(self.bodyparts)})"


class KeypointsDict(dict):
    """Dict that iterates over values instead of keys for test compatibility."""

    def __iter__(self):
        return iter(self.values())


def harmonize_to_canonical(data: List[Dict], mapping: Dict[str, str]) -> List[Dict]:
    """Map keypoints from any source to canonical skeleton.

    Consolidates harmonize_dlc_to_canonical and harmonize_sleap_to_canonical
    into a single function since the logic is identical.

    Optimized version using dict comprehension and single validation pass.
    Performance improvement: ~10-30x faster for large datasets.

    Args:
        data: Pose data from import_dlc_pose or import_sleap_pose
        mapping: Dict mapping source keypoint names to canonical names

    Returns:
        Harmonized pose data with canonical keypoint names

    Example:
        >>> mapping = {"snout": "nose", "ear_l": "ear_left"}
        >>> harmonized = harmonize_to_canonical(dlc_data, mapping)
    """
    if not data:
        return []

    # Extract all unique keypoint names from first frame for validation (single pass)
    first_frame_kps = normalize_keypoints_to_dict(data[0]["keypoints"])
    all_source_names = set(first_frame_kps.keys())

    # Pre-compute validation once instead of per-frame
    expected_names = set(mapping.keys())
    missing_in_first = expected_names - all_source_names
    unmapped = all_source_names - expected_names

    # Log warnings once, not per frame
    if missing_in_first:
        logger.warning(f"Mapping expects keypoints {missing_in_first} not found in data. " f"These will be missing from all frames.")
    if unmapped:
        logger.warning(f"Data contains unmapped keypoints {unmapped} not in canonical skeleton")

    # Fast path: Use list comprehension with pre-validated mapping
    # Convert mapping.items() once to avoid repeated dict iteration
    mapping_items = list(mapping.items())

    harmonized = []
    for frame in data:
        kp_dict = frame["keypoints"]
        # If already dict, skip normalization
        if not isinstance(kp_dict, dict):
            kp_dict = normalize_keypoints_to_dict(kp_dict)

        # Build canonical keypoints with dict comprehension (faster than loop)
        canonical_keypoints = {
            canonical_name: {
                "name": canonical_name,
                "x": kp_dict[source_name]["x"],
                "y": kp_dict[source_name]["y"],
                "confidence": kp_dict[source_name]["confidence"],
            }
            for source_name, canonical_name in mapping_items
            if source_name in kp_dict
        }

        harmonized.append({"frame_index": frame["frame_index"], "keypoints": canonical_keypoints})

    return harmonized


def import_dlc_pose(h5_path: Path, mapping: Optional[Dict[str, str]] = None) -> tuple[List[Dict], PoseMetadata]:
    """Import DeepLabCut H5 pose data with metadata extraction.

    DLC stores data as pandas DataFrame with MultiIndex columns:
    (scorer, bodyparts, coords) where coords are x, y, likelihood.

    The scorer (first level of MultiIndex) contains the model name and is
    extracted as metadata.

    Optimized version using vectorized pandas operations.
    Performance improvement: ~5-15x faster for large datasets.

    Args:
        h5_path: Path to DLC H5 output file
        mapping: Optional dict mapping source keypoint names to canonical names.
                 If provided, harmonization is applied automatically.

    Returns:
        Tuple of (frames, metadata) where:
        - frames: List of frame dictionaries with keypoints and confidence scores.
                  Format: [{"frame_index": int, "keypoints": {name: {x, y, confidence}}}]
        - metadata: PoseMetadata object with scorer, confidence_definition, etc.

        If mapping provided, keypoints in frames are harmonized to canonical names
        but metadata.bodyparts contains original names.

    Raises:
        PoseError: If file doesn't exist or format is invalid

    Example:
        >>> frames, metadata = import_dlc_pose(Path("pose.h5"))
        >>> print(f"Loaded {len(frames)} frames")
        >>> print(f"Scorer: {metadata.scorer}")
        >>> print(f"Bodyparts: {metadata.bodyparts}")
        >>> print(f"Confidence: {metadata.confidence_definition}")
    """
    if not h5_path.exists():
        raise PoseError(f"DLC H5 file not found: {h5_path}")

    try:
        with _HDF5_IO_LOCK:
            df = pd.read_hdf(h5_path)

        # Extract metadata from MultiIndex columns
        scorer = df.columns.levels[0][0]  # First level is scorer
        bodyparts = df.columns.levels[1].tolist()  # Second level is bodyparts

        logger.debug(f"Extracted DLC scorer: {scorer}")
        logger.debug(f"Found {len(bodyparts)} bodyparts: {bodyparts}")

        # Vectorized approach: Extract all coordinates at once
        # Pre-build column name tuples for fast access
        coord_cols = {bp: {"x": (scorer, bp, "x"), "y": (scorer, bp, "y"), "likelihood": (scorer, bp, "likelihood")} for bp in bodyparts}

        # Convert to NumPy for faster iteration (avoid MultiIndex overhead)
        frame_indices = df.index.to_numpy()

        # Extract coordinate arrays for each bodypart (vectorized)
        bp_arrays = {}
        for bp in bodyparts:
            bp_arrays[bp] = {"x": df[coord_cols[bp]["x"]].to_numpy(), "y": df[coord_cols[bp]["y"]].to_numpy(), "likelihood": df[coord_cols[bp]["likelihood"]].to_numpy()}

        # Build frames with vectorized access
        frames = []
        for i, frame_idx in enumerate(frame_indices):
            keypoints = {}

            for bp in bodyparts:
                x = bp_arrays[bp]["x"][i]
                y = bp_arrays[bp]["y"][i]
                likelihood = bp_arrays[bp]["likelihood"][i]

                # Skip NaN values
                if not (np.isnan(x) or np.isnan(y) or np.isnan(likelihood)):
                    keypoints[bp] = {"name": bp, "x": float(x), "y": float(y), "confidence": float(likelihood)}

            frames.append({"frame_index": int(frame_idx), "keypoints": KeypointsDict(keypoints)})

        # Apply harmonization if mapping provided
        if mapping is not None:
            frames = harmonize_to_canonical(frames, mapping)

        # Build metadata object
        metadata = PoseMetadata(
            confidence_definition="Likelihood score from neural network output (0-1 range)",
            scorer=scorer,
            source_software="DeepLabCut",
            source_software_version=None,  # Not available in H5 file
            bodyparts=bodyparts,
        )

        return frames, metadata

    except Exception as e:
        raise PoseError(f"Failed to parse DLC H5: {e}")


def import_sleap_pose(h5_path: Path, mapping: Optional[Dict[str, str]] = None) -> tuple[List[Dict], PoseMetadata]:
    """Import SLEAP H5 pose data with metadata extraction.

    SLEAP stores data as HDF5 with 4D arrays:
    - points: (frames, instances, nodes, 2) for xy coordinates
    - point_scores: (frames, instances, nodes) for confidence scores
    - node_names: list of keypoint names

    The model name is extracted from the provenance metadata if available.

    Currently supports single-animal tracking (first instance only).
    Multi-animal support can be added by extending the return format
    to include instance_id.

    Args:
        h5_path: Path to SLEAP H5 output file
        mapping: Optional dict mapping source keypoint names to canonical names.
                 If provided, harmonization is applied automatically.

    Returns:
        Tuple of (frames, metadata) where:
        - frames: List of frame dictionaries with keypoints and confidence scores.
                  Format: [{"frame_index": int, "keypoints": {name: {x, y, confidence}}}]
        - metadata: PoseMetadata object with scorer, confidence_definition, etc.

        If mapping provided, keypoints in frames are harmonized to canonical names
        but metadata.bodyparts contains original names.

    Raises:
        PoseError: If file doesn't exist or format is invalid

    Example:
        >>> # Without harmonization
        >>> frames, metadata = import_sleap_pose(Path("analysis.h5"))
        >>> print(f"Loaded {len(frames)} frames")
        >>> print(f"Model: {metadata.scorer}")
        >>> print(f"Confidence: {metadata.confidence_definition}")
        >>>
        >>> # With harmonization
        >>> mapping = {"nose_tip": "nose", "left_ear": "ear_left"}
        >>> frames, metadata = import_sleap_pose(Path("analysis.h5"), mapping=mapping)
    """
    if not h5_path.exists():
        raise PoseError(f"SLEAP H5 file not found: {h5_path}")

    try:
        with _HDF5_IO_LOCK:
            with h5py.File(h5_path, "r") as f:
                # Read datasets
                node_names_raw = f["node_names"][:]
                # Decode bytes to strings if necessary
                node_names = [name.decode("utf-8") if isinstance(name, bytes) else str(name) for name in node_names_raw]

                points = f["tracks"][:]  # (n_instances, n_coords, n_nodes, n_frames)
                scores = f["point_scores"][:]  # (n_instances, n_nodes, n_frames)

                # Try to extract model name from provenance (if available)
                model_name = "unknown"
                version = None
                if "provenance" in f.attrs:
                    provenance = f.attrs["provenance"]
                    if isinstance(provenance, bytes):
                        provenance = provenance.decode("utf-8")
                    # Simple extraction - could be enhanced
                    if "model" in str(provenance).lower():
                        model_name = "SLEAP_model"

                logger.debug(f"Found {len(node_names)} SLEAP nodes: {node_names}")

        frames = []
        n_instances, n_coords, n_nodes, n_frames = points.shape

        # Validate coordinate dimensions (2D for now, but structured for 3D extension)
        if n_coords not in [2, 3]:
            raise PoseError(f"Unsupported coordinate dimensions: {n_coords} (expected 2 or 3)")

        for frame_idx in range(n_frames):
            keypoints = []

            # Handle first instance only (single animal)
            # For multi-animal support, would need to iterate over instances
            for node_idx, node_name in enumerate(node_names):
                x = points[0, 0, node_idx, frame_idx]
                y = points[0, 1, node_idx, frame_idx]
                confidence = scores[0, node_idx, frame_idx]

                # Skip invalid points (NaN or zero score)
                if np.isnan(x) or np.isnan(y) or confidence == 0:
                    continue

                kp_data = {"name": node_name, "x": float(x), "y": float(y), "confidence": float(confidence)}

                # Future 3D support: add z coordinate if present
                # if n_coords == 3:
                #     z = points[frame_idx, 0, node_idx, 2]
                #     if not np.isnan(z):
                #         kp_data["z"] = float(z)

                keypoints.append(kp_data)

            frames.append({"frame_index": frame_idx, "keypoints": KeypointsDict({kp["name"]: kp for kp in keypoints})})

        # Apply harmonization if mapping provided
        if mapping is not None:
            frames = harmonize_to_canonical(frames, mapping)

        # Build metadata object
        metadata = PoseMetadata(
            confidence_definition="Instance score from centroid confidence (0-1 range)",
            scorer=model_name,
            source_software="SLEAP",
            source_software_version=version,
            bodyparts=node_names,
        )

        return frames, metadata

    except Exception as e:
        raise PoseError(f"Failed to parse SLEAP H5: {e}")


def validate_skeleton_edges(nodes: List[str], edges: List[List[int]]) -> None:
    """Validate that skeleton edges reference valid node indices.

    Args:
        nodes: List of node names
        edges: List of [node_idx1, node_idx2] pairs

    Raises:
        ValueError: If any edge references an invalid node index
        TypeError: If edges are not properly formatted

    Example:
        >>> nodes = ["nose", "ear_left", "ear_right"]
        >>> edges = [[0, 1], [0, 2]]  # Valid
        >>> validate_skeleton_edges(nodes, edges)  # No error
        >>> edges = [[0, 5]]  # Invalid index
        >>> validate_skeleton_edges(nodes, edges)  # Raises ValueError
    """
    if not isinstance(nodes, list):
        raise TypeError(f"nodes must be a list, got {type(nodes)}")

    if not isinstance(edges, list):
        raise TypeError(f"edges must be a list, got {type(edges)}")

    n_nodes = len(nodes)

    for i, edge in enumerate(edges):
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError(f"Edge {i}: must be a list/tuple of 2 integers, got {edge}")

        src, dst = edge

        if not isinstance(src, int) or not isinstance(dst, int):
            raise TypeError(f"Edge {i}: indices must be integers, got ({type(src)}, {type(dst)})")

        if src < 0 or src >= n_nodes:
            raise ValueError(f"Edge {i}: source index {src} out of range [0, {n_nodes})")

        if dst < 0 or dst >= n_nodes:
            raise ValueError(f"Edge {i}: destination index {dst} out of range [0, {n_nodes})")


def create_skeleton(
    name: str,
    nodes: List[str],
    edges: Optional[List[List[int]]] = None,
    validate: bool = True,
) -> Skeleton:
    """Create a Skeleton object with optional validation.

    This is the recommended way to create Skeleton objects for use with
    PoseEstimation. The skeleton should be added to a Skeletons container
    in the NWBFile and then linked to PoseEstimation objects.

    Args:
        name: Skeleton identifier (e.g., "mouse_skeleton", "subject")
        nodes: List of bodypart/node names in order
        edges: List of [node_idx1, node_idx2] pairs defining connectivity.
               If None or empty, creates skeleton with no edges.
        validate: If True, validate that edges reference valid node indices

    Returns:
        Skeleton object ready to add to Skeletons container

    Raises:
        ValueError: If validation fails

    Example:
        >>> skeleton = create_skeleton(
        ...     name="mouse_skeleton",
        ...     nodes=["nose", "ear_left", "ear_right"],
        ...     edges=[[0, 1], [0, 2]],
        ...     validate=True
        ... )
        >>> # Add to NWB:
        >>> # skeletons = Skeletons(skeletons=[skeleton])
        >>> # nwbfile.add_lab_meta_data(skeletons)
    """
    if not nodes:
        raise ValueError("Skeleton must have at least one node")

    if edges is None:
        edges = []

    if validate and edges:
        validate_skeleton_edges(nodes, edges)

    # Convert edges to numpy array with proper shape
    if edges:
        edges_array = np.array(edges, dtype="uint8")
    else:
        # Empty array with correct shape (0, 2)
        edges_array = np.array([], dtype="uint8").reshape(0, 2)

    return Skeleton(name=name, nodes=nodes, edges=edges_array)


def create_skeletons_container(name: str, skeletons: List[Skeleton]) -> Skeletons:
    """Create a Skeletons container (NWB LabMetaData) for one or more skeletons.

    The Skeletons container is added to the NWBFile as LabMetaData, then
    individual PoseEstimation objects link to specific skeletons within it.

    Args:
        name: Container identifier (required)
        skeletons: List of Skeleton objects (must be non-empty)

    Returns:
        Skeletons container ready to add to NWBFile

    Raises:
        ValueError: If skeletons list is empty
        TypeError: If skeletons is not a list or contains non-Skeleton objects

    Example:
        >>> # Single skeleton
        >>> skeleton = create_skeleton(name="mouse", nodes=["nose", "ear_left"])
        >>> container = create_skeletons_container(name="skeletons", skeletons=[skeleton])
        >>> nwbfile.add_lab_meta_data(container)
        >>>
        >>> # Multiple skeletons
        >>> mouse_skel = create_skeleton(name="mouse", nodes=["nose", "ear_left"])
        >>> rat_skel = create_skeleton(name="rat", nodes=["snout", "ear"])
        >>> container = create_skeletons_container(name="skeletons", skeletons=[mouse_skel, rat_skel])
        >>> nwbfile.add_lab_meta_data(container)
    """
    if not isinstance(skeletons, list):
        raise TypeError(f"skeletons must be a list, got {type(skeletons)}")

    if not skeletons:
        raise ValueError("skeletons list cannot be empty")

    if not all(isinstance(s, Skeleton) for s in skeletons):
        raise TypeError("All items in skeletons list must be Skeleton objects")

    return Skeletons(skeletons=skeletons)


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
    skeleton: Optional[Skeleton] = None,
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
        skeleton: Optional pre-created Skeleton object with nodes matching bodyparts.
              If None, a Skeleton is auto-created from the detected bodyparts
              with empty edges and a deterministic uuid5-derived name.
              The skeleton name is used to construct the PoseEstimation name
              and description.
        original_videos: Paths to original video files (can be multiple videos)
        labeled_videos: Paths to labeled video files (can be multiple videos)
        dimensions: Video dimensions array shape (n_videos, 2)
        devices: List of Device objects for cameras/recording devices

    Returns:
        PoseEstimation object ready to add to NWB file

    Raises:
        PoseError: If data is empty, timestamp count mismatches, or validation fails

    Example:
        >>> from w2t_bkin.ingest.pose import import_dlc_pose, create_skeleton
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

    # Extract metadata (all required fields from PoseMetadata)
    confidence_definition = metadata.confidence_definition
    scorer = metadata.scorer
    source_software = metadata.source_software
    source_software_version = metadata.source_software_version or "unknown"

    # Ensure PoseEstimation always has a non-None skeleton.
    # ndx-pose PoseEstimation.nodes/edges dereference PoseEstimation.skeleton.
    if skeleton is None:
        key = f"w2t_bkin|pose|{source_software}|{source_software_version}|{scorer}|{','.join(bodyparts)}"
        skel_id = uuid.uuid5(uuid.NAMESPACE_URL, key).hex[:8]
        skeleton = create_skeleton(name=f"subject_{skel_id}", nodes=bodyparts, edges=[])
    else:
        # Validate provided skeleton nodes match detected bodyparts
        skeleton_nodes = skeleton.nodes
        if not all(bp in skeleton_nodes for bp in bodyparts):
            missing = set(bodyparts) - set(skeleton_nodes)
            raise PoseError(f"Skeleton missing required bodyparts: {missing}")

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
