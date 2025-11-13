"""Facemap motion energy domain models (Phase 3 - Optional).

This module defines models for Facemap facial motion energy analysis.
Facemap data includes ROI definitions and motion energy signals aligned
to the session reference timebase.

Model Hierarchy:
---------------
- FacemapBundle: Complete Facemap dataset aligned to timebase
  ├── FacemapROI (list)
  └── FacemapSignal (list)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Aligned**: Timestamps mapped to reference timebase
- **Cross-Validated**: Signals reference defined ROIs

Requirements:
-------------
- FR-6: Import/compute Facemap metrics
- FR-TB-1..6: Align to reference timebase

Acceptance Criteria:
-------------------
- A1, A3: Facemap data in NWB and QC report

Usage:
------
>>> from w2t_bkin.domain.facemap import FacemapBundle, FacemapROI, FacemapSignal
>>>
>>> roi = FacemapROI(
...     name="eye",
...     x=100,
...     y=50,
...     width=80,
...     height=60
... )
>>>
>>> signal = FacemapSignal(
...     roi_name="eye",
...     timestamps=[0.0, 0.033, 0.066],
...     values=[0.5, 0.7, 0.4],
...     sampling_rate=30.0
... )
>>>
>>> bundle = FacemapBundle(
...     session_id="Session-001",
...     camera_id="cam0",
...     rois=[roi],
...     signals=[signal],
...     alignment_method="nearest",
...     generated_at="2025-11-13T10:30:00Z"
... )

See Also:
---------
- w2t_bkin.facemap: Facemap processing
- w2t_bkin.sync: Timebase alignment
"""

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


class FacemapROI(BaseModel):
    """Region of interest for Facemap analysis.

    Defines a rectangular ROI on the face camera for motion energy
    extraction.

    Attributes:
        name: ROI identifier (e.g., "eye", "whisker", "nose")
        x: Top-left X coordinate (pixels)
        y: Top-left Y coordinate (pixels)
        width: ROI width (pixels)
        height: ROI height (pixels)

    Requirements:
        - FR-6: Import/compute Facemap metrics
    """

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="ROI identifier (e.g., 'eye', 'whisker', 'nose')")
    x: int = Field(..., description="Top-left X coordinate in pixels", ge=0)
    y: int = Field(..., description="Top-left Y coordinate in pixels", ge=0)
    width: int = Field(..., description="ROI width in pixels", gt=0)
    height: int = Field(..., description="ROI height in pixels", gt=0)


class FacemapSignal(BaseModel):
    """Time series signal from Facemap ROI.

    Motion energy or other signal extracted from an ROI, aligned
    to the session reference timebase.

    Attributes:
        roi_name: Name of source ROI (must match an ROI in FacemapBundle)
        timestamps: Aligned timestamps (seconds, reference timebase)
        values: Signal values (motion energy, 0.0-1.0 normalized)
        sampling_rate: Signal sampling rate (Hz)

    Requirements:
        - FR-6: Import/compute Facemap metrics
        - FR-TB-1..6: Align to reference timebase

    Note:
        Timestamps are aligned to the session reference timebase
        using the mapping strategy (nearest|linear) configured in
        timebase.mapping.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    roi_name: str = Field(..., description="Name of source ROI (must match an ROI in FacemapBundle)")
    timestamps: List[float] = Field(..., description="Aligned timestamps in seconds (reference timebase)")
    values: List[float] = Field(..., description="Motion energy signal values (normalized 0.0-1.0)")
    sampling_rate: float = Field(..., description="Signal sampling rate in Hz", gt=0)


class FacemapBundle(BaseModel):
    """Facemap data bundle aligned to reference timebase.

    Complete Facemap dataset for one camera with ROI definitions
    and aligned motion energy signals.

    Attributes:
        session_id: Session identifier
        camera_id: Camera identifier
        rois: List of ROI definitions
        signals: List of motion energy signals (one per ROI)
        alignment_method: Timebase alignment method ("nearest"|"linear")
        generated_at: ISO 8601 timestamp

    Requirements:
        - FR-6: Import/compute Facemap metrics
        - FR-TB-1..6: Align to reference timebase
        - A1: Include in NWB
        - A3: Include in QC report

    Validation:
        All signals must reference ROIs defined in the rois list.

    Example:
        >>> bundle = FacemapBundle(
        ...     session_id="Session-001",
        ...     camera_id="cam0",
        ...     rois=[FacemapROI(name="eye", ...)],
        ...     signals=[FacemapSignal(roi_name="eye", ...)],
        ...     alignment_method="nearest",
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str = Field(..., description="Session identifier")
    camera_id: str = Field(..., description="Camera identifier")
    rois: List[FacemapROI] = Field(..., description="List of ROI definitions")
    signals: List[FacemapSignal] = Field(..., description="List of motion energy signals (one per ROI)")
    alignment_method: Literal["nearest", "linear"] = Field(..., description="Timebase alignment method: 'nearest' | 'linear'")
    generated_at: str = Field(..., description="ISO 8601 timestamp of facemap bundle generation")

    @model_validator(mode="after")
    def validate_signals_match_rois(self) -> "FacemapBundle":
        """Validate that all signals reference defined ROIs.

        Ensures referential integrity between signals and ROIs.

        Raises:
            ValueError: If a signal references an undefined ROI.

        Requirements:
            - Data integrity check for cross-model references
        """
        roi_names = {roi.name for roi in self.rois}
        for signal in self.signals:
            if signal.roi_name not in roi_names:
                raise ValueError(f"Signal references undefined ROI: {signal.roi_name}. " f"Defined ROIs: {roi_names}")
        return self
