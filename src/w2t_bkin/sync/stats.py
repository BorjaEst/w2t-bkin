"""Create and persist alignment statistics.

This module handles the representation, creation, and persistence of
synchronization quality metrics.

Example:
    >>> stats = create_alignment_stats(
    ...     timebase_source="ttl",
    ...     mapping="nearest",
    ...     offset_s=0.0,
    ...     max_jitter_s=0.008,
    ...     p95_jitter_s=0.005,
    ...     aligned_samples=1000
    ... )
    >>> write_alignment_stats(stats, Path("alignment.json"))
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, Field

from w2t_bkin.exceptions import SyncError
from w2t_bkin.utils import write_json

logger = logging.getLogger(__name__)


class AlignmentStats(BaseModel):
    """Alignment quality metrics.

    Attributes:
        timebase_source: Strategy name (rate_based, ttl_based, hardware_pulse, or legacy values)
        mapping: "nearest" or "linear"
        offset_s: Time offset in seconds
        max_jitter_s: Maximum jitter in seconds
        p95_jitter_s: 95th percentile jitter in seconds
        aligned_samples: Number of aligned samples
    """

    model_config = {"frozen": True, "extra": "forbid"}

    timebase_source: str = Field(..., description="Source of reference timebase (strategy name or legacy: nominal_rate/ttl/neuropixels)")
    mapping: Literal["nearest", "linear"] = Field(..., description="Alignment mapping strategy: 'nearest' | 'linear'")
    offset_s: float = Field(..., description="Time offset applied to timebase in seconds")
    max_jitter_s: float = Field(..., description="Maximum jitter observed in seconds", ge=0)
    p95_jitter_s: float = Field(..., description="95th percentile jitter in seconds", ge=0)
    aligned_samples: int = Field(..., description="Number of samples successfully aligned", ge=0)


def create_alignment_stats(
    timebase_source: str,
    mapping: str,
    offset_s: float,
    max_jitter_s: float,
    p95_jitter_s: float,
    aligned_samples: int,
) -> AlignmentStats:
    """Create alignment statistics object.

    Args:
        timebase_source: "nominal_rate", "ttl", or "neuropixels"
        mapping: "nearest" or "linear"
        offset_s: Time offset in seconds
        max_jitter_s: Maximum jitter
        p95_jitter_s: 95th percentile jitter
        aligned_samples: Number of aligned samples

    Returns:
        AlignmentStats instance
    """
    return AlignmentStats(
        timebase_source=timebase_source,
        mapping=mapping,
        offset_s=offset_s,
        max_jitter_s=max_jitter_s,
        p95_jitter_s=p95_jitter_s,
        aligned_samples=aligned_samples,
    )


def write_alignment_stats(stats: AlignmentStats, output_path: Path) -> None:
    """Write alignment stats to JSON file.

    Args:
        stats: AlignmentStats instance
        output_path: Output JSON path
    """
    data = stats.model_dump()
    data["generated_at"] = datetime.utcnow().isoformat()
    write_json(data, output_path)
    logger.info(f"Wrote alignment stats to {output_path}")


def load_alignment_manifest(alignment_path: Union[str, Path]) -> dict:
    """Load alignment manifest from JSON (stub).

    Args:
        alignment_path: Path to alignment.json

    Returns:
        Dict with alignment data per camera

    Raises:
        SyncError: File not found or invalid JSON

    Note:
        Returns mock data if file doesn't exist.
    """
    alignment_path = Path(alignment_path) if isinstance(alignment_path, str) else alignment_path

    if not alignment_path.exists():
        # For Phase 3 integration tests, return mock data if file doesn't exist
        logger.warning(f"Alignment manifest not found: {alignment_path}, returning mock data")
        return {
            "cam0": {
                "timestamps": [i / 30.0 for i in range(100)],  # 100 frames at 30fps
                "source": "nominal_rate",
                "mapping": "nearest",
            }
        }

    try:
        with open(alignment_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise SyncError(f"Failed to load alignment manifest from {alignment_path}: {e}")


def compute_alignment(manifest: dict, config: dict) -> dict:
    """Compute timebase alignment for all cameras (stub).

    Args:
        manifest: Manifest from ingest
        config: Timebase configuration

    Returns:
        Dict with timestamps per camera

    Raises:
        SyncError: Alignment failed

    Note:
        Currently returns mock data.
    """
    # Stub implementation - returns mock alignment data
    alignment = {}

    for camera in manifest.get("cameras", []):
        camera_id = camera.get("camera_id", "cam0")
        frame_count = camera.get("frame_count", 1000)

        # Generate mock timestamps at 30 fps
        timestamps = [i / 30.0 for i in range(frame_count)]

        alignment[camera_id] = {
            "timestamps": timestamps,
            "source": "nominal_rate",
            "mapping": "nearest",
            "frame_count": frame_count,
        }

    logger.info(f"Computed alignment for {len(alignment)} cameras (stub)")
    return alignment
