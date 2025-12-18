"""Pure functions for computing synchronization statistics."""

import logging
from typing import Dict, List, Optional

import numpy as np

from w2t_bkin.models import TrialAlignment

logger = logging.getLogger(__name__)


def compute_alignment_statistics(trial_offsets: List[float], ttl_channels: Dict[str, int]) -> Dict[str, any]:
    """Compute statistics about trial-TTL alignment.

    Pure function that calculates mean, std, min, max of trial offsets.

    Args:
        trial_offsets: List of trial offset times in seconds
        ttl_channels: Dictionary mapping TTL channel ID to pulse count

    Returns:
        Dictionary containing alignment statistics with structure:
        {
            "trial_offsets": {trial_num: offset_seconds, ...},
            "ttl_channels": {channel_name: pulse_count, ...},
            "statistics": {...}
        }
    """
    logger.info("Computing alignment statistics")

    # Convert list to dict for plotting compatibility
    trial_offsets_dict = {i + 1: offset for i, offset in enumerate(trial_offsets)}

    stats = {"ttl_channels": ttl_channels, "trial_offsets": trial_offsets_dict}

    if trial_offsets:
        offsets_array = np.array(trial_offsets)

        stats["statistics"] = {
            "n_trials_aligned": len(trial_offsets),
            "mean_offset_s": float(np.mean(offsets_array)),
            "std_offset_s": float(np.std(offsets_array)),
            "min_offset_s": float(np.min(offsets_array)),
            "max_offset_s": float(np.max(offsets_array)),
        }

        logger.info(f"Trials: {stats['statistics']['n_trials_aligned']}")
        logger.info(f"Mean offset: {stats['statistics']['mean_offset_s']:.4f} s")
        logger.info(f"Std offset: {stats['statistics']['std_offset_s']:.4f} s")
        logger.debug(f"Offset range: [{stats['statistics']['min_offset_s']:.4f}, " f"{stats['statistics']['max_offset_s']:.4f}] s")
    else:
        logger.warning("No trial offsets - synchronization statistics are empty")

    return stats


def compute_alignment_statistics_from_result(trial_alignment: Optional[TrialAlignment], ttl_pulse_counts: Dict[str, int]) -> Dict[str, any]:
    """Compute alignment statistics from TrialAlignment result.

    Convenience function that extracts offsets from TrialAlignment.

    Args:
        trial_alignment: Trial alignment result or None
        ttl_pulse_counts: TTL channel pulse counts

    Returns:
        Dictionary containing alignment statistics
    """
    trial_offsets = trial_alignment.trial_offsets if trial_alignment else []

    return compute_alignment_statistics(trial_offsets=trial_offsets, ttl_channels=ttl_pulse_counts)
