"""Alignment statistics models.

Defines AlignmentStats for representing alignment quality metrics.
"""

from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["AlignmentStats"]


class AlignmentStats(BaseModel):
    """Alignment quality metrics.

    Attributes:
        timebase_source: "nominal_rate", "ttl", or "neuropixels"
        mapping: "nearest" or "linear"
        offset_s: Time offset in seconds
        max_jitter_s: Maximum jitter in seconds
        p95_jitter_s: 95th percentile jitter in seconds
        aligned_samples: Number of aligned samples
    """

    model_config = {"frozen": True, "extra": "forbid"}

    timebase_source: Literal["nominal_rate", "ttl", "neuropixels"] = Field(..., description="Source of reference timebase: 'nominal_rate' | 'ttl' | 'neuropixels'")
    mapping: Literal["nearest", "linear"] = Field(..., description="Alignment mapping strategy: 'nearest' | 'linear'")
    offset_s: float = Field(..., description="Time offset applied to timebase in seconds")
    max_jitter_s: float = Field(..., description="Maximum jitter observed in seconds", ge=0)
    p95_jitter_s: float = Field(..., description="95th percentile jitter in seconds", ge=0)
    aligned_samples: int = Field(..., description="Number of samples successfully aligned", ge=0)
