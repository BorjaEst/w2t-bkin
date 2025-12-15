"""Prefect tasks for synchronization and alignment."""

import logging
from typing import Dict, List, Optional

from prefect import task

from w2t_bkin.models import TrialAlignment
from w2t_bkin.operations import compute_alignment_statistics, compute_alignment_statistics_from_result

logger = logging.getLogger(__name__)


@task(
    name="Compute Alignment Statistics",
    description="Calculate trial-TTL alignment statistics",
    tags=["sync", "statistics"],
    retries=1,
)
def compute_alignment_stats_task(trial_offsets: List[float], ttl_channels: Dict[str, int]) -> Dict[str, any]:
    """Compute statistics about trial-TTL alignment.

    Prefect task wrapper for compute_alignment_statistics operation.

    Args:
        trial_offsets: List of trial offset times in seconds
        ttl_channels: Dictionary mapping TTL channel ID to pulse count

    Returns:
        Dictionary containing alignment statistics
    """
    logger.info("Computing alignment statistics")

    return compute_alignment_statistics(trial_offsets=trial_offsets, ttl_channels=ttl_channels)


@task(
    name="Compute Alignment Stats from Result",
    description="Calculate alignment statistics from TrialAlignment",
    tags=["sync", "statistics"],
    retries=1,
)
def compute_alignment_stats_from_result_task(trial_alignment: Optional[TrialAlignment], ttl_pulse_counts: Dict[str, int]) -> Dict[str, any]:
    """Compute alignment statistics from TrialAlignment result.

    Prefect task wrapper for compute_alignment_statistics_from_result operation.
    Convenience task that extracts offsets from TrialAlignment.

    Args:
        trial_alignment: Trial alignment result or None
        ttl_pulse_counts: TTL channel pulse counts

    Returns:
        Dictionary containing alignment statistics
    """
    logger.info("Computing alignment statistics from TrialAlignment")

    return compute_alignment_statistics_from_result(trial_alignment=trial_alignment, ttl_pulse_counts=ttl_pulse_counts)
