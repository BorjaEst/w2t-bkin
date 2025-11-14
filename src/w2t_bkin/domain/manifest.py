"""Manifest and verification domain models (Phase 1).

This module defines models for file discovery (Manifest) and frame/TTL
verification results. These models track discovered files and their
validation status.

Model Hierarchy:
---------------
- Manifest
  ├── ManifestCamera (list)
  ├── ManifestTTL (list)
  └── bpod_files (optional list)

- VerificationSummary
  └── CameraVerificationResult (list)

- VerificationResult
  └── CameraVerificationResult (list)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Optional Counts**: ManifestCamera supports fast discovery (counts=None)
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation

Requirements:
-------------
- FR-1: Discover files from patterns
- FR-2, FR-3: Frame/TTL verification with tolerance
- FR-13: Persist verification_summary.json
- FR-15: Validate camera-TTL references
- FR-16: Warning behavior on mismatch

Acceptance Criteria:
-------------------
- A6, A7: Verification sidecars and error reporting

Usage:
------
>>> from w2t_bkin.ingest import build_and_count_manifest
>>> manifest = build_and_count_manifest(config, session)
>>> manifest.cameras[0].frame_count  # int or None
>>>
>>> from w2t_bkin.domain.manifest import VerificationSummary
>>> summary = VerificationSummary(
...     session_id="Session-001",
...     cameras=[...],
...     generated_at="2025-11-13T10:30:00Z"
... )

See Also:
---------
- w2t_bkin.ingest: Manifest building and verification
- design.md: Sidecar schemas
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ManifestCamera(BaseModel):
    """Camera entry in manifest with discovered files.

    This model tracks discovered video files and their verification counts.
    Counts are optional to support fast discovery mode (skip counting).

    Attributes:
        camera_id: Camera identifier from session.toml
        ttl_id: Referenced TTL channel for verification
        video_files: List of absolute paths to video files
        frame_count: Total frame count (None = not counted yet)
        ttl_pulse_count: Total TTL pulse count (None = not counted yet)

    Design Notes:
        - None = not counted (fast discovery)
        - int >= 0 = counted value
        - Absolute paths are enforced during manifest building

    Requirements:
        - FR-1: File discovery
        - FR-2: Frame/TTL counting for verification
    """

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str = Field(..., description="Camera identifier from session.toml")
    ttl_id: str = Field(..., description="Referenced TTL channel ID for verification")
    video_files: List[str] = Field(..., description="List of absolute paths to discovered video files")
    frame_count: Optional[int] = Field(default=None, description="Total frame count across all videos (None = not counted yet)")
    ttl_pulse_count: Optional[int] = Field(default=None, description="Total TTL pulse count (None = not counted yet)")


class ManifestTTL(BaseModel):
    """TTL entry in manifest with discovered files.

    Attributes:
        ttl_id: TTL channel identifier
        files: List of absolute paths to TTL files

    Requirements:
        - FR-1: TTL file discovery
    """

    model_config = {"frozen": True, "extra": "forbid"}

    ttl_id: str = Field(..., description="TTL channel identifier")
    files: List[str] = Field(..., description="List of absolute paths to discovered TTL files")


class Manifest(BaseModel):
    """Manifest tracking all discovered files for a session.

    Built by ingest.build_and_count_manifest() and persisted as manifest.json.
    Links session specifications to actual discovered files with optional
    verification counts.

    Attributes:
        session_id: Session identifier
        cameras: List of camera manifest entries
        ttls: List of TTL manifest entries
        bpod_files: List of Bpod file paths (optional)

    Requirements:
        - FR-1: Complete file discovery
        - FR-13: Persist manifest for downstream stages

    Example:
        >>> manifest = Manifest(
        ...     session_id="Session-001",
        ...     cameras=[ManifestCamera(...)],
        ...     ttls=[ManifestTTL(...)],
        ...     bpod_files=["path/to/session.mat"]
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str = Field(..., description="Session identifier")
    cameras: List[ManifestCamera] = Field(default_factory=list, description="List of camera manifest entries")
    ttls: List[ManifestTTL] = Field(default_factory=list, description="List of TTL manifest entries")
    bpod_files: Optional[List[str]] = Field(default=None, description="List of Bpod .mat file paths (optional)")


class CameraVerificationResult(BaseModel):
    """Verification result for a single camera.

    Captures the frame/TTL count comparison and mismatch status.

    Attributes:
        camera_id: Camera identifier
        ttl_id: Referenced TTL channel
        frame_count: Total video frames
        ttl_pulse_count: Total TTL pulses
        mismatch: Absolute difference |frame_count - ttl_pulse_count|
        verifiable: Whether camera has valid TTL reference
        status: "pass" | "warn" | "fail"

    Requirements:
        - FR-2: Frame/TTL comparison
        - FR-3: Abort on excessive mismatch
        - FR-16: Warning behavior
    """

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str = Field(..., description="Camera identifier")
    ttl_id: str = Field(..., description="Referenced TTL channel ID")
    frame_count: int = Field(..., description="Total video frame count", ge=0)
    ttl_pulse_count: int = Field(..., description="Total TTL pulse count", ge=0)
    mismatch: int = Field(..., description="Absolute difference |frame_count - ttl_pulse_count|", ge=0)
    verifiable: bool = Field(..., description="Whether camera has valid TTL reference for verification")
    status: Literal["pass", "warn", "fail"] = Field(..., description="Verification status: 'pass' | 'warn' | 'fail'")


class VerificationSummary(BaseModel):
    """Verification summary for frame/TTL counts.

    Persisted as verification_summary.json sidecar for QC reporting.

    Attributes:
        session_id: Session identifier
        cameras: List of per-camera verification results
        generated_at: ISO 8601 timestamp

    Requirements:
        - FR-13: Persist verification summary
        - FR-8: Include in QC report

    Example:
        >>> summary = VerificationSummary(
        ...     session_id="Session-001",
        ...     cameras=[CameraVerificationResult(...)],
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str = Field(..., description="Session identifier")
    cameras: List[CameraVerificationResult] = Field(..., description="List of per-camera verification results")
    generated_at: str = Field(..., description="ISO 8601 timestamp of verification")


class VerificationResult(BaseModel):
    """Result of manifest verification.

    Returned by ingest.verify_manifest() for programmatic handling.

    Attributes:
        status: "pass" | "warn" | "fail"
        camera_results: Per-camera verification details

    Requirements:
        - FR-2, FR-3: Verification logic
    """

    model_config = {"frozen": True, "extra": "forbid"}

    status: Literal["pass", "warn", "fail"] = Field(..., description="Overall verification status: 'pass' | 'warn' | 'fail'")
    camera_results: List[CameraVerificationResult] = Field(default_factory=list, description="Per-camera verification details")
