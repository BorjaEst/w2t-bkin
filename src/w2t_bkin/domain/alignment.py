"""Alignment and provenance domain models (Phase 2).

This module contains Provenance model for configuration tracking.
AlignmentStats has been moved to sync.models (module-local ownership).

Model Hierarchy:
---------------
- Provenance: Config/session hashes for reproducibility
- AlignmentStats: Moved to sync.models (re-exported from domain for compatibility)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Hashable**: Supports deterministic provenance tracking

Requirements:
-------------
- FR-TB-1..6: Timebase alignment strategy
- FR-17: Provenance of timebase choice
- NFR-11: Configuration hashing for reproducibility

Acceptance Criteria:
-------------------
- A17: Jitter budget enforcement
- A18: Deterministic hashing

Usage:
------
>>> # AlignmentStats now in sync.models
>>> from w2t_bkin.sync.models import AlignmentStats
>>> stats = AlignmentStats(
...     timebase_source="ttl",
...     mapping="nearest",
...     offset_s=0.0,
...     max_jitter_s=0.0001,
...     p95_jitter_s=0.00005,
...     aligned_samples=8580
... )
>>>
>>> from w2t_bkin.domain.alignment import Provenance
>>> prov = Provenance(
...     config_hash="abc123...",
...     session_hash="def456..."
... )

See Also:
---------
- w2t_bkin.sync: Timebase alignment implementation
- design.md: Alignment stats schema
"""

from typing import Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Provenance metadata for reproducibility.

    Tracks configuration and session hashes to ensure reproducible outputs.
    Hashes are computed deterministically from config.toml and session.toml
    contents.

    Attributes:
        config_hash: SHA256 hash of config.toml content
        session_hash: SHA256 hash of session.toml content

    Requirements:
        - NFR-11: Provenance tracking via deterministic hashing
        - A18: Deterministic hashing support

    Example:
        >>> from w2t_bkin.config import load_config, load_session
        >>> from w2t_bkin.utils import stable_hash
        >>>
        >>> config = load_config("config.toml")
        >>> session = load_session("session.toml")
        >>>
        >>> prov = Provenance(
        ...     config_hash=stable_hash(config),
        ...     session_hash=stable_hash(session)
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    config_hash: str = Field(..., description="SHA256 hash of config.toml content for reproducibility")
    session_hash: str = Field(..., description="SHA256 hash of session.toml content for reproducibility")
