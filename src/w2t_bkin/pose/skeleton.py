"""Skeleton management utilities for pose estimation.

Provides functions to create, validate, and manage Skeleton objects
for use with ndx-pose PoseEstimation containers.

Key Functions:
--------------
- validate_skeleton_edges: Validate edge indices against node list
- create_skeleton: Factory for individual Skeleton objects
- create_skeletons_container: Factory for Skeletons container (NWB LabMetaData)

OOP Design:
-----------
This module follows the Factory pattern, providing clean constructors
for ndx-pose objects with proper validation and defaults.
"""

from typing import List, Optional

from ndx_pose import Skeleton, Skeletons
import numpy as np


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


def create_skeletons_container(
    name: str,
    skeletons: List[Skeleton],
) -> Skeletons:
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


__all__ = ["validate_skeleton_edges", "create_skeleton", "create_skeletons_container"]
