"""Prefect tasks for synchronization and alignment."""

import logging
from typing import Dict, List, Optional

import numpy as np
from prefect import task

# from w2t_bkin.operations import something from sync
from w2t_bkin.config import SynchronizationConfig
from w2t_bkin.models import DataResults, SyncResults, SyncStatistics

logger = logging.getLogger(__name__)


@task(
    name="Compute Rate-Based Offsets",
    description="Compute synchronization offsets using rate-based method",
    tags=["sync", "rate_based"],
    retries=1,
)
def compute_rate_based_offsets_task(data: DataResult, config: SynchronizationConfig) -> SyncResults:
    pass  # TODO: implement


@task(
    name="Compute Hardware Pulse Offsets",
    description="Compute synchronization offsets using hardware pulse method",
    tags=["sync", "hardware_pulse"],
    retries=1,
)
def compute_hardware_pulse_offsets_task(data: DataResult, config: SynchronizationConfig) -> SyncResults:
    pass  # TODO: implement


@task(
    name="Compute Network Stream Offsets",
    description="Compute synchronization offsets using network stream method",
    tags=["sync", "network_stream"],
    retries=1,
)
def compute_network_stream_offsets_task(data: DataResult, config: SynchronizationConfig) -> SyncResults:
    pass  # TODO: implement


@task(
    name="Compute Alignment Statistics",
    description="Calculate trial-TTL alignment statistics",
    tags=["sync", "statistics"],
    retries=1,
)
def compute_alignment_stats_task(offsets: OffsetsResults, ttl_data) -> SyncStatistics:

    logger.info("Computing alignment statistics")
    pass  # TODO: implement compute_alignment_statistics_from_result
