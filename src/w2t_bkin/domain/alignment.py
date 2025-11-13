"""Alignment and provenance domain models (Phase 2).

This module defines models for timebase alignment statistics and
provenance tracking. These models capture alignment quality metrics
and configuration hashes for reproducibility.

Model Hierarchy:
---------------
- AlignmentStats: Jitter metrics and alignment summary
- Provenance: Config/session hashes for reproducibility

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
>>> from w2t_bkin.domain.alignment import AlignmentStats
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


class AlignmentStats(BaseModel):
    """Alignment statistics for timebase synchronization (Phase 2).

    Captures metrics about the quality of alignment between the reference
    timebase and derived data streams (pose, facemap, etc). Jitter metrics
    are compared against the configured jitter_budget_s threshold.

    Attributes:
        timebase_source: Source of reference timebase ("nominal_rate"|"ttl"|"neuropixels")
        mapping: Alignment mapping strategy ("nearest"|"linear")
        offset_s: Time offset applied to timebase (seconds)
        max_jitter_s: Maximum jitter observed (seconds)
        p95_jitter_s: 95th percentile jitter (seconds)
        aligned_samples: Number of samples successfully aligned

    Requirements:
        - FR-TB-1..6: Timebase alignment strategy
        - FR-17: Provenance of timebase choice
        - A17: Jitter budget enforcement before NWB

    Example:
        >>> stats = AlignmentStats(
        ...     timebase_source="ttl",
        ...     mapping="nearest",
        ...     offset_s=0.0,
        ...     max_jitter_s=0.0001,
        ...     p95_jitter_s=0.00005,
        ...     aligned_samples=8580
        ... )
        >>> # Check against budget
        >>> if stats.max_jitter_s > budget:
        ...     raise JitterExceedsBudgetError(...)
    """

    model_config = {"frozen": True, "extra": "forbid"}

    timebase_source: Literal["nominal_rate", "ttl", "neuropixels"] = Field(..., description="Source of reference timebase: 'nominal_rate' | 'ttl' | 'neuropixels'")
    mapping: Literal["nearest", "linear"] = Field(..., description="Alignment mapping strategy: 'nearest' | 'linear'")
    offset_s: float = Field(..., description="Time offset applied to timebase in seconds")
    max_jitter_s: float = Field(..., description="Maximum jitter observed in seconds", ge=0)
    p95_jitter_s: float = Field(..., description="95th percentile jitter in seconds", ge=0)
    aligned_samples: int = Field(..., description="Number of samples successfully aligned", ge=0)


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
