"""Pose module-local models for pose estimation data.

This module defines models owned by the pose module for representing
pose estimation data from DeepLabCut or SLEAP, harmonized to a canonical
skeleton format and aligned to the session reference timebase.

Model ownership follows the target architecture where each module owns
its own models rather than sharing through a central domain package.

DEPRECATION NOTICE
------------------
The PoseBundle, PoseFrame, and PoseKeypoint models are DEPRECATED and will be
removed in a future release. These intermediate models are being phased out in
favor of the NWB-first architecture pattern.

For new code, use the NWB-first workflow:
    1. Use build_pose_estimation() to create ndx_pose.PoseEstimation objects directly
    2. Pass PoseEstimation objects to assemble_nwb(pose_estimations=[...])
    3. Avoid creating PoseBundle, PoseFrame, or PoseKeypoint instances

See MIGRATION.md for detailed migration guidance and examples.

Legacy code using PoseBundle will continue to work during the transition period,
but should be updated to the NWB-first pattern when possible.
"""

from typing import List, Literal
import warnings

from pydantic import BaseModel, Field

__all__ = ["PoseKeypoint", "PoseFrame", "PoseBundle"]


def _emit_deprecation_warning(model_name: str) -> None:
    """Emit deprecation warning for legacy pose models."""
    warnings.warn(
        f"{model_name} is deprecated and will be removed in a future release. "
        f"Use the NWB-first workflow instead: build_pose_estimation() → assemble_nwb(pose_estimations=[...]). "
        f"See MIGRATION.md for guidance.",
        DeprecationWarning,
        stacklevel=3,
    )


class PoseKeypoint(BaseModel):
    """Single keypoint in pose estimation.

    .. deprecated::
        PoseKeypoint is deprecated. Use build_pose_estimation() to create
        ndx_pose.PoseEstimation objects directly instead.

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

    def __init__(self, **data):
        _emit_deprecation_warning("PoseKeypoint")
        super().__init__(**data)


class PoseFrame(BaseModel):
    """Pose data for a single frame.

    .. deprecated::
        PoseFrame is deprecated. Use build_pose_estimation() to create
        ndx_pose.PoseEstimation objects directly instead.

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

    def __init__(self, **data):
        _emit_deprecation_warning("PoseFrame")
        super().__init__(**data)


class PoseBundle(BaseModel):
    """Harmonized pose data bundle aligned to reference timebase.

    .. deprecated::
        PoseBundle is deprecated. Use build_pose_estimation() to create
        ndx_pose.PoseEstimation objects directly instead.

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

    Example (DEPRECATED - use build_pose_estimation() instead):
        >>> from w2t_bkin.pose.models import PoseBundle
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

    def __init__(self, **data):
        _emit_deprecation_warning("PoseBundle")
        super().__init__(**data)
