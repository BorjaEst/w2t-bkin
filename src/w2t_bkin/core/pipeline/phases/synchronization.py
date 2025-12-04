"""Phase 4: Synchronization."""

import logging
from typing import Optional

import numpy as np
from rich.progress import Progress, TaskID

from ..models import PipelineContext

logger = logging.getLogger(__name__)


def run_phase_4(context: PipelineContext, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> None:
    """Synchronization and jitter checking."""
    logger.info("Computing alignment statistics...")

    context.alignment_stats = {
        "trial_offsets": context.trial_offsets if context.trial_offsets else {},
        "ttl_channels": {k: len(v) for k, v in context.ttl_pulses.items()},
    }

    if context.trial_offsets:
        offsets_array = np.array(list(context.trial_offsets.values()))
        stats = {
            "n_trials_aligned": len(context.trial_offsets),
            "mean_offset_s": float(np.mean(offsets_array)),
            "std_offset_s": float(np.std(offsets_array)),
            "min_offset_s": float(np.min(offsets_array)),
            "max_offset_s": float(np.max(offsets_array)),
        }
        context.alignment_stats["statistics"] = stats

        logger.info(f"  Trials: {stats['n_trials_aligned']}")
        logger.info(f"  Mean offset: {stats['mean_offset_s']:.4f} s")
        logger.info(f"  Std offset: {stats['std_offset_s']:.4f} s")
        logger.debug(f"  Offset range: [{stats['min_offset_s']:.4f}, {stats['max_offset_s']:.4f}] s")
    else:
        logger.warning("  No trial offsets computed - synchronization statistics are empty")
