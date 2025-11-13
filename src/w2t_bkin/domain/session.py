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

from pydantic import BaseModel


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

    id: str
    subject_id: str
    date: str
    experimenter: str
    description: str
    sex: str
    age: str
    genotype: str


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

    path: str
    order: str


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

    id: str
    description: str
    paths: str


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

    id: str
    description: str
    paths: str
    order: str
    ttl_id: str


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

    session: SessionMetadata
    bpod: BpodSession
    TTLs: List[TTL]
    cameras: List[Camera]
