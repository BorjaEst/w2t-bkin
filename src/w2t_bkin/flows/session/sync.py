"""Synchronization phase helpers."""

from typing import Dict, Optional

from w2t_bkin.models import BpodData, SessionInfo, TrialAlignment, TTLData


def align_trials_with_ttl(bpod_data: Optional[BpodData], ttl_data: Dict[str, TTLData], session_info: SessionInfo, run_logger) -> Optional[TrialAlignment]:
    """Align behavioral trials with TTL pulses.

    Args:
        bpod_data: Bpod behavioral data
        ttl_data: TTL pulse data
        session_info: Session configuration
        run_logger: Prefect logger

    Returns:
        Trial alignment result or None
    """
    if not (bpod_data and ttl_data):
        return None

    # Extract trial_type configs from metadata
    bpod_meta = session_info.metadata.get("bpod", {})
    sync_meta = bpod_meta.get("sync", {}) if isinstance(bpod_meta, dict) else {}
    trial_type_configs = sync_meta.get("trial_types", []) if isinstance(sync_meta, dict) else []

    if not trial_type_configs:
        run_logger.info("Skipping trial alignment (no trial_type configs in metadata)")
        return None

    # Extract TTL pulse timestamps
    ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}

    trial_alignment = tasks.align_trials_task(trial_type_configs, bpod_data.data, ttl_pulses)

    if trial_alignment.warnings:
        for warning in trial_alignment.warnings:
            run_logger.warning(f"Trial alignment: {warning}")

    return trial_alignment


def compute_sync_stats(trial_alignment: Optional[TrialAlignment], ttl_data: Dict[str, TTLData], run_logger) -> Optional[Dict]:
    """Compute synchronization statistics.

    Args:
        trial_alignment: Trial alignment results
        ttl_data: TTL pulse data
        run_logger: Prefect logger

    Returns:
        Alignment statistics or None
    """
    if not (trial_alignment and ttl_data):
        return None

    ttl_channels = {ttl_id: len(ttl.timestamps) for ttl_id, ttl in ttl_data.items()}

    # Convert trial_offsets dict to list of values
    trial_offsets_list = list(trial_alignment.trial_offsets.values()) if isinstance(trial_alignment.trial_offsets, dict) else trial_alignment.trial_offsets
    alignment_stats = tasks.compute_alignment_stats_task(trial_offsets_list, ttl_channels)

    run_logger.info("Computed alignment statistics")
    return alignment_stats
