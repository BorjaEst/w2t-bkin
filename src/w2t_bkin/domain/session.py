"""Session domain models for W2T-BKIN pipeline (Phase 0).

This module defines Pydantic models for session metadata and specifications
loaded from session.toml files. Session models describe the experimental
session, subject information, and file patterns for discovery.

Model Hierarchy:
---------------
- Session (top-level)
  ├── SessionMetadata
  ├── BpodSession
  ├── TTL (list)
  └── Camera (list)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Hashable**: Supports deterministic provenance tracking

Requirements:
-------------
- FR-1: Ingest camera videos, TTLs, and Bpod files
- FR-15: Validate camera-TTL references
- NFR-10: Type safety via Pydantic

Acceptance Criteria:
-------------------
- A18: Supports deterministic hashing

Usage:
------
>>> from w2t_bkin.config import load_session
>>> session = load_session("session.toml")
>>> print(session.session.subject_id)
>>> for cam in session.cameras:
...     print(f"{cam.id} -> {cam.ttl_id}")

See Also:
---------
- w2t_bkin.config: Loading and validation logic
- spec/spec-session-toml.md: Schema specification
"""

from typing import List

from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Session metadata and subject information.

    Attributes:
        id: Unique session identifier
        subject_id: Subject/animal identifier
        date: Session date (ISO 8601 format recommended)
        experimenter: Name of experimenter
        description: Session description
        sex: Subject sex (M/F/U)
        age: Subject age (e.g., "P60", "3mo")
        genotype: Subject genotype (e.g., "WT", "Cre+")

    Requirements:
        - FR-1: Session metadata for NWB
        - NFR-9: Support anonymized subject IDs
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique session identifier")
    subject_id: str = Field(..., description="Subject/animal identifier (supports anonymization)")
    date: str = Field(..., description="Session date (ISO 8601 format recommended)")
    experimenter: str = Field(..., description="Name or ID of experimenter")
    description: str = Field(..., description="Human-readable session description")
    sex: str = Field(..., description="Subject sex: 'M' (male), 'F' (female), or 'U' (unknown)")
    age: str = Field(..., description="Subject age (e.g., 'P60', '3mo', '2y')")
    genotype: str = Field(..., description="Subject genotype (e.g., 'WT', 'Cre+', 'KO')")


class BpodSession(BaseModel):
    """Bpod file configuration for session.

    Attributes:
        path: Glob pattern for Bpod .mat files
        order: File ordering strategy (e.g., "name_asc", "time_asc")

    Requirements:
        - FR-1: Discover Bpod files via patterns
        - FR-11: Parse Bpod trials/events
    """

    model_config = {"frozen": True, "extra": "forbid"}

    path: str = Field(..., description="Glob pattern for Bpod .mat files (e.g., 'Bpod/*.mat')")
    order: str = Field(..., description="File ordering strategy: 'name_asc', 'name_desc', 'time_asc', 'time_desc'")


class TTL(BaseModel):
    """TTL channel configuration.

    Defines a TTL channel that provides synchronization pulses.
    Cameras reference TTL channels via ttl_id for verification.

    Attributes:
        id: Unique TTL channel identifier
        description: Human-readable description
        paths: Glob pattern for TTL files

    Requirements:
        - FR-1: Discover TTL files via patterns
        - FR-2: Verify frame/TTL counts
        - FR-15: Validate camera-TTL references
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique TTL channel identifier (referenced by cameras)")
    description: str = Field(..., description="Human-readable description of TTL channel")
    paths: str = Field(..., description="Glob pattern for TTL pulse files (e.g., 'TTLs/cam_sync*.txt')")


class Camera(BaseModel):
    """Camera configuration.

    Defines a camera source with file patterns and TTL reference.

    Attributes:
        id: Unique camera identifier
        description: Human-readable description
        paths: Glob pattern for video files
        order: File ordering strategy (e.g., "name_asc", "time_asc")
        ttl_id: Reference to TTL channel for verification

    Requirements:
        - FR-1: Discover video files via patterns
        - FR-2: Verify frame counts against TTL
        - FR-15: Validate TTL reference exists
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique camera identifier")
    description: str = Field(..., description="Human-readable description of camera view")
    paths: str = Field(..., description="Glob pattern for video files (e.g., 'Video/cam0_*.avi')")
    order: str = Field(..., description="File ordering strategy: 'name_asc', 'name_desc', 'time_asc', 'time_desc'")
    ttl_id: str = Field(..., description="Reference to TTL channel ID for frame/pulse verification")


class Session(BaseModel):
    """Session configuration model (strict schema).

    Top-level model loaded from session.toml containing all session
    metadata, file patterns, and relationships.

    Requirements:
        - FR-1: Session-driven discovery
        - FR-15: Camera-TTL validation
        - NFR-10: Type safety

    Example:
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("session.toml")
        >>> session.session.subject_id
        'Mouse-123'
        >>> [cam.id for cam in session.cameras]
        ['cam0', 'cam1']
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session: SessionMetadata = Field(..., description="Session metadata and subject information")
    bpod: BpodSession = Field(..., description="Bpod file configuration")
    TTLs: List[TTL] = Field(..., description="List of TTL channel configurations")
    cameras: List[Camera] = Field(..., description="List of camera configurations")
