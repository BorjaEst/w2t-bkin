"""Pose estimation domain models (Phase 3 - Optional).

This module defines models for pose estimation data from DeepLabCut
or SLEAP. Pose data is harmonized to a canonical skeleton format and
aligned to the session reference timebase.

Model Hierarchy:
---------------
- PoseBundle: Complete pose dataset aligned to timebase
  └── PoseFrame (list)
      └── PoseKeypoint (list)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Harmonized**: Canonical skeleton across DLC/SLEAP
- **Aligned**: Timestamps mapped to reference timebase

Requirements:
-------------
- FR-5: Import and harmonize pose results
- FR-TB-1..6: Align to reference timebase

Acceptance Criteria:
-------------------
- A1, A3: Pose data in NWB and QC report

Usage:
------
>>> from w2t_bkin.domain.pose import PoseBundle, PoseFrame, PoseKeypoint
>>>
>>> keypoint = PoseKeypoint(
...     name="nose",
...     x=320.5,
...     y=240.2,
...     confidence=0.95
... )
>>>
>>> frame = PoseFrame(
...     frame_index=0,
...     timestamp=0.0,
...     keypoints=[keypoint],
...     source="dlc"
... )
>>>
>>> bundle = PoseBundle(
...     session_id="Session-001",
...     camera_id="cam0",
...     model_name="dlc_mouse_v1",
...     skeleton="mouse_12pt",
...     frames=[frame],
...     alignment_method="nearest",
...     mean_confidence=0.95,
...     generated_at="2025-11-13T10:30:00Z"
... )

See Also:
---------
- w2t_bkin.pose: Pose import and harmonization
- w2t_bkin.sync: Timebase alignment
"""

from typing import List, Literal

from pydantic import BaseModel, Field


class PoseKeypoint(BaseModel):
    """Single keypoint in pose estimation.

    Represents a 2D keypoint location with confidence score.

    Attributes:
        name: Keypoint name (from canonical skeleton)
        x: X coordinate (pixels)
        y: Y coordinate (pixels)
        confidence: Confidence score (0.0-1.0)

    Requirements:
        - FR-5: Preserve confidence scores
    """

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="Keypoint name from canonical skeleton (e.g., 'nose', 'left_ear')")
    x: float = Field(..., description="X coordinate in pixels")
    y: float = Field(..., description="Y coordinate in pixels")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)", ge=0.0, le=1.0)


class PoseFrame(BaseModel):
    """Pose data for a single frame.

    Contains all keypoints for one video frame with aligned timestamp.

    Attributes:
        frame_index: Video frame index (0-indexed)
        timestamp: Aligned timestamp (seconds, reference timebase)
        keypoints: List of keypoints for this frame
        source: Pose estimation source ("dlc" | "sleap")

    Requirements:
        - FR-5: Harmonize pose data
        - FR-TB-1..6: Align to reference timebase

    Note:
        Timestamps are aligned to the session reference timebase
        using the mapping strategy (nearest|linear) configured in
        timebase.mapping.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    frame_index: int = Field(..., description="Video frame index (0-indexed)", ge=0)
    timestamp: float = Field(..., description="Aligned timestamp in seconds (reference timebase)")
    keypoints: List[PoseKeypoint] = Field(..., description="List of keypoints for this frame")
    source: Literal["dlc", "sleap"] = Field(..., description="Pose estimation source: 'dlc' (DeepLabCut) | 'sleap' (SLEAP)")


class PoseBundle(BaseModel):
    """Harmonized pose data bundle aligned to reference timebase.

    Complete pose dataset for one camera, harmonized to canonical
    skeleton and aligned to the session reference timebase.

    Attributes:
        session_id: Session identifier
        camera_id: Camera identifier
        model_name: Pose model identifier (e.g., "dlc_mouse_v1")
        skeleton: Canonical skeleton name (e.g., "mouse_12pt")
        frames: List of pose frames
        alignment_method: Timebase alignment method ("nearest"|"linear")
        mean_confidence: Mean confidence across all keypoints
        generated_at: ISO 8601 timestamp

    Requirements:
        - FR-5: Import and harmonize pose results
        - FR-TB-1..6: Align to reference timebase
        - A1: Include in NWB
        - A3: Include in QC report

    Example:
        >>> bundle = PoseBundle(
        ...     session_id="Session-001",
        ...     camera_id="cam0",
        ...     model_name="dlc_mouse_v1",
        ...     skeleton="mouse_12pt",
        ...     frames=[...],
        ...     alignment_method="nearest",
        ...     mean_confidence=0.89,
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str = Field(..., description="Session identifier")
    camera_id: str = Field(..., description="Camera identifier")
    model_name: str = Field(..., description="Pose model identifier (e.g., 'dlc_mouse_v1', 'sleap_rat_16pt')")
    skeleton: str = Field(..., description="Canonical skeleton name (e.g., 'mouse_12pt', 'rat_16pt')")
    frames: List[PoseFrame] = Field(..., description="List of pose frames with aligned timestamps")
    alignment_method: Literal["nearest", "linear"] = Field(..., description="Timebase alignment method: 'nearest' | 'linear'")
    mean_confidence: float = Field(..., description="Mean confidence across all keypoints and frames", ge=0.0, le=1.0)
    generated_at: str = Field(..., description="ISO 8601 timestamp of pose bundle generation")
