"""Prefect tasks for synchronization and alignment.

Provides Prefect task wrappers for computing trial-level synchronization offsets
and alignment statistics. Delegates to low-level sync primitives in w2t_bkin.sync.

Key Concepts:
    - Trial offsets: Dict[trial_number, absolute_time_offset] used to convert
      Bpod relative timestamps to absolute time aligned with TTL pulses.
    - Alignment stats: Quality metrics for sync (n_trials aligned, offset stats, etc.)

Architecture:
    Pure sync functions (sync.ttl, sync.core) → Prefect task wrappers (here)
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from prefect import get_run_logger, task

from w2t_bkin.config import SynchronizationConfig
from w2t_bkin.exceptions import SyncError
from w2t_bkin.models import BpodData, TTLData
from w2t_bkin.sync.ttl import align_bpod_trials_to_ttl
from w2t_bkin.sync.ttl_robust import align_bpod_trials_to_ttl_robust

logger = logging.getLogger(__name__)

# Type alias for clarity
TrialOffsets = Dict[int, float]  # trial_number → absolute time offset
RobustOffsetsResult = Dict[str, Any]


@task(
    name="Compute Rate-Based Offsets",
    description="Compute synchronization offsets using rate-based method (no-op for trial offsets)",
    tags=["sync", "rate_based"],
    retries=1,
)
def compute_rate_based_offsets_task(data: Dict[str, Any], config: SynchronizationConfig) -> TrialOffsets:
    """Compute trial offsets using rate-based synchronization (no-op).

    Rate-based sync does not provide absolute time alignment for Bpod trials.
    Returns empty offsets, which ingest/behavior treats as relative time (offset=0.0).

    Args:
        data: Ingestion results (unused for rate-based)
        config: Synchronization configuration (unused)

    Returns:
        Empty dict (no absolute alignment)
    """
    run_logger = get_run_logger()
    run_logger.warning("Rate-based synchronization does not provide trial-level offsets. " "Bpod timestamps will remain relative to trial start.")
    return {}


@task(
    name="Compute Hardware Pulse Offsets",
    description="Compute synchronization offsets using hardware TTL pulse method",
    tags=["sync", "hardware_pulse"],
    retries=1,
)
def compute_hardware_pulse_offsets_task(data: Dict[str, Any], config: SynchronizationConfig) -> TrialOffsets:
    """Compute trial offsets by aligning Bpod trials to TTL sync pulses.

    Algorithm:
        1. For each trial, extract sync signal start time (from Bpod States)
        2. Match to next available TTL pulse from corresponding channel
        3. Compute offset: ttl_time - (trial_start + sync_signal_time)
        4. Apply global offset from config

    Args:
        data: Ingestion results containing:
            - data["bpod"]: BpodData with trials and sync_trial_types config
            - data["ttl"]: Dict[ttl_id, TTLData] with pulse timestamps
        config: Synchronization configuration (uses global_offset)

    Returns:
        Dict mapping trial_number → absolute time offset in seconds

    Raises:
        SyncError: If required data missing or sync config invalid
    """
    run_logger = get_run_logger()
    run_logger.info("Computing trial offsets using hardware TTL pulse alignment")

    # Validate inputs
    bpod_data: Optional[BpodData] = data.get("bpod")
    ttl_data: Optional[Dict[str, TTLData]] = data.get("ttl")

    if not bpod_data:
        run_logger.warning("No Bpod data available for synchronization")
        return {}

    if not ttl_data:
        run_logger.warning("No TTL data available for synchronization")
        return {}

    if not bpod_data.sync_trial_types:
        raise SyncError("Bpod sync configuration missing. Add [[bpod.sync.trial_types]] " "to metadata.toml with trial_type, sync_signal, and sync_ttl fields.")

    # Convert TTLData to primitive dict for alignment function
    ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}

    run_logger.debug(f"Aligning {bpod_data.n_trials} trials with {len(ttl_pulses)} TTL channel(s): " f"{', '.join(ttl_pulses.keys())}")

    # Compute trial offsets using low-level alignment
    trial_offsets, warnings = align_bpod_trials_to_ttl(
        trial_type_configs=bpod_data.sync_trial_types,
        bpod_data=bpod_data.data,
        ttl_pulses=ttl_pulses,
    )

    # Apply global offset from config (if configured)
    global_offset = config.global_offset
    if global_offset != 0.0:
        run_logger.debug(f"Applying global offset: {global_offset:.4f}s")
        trial_offsets = {trial_num: offset + global_offset for trial_num, offset in trial_offsets.items()}

    # Log alignment summary
    if trial_offsets:
        offsets_array = np.array(list(trial_offsets.values()))
        run_logger.info(f"Aligned {len(trial_offsets)}/{bpod_data.n_trials} trials. " f"Offset range: [{offsets_array.min():.4f}, {offsets_array.max():.4f}] s")
    else:
        run_logger.warning("No trials could be aligned to TTL pulses")

    # Log warnings (already logged by align_bpod_trials_to_ttl, but summarize here)
    if warnings:
        run_logger.warning(f"Synchronization produced {len(warnings)} warning(s) (see logs for details)")

    return trial_offsets


@task(
    name="Compute Hardware Pulse Offsets (Robust)",
    description="Compute robust synchronization offsets using hardware TTL pulses",
    tags=["sync", "hardware_pulse", "robust"],
    retries=1,
)
def compute_hardware_pulse_robust_offsets_task(
    data: Dict[str, Any],
    config: SynchronizationConfig,
) -> RobustOffsetsResult:
    """Compute trial offsets using robust TTL alignment with drift handling.

    Args:
        data: Ingestion results containing Bpod and TTL data.
        config: Synchronization configuration (tolerance, global offset).

    Returns:
        Dict with keys:
            - offsets: Dict mapping trial_number → absolute time offset
            - stats: Dict of alignment statistics and labels
            - warnings: List of warning strings
    """
    run_logger = get_run_logger()
    run_logger.info("Computing trial offsets using robust TTL alignment")

    bpod_data: Optional[BpodData] = data.get("bpod")
    ttl_data: Optional[Dict[str, TTLData]] = data.get("ttl")

    if not bpod_data:
        run_logger.warning("No Bpod data available for robust synchronization")
        return {"offsets": {}, "stats": {}, "warnings": []}

    if not ttl_data:
        run_logger.warning("No TTL data available for robust synchronization")
        return {"offsets": {}, "stats": {}, "warnings": []}

    if not bpod_data.sync_trial_types:
        raise SyncError("Bpod sync configuration missing. Add [[bpod.sync.trial_types]] " "to metadata.toml with trial_type, sync_signal, and sync_ttl fields.")

    ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}

    run_logger.debug(
        "Robust alignment for %s trials across %s TTL channel(s)",
        bpod_data.n_trials,
        len(ttl_pulses),
    )

    offsets, warnings, stats = align_bpod_trials_to_ttl_robust(
        trial_type_configs=bpod_data.sync_trial_types,
        bpod_data=bpod_data.data,
        ttl_pulses=ttl_pulses,
        tolerance_s=config.tolerance,
        min_matches=config.robust_min_matches,
        max_start_trial_search=config.robust_max_start_trial_search,
    )

    global_offset = config.global_offset
    if global_offset != 0.0:
        offsets = {trial_num: offset + global_offset for trial_num, offset in offsets.items()}
        stats["global_offset_s"] = global_offset

    if warnings:
        run_logger.warning(
            "Robust synchronization produced %s warning(s); see logs",
            len(warnings),
        )

    run_logger.info(
        "Robust alignment produced offsets for %s/%s trials",
        len(offsets),
        bpod_data.n_trials,
    )

    return {"offsets": offsets, "stats": stats, "warnings": warnings}


@task(
    name="Compute Network Stream Offsets",
    description="Compute synchronization offsets using network stream method (not implemented)",
    tags=["sync", "network_stream"],
    retries=1,
)
def compute_network_stream_offsets_task(data: Dict[str, Any], config: SynchronizationConfig) -> TrialOffsets:
    """Compute trial offsets using network stream synchronization (not implemented).

    Args:
        data: Ingestion results (unused)
        config: Synchronization configuration (unused)

    Returns:
        Empty dict (no implementation)
    """
    run_logger = get_run_logger()
    run_logger.warning("Network stream synchronization not yet implemented. " "Bpod timestamps will remain relative to trial start.")
    return {}
