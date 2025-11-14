"""Alignment statistics creation and persistence.

Provides utilities for creating, writing, and loading alignment statistics
that track timebase quality metrics (jitter, drift, samples aligned, etc.).

Example:
    >>> from w2t_bkin.sync import create_alignment_stats, write_alignment_stats
    >>>
    >>> stats = create_alignment_stats(
    ...     timebase_source="ttl",
    ...     mapping="nearest",
    ...     offset_s=0.0,
    ...     max_jitter_s=0.008,
    ...     p95_jitter_s=0.005,
    ...     aligned_samples=1000
    ... )
    >>>
    >>> write_alignment_stats(stats, Path("data/processed/alignment_stats.json"))
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Union

from ..domain import AlignmentStats
from ..utils import write_json
from .exceptions import SyncError

__all__ = [
    "create_alignment_stats",
    "write_alignment_stats",
    "load_alignment_manifest",
    "compute_alignment",
]

logger = logging.getLogger(__name__)


def create_alignment_stats(
    timebase_source: str,
    mapping: str,
    offset_s: float,
    max_jitter_s: float,
    p95_jitter_s: float,
    aligned_samples: int,
) -> AlignmentStats:
    """Create alignment stats instance.

    Constructs an AlignmentStats domain object with timebase and jitter metrics.
    This is typically called after performing alignment and computing jitter statistics.

    Args:
        timebase_source: Source of timebase (nominal_rate, ttl, neuropixels)
        mapping: Mapping strategy used (nearest, linear)
        offset_s: Time offset applied to timebase
        max_jitter_s: Maximum jitter observed across all samples
        p95_jitter_s: 95th percentile jitter
        aligned_samples: Number of samples successfully aligned

    Returns:
        AlignmentStats instance ready for persistence

    Example:
        >>> stats = create_alignment_stats(
        ...     timebase_source="ttl",
        ...     mapping="linear",
        ...     offset_s=0.5,
        ...     max_jitter_s=0.0082,
        ...     p95_jitter_s=0.0051,
        ...     aligned_samples=5000
        ... )
        >>> print(f"Aligned {stats.aligned_samples} samples")
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
    """Write alignment stats to JSON sidecar file.

    Serializes AlignmentStats to JSON with generation timestamp for QC reporting.
    Output file can be loaded by analysis tools or included in NWB metadata.

    Args:
        stats: AlignmentStats instance to persist
        output_path: Output file path (typically .json extension)

    Example:
        >>> from pathlib import Path
        >>> stats = create_alignment_stats(...)
        >>> output_path = Path("data/processed/session_001/alignment_cam0.json")
        >>> write_alignment_stats(stats, output_path)
    """
    data = stats.model_dump()
    data["generated_at"] = datetime.utcnow().isoformat()
    write_json(data, output_path)
    logger.info(f"Wrote alignment stats to {output_path}")


def load_alignment_manifest(alignment_path: Union[str, Path]) -> dict:
    """Load alignment manifest from JSON file (Phase 2 stub).

    Loads pre-computed alignment data from a manifest JSON file. This is
    typically used in Phase 3+ when alignment has been computed separately
    and saved to disk.

    Args:
        alignment_path: Path to alignment.json (str or Path)

    Returns:
        Dictionary with alignment data per camera:
        {
            "cam0": {
                "timestamps": List[float],
                "source": str,
                "mapping": str,
                "frame_count": int
            },
            ...
        }

    Raises:
        SyncError: If file not found or invalid JSON

    Note:
        Currently returns mock data if file doesn't exist (for Phase 3 integration).

    Example:
        >>> alignment = load_alignment_manifest("data/processed/alignment.json")
        >>> cam0_timestamps = alignment["cam0"]["timestamps"]
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
    """Compute timebase alignment for all cameras (Phase 2 stub).

    Future: Will compute comprehensive alignment for all cameras in a session
    based on manifest and config. Currently returns mock alignment data.

    Args:
        manifest: Manifest dictionary from Phase 1 ingest
        config: Configuration dictionary with timebase settings

    Returns:
        Alignment dictionary with timestamps per camera:
        {
            "cam0": {
                "timestamps": List[float],
                "source": str,
                "mapping": str,
                "frame_count": int
            },
            ...
        }

    Raises:
        SyncError: If alignment computation fails

    Example:
        >>> from w2t_bkin.ingest import create_manifest
        >>> manifest = create_manifest(session)
        >>> config = {"timebase": {...}}
        >>> alignment = compute_alignment(manifest, config)
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
