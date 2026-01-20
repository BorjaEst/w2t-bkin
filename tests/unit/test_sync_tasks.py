"""Unit tests for synchronization tasks (tasks/sync.py).

Tests trial-level synchronization using hardware TTL pulses, rate-based,
and network stream strategies. Validates offset computation, alignment stats,
and edge case handling.
"""

from pathlib import Path
from typing import Dict, List

import pytest

from w2t_bkin.config import SynchronizationConfig
from w2t_bkin.exceptions import SyncError
from w2t_bkin.models import BpodData, TTLData
from w2t_bkin.tasks.sync import (
    compute_alignment_stats_task,
    compute_hardware_pulse_offsets_task,
    compute_network_stream_offsets_task,
    compute_rate_based_offsets_task,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def minimal_bpod_data() -> BpodData:
    """Create minimal BpodData with 3 trials."""
    return BpodData(
        data={
            "SessionData": {
                "nTrials": 3,
                "TrialStartTimestamp": [0.0, 10.0, 20.0],
                "TrialTypes": [1, 1, 2],
                "RawEvents": {
                    "Trial": [
                        {"States": {"W2T_Audio": [1.0, 1.5]}},
                        {"States": {"W2T_Audio": [1.2, 1.7]}},
                        {"States": {"A2L_Audio": [0.8, 1.3]}},
                    ]
                },
            }
        },
        source_files=[Path("/fake/bpod.mat")],
        sync_trial_types=[
            {"trial_type": 1, "sync_signal": "W2T_Audio", "sync_ttl": "ttl_cue"},
            {"trial_type": 2, "sync_signal": "A2L_Audio", "sync_ttl": "ttl_cue"},
        ],
    )


@pytest.fixture
def ttl_data_3_pulses() -> Dict[str, TTLData]:
    """Create TTL data with 3 pulses matching the 3 trials."""
    return {
        "ttl_cue": TTLData(
            channel_id="ttl_cue",
            timestamps=[1.0, 11.2, 20.8],  # Match trial sync signals
            source_files=[Path("/fake/ttl_cue.txt")],
        )
    }


@pytest.fixture
def sync_config_default() -> SynchronizationConfig:
    """Default synchronization config."""
    return SynchronizationConfig(
        strategy="hardware_pulse",
        reference_channel="ttl_cue",
        alignment_method="nearest",
        tolerance=0.01,
        global_offset=0.0,
    )


@pytest.fixture
def sync_config_with_offset() -> SynchronizationConfig:
    """Sync config with non-zero global offset."""
    return SynchronizationConfig(
        strategy="hardware_pulse",
        reference_channel="ttl_cue",
        alignment_method="nearest",
        tolerance=0.01,
        global_offset=5.0,
    )


# ============================================================================
# Tests: compute_hardware_pulse_offsets_task
# ============================================================================


class TestComputeHardwarePulseOffsets:
    """Test hardware TTL pulse synchronization."""

    def test_computes_offsets_for_all_trials(
        self, minimal_bpod_data, ttl_data_3_pulses, sync_config_default
    ):
        """Should compute offsets for all trials when TTL pulses match."""
        data = {"bpod": minimal_bpod_data, "ttl": ttl_data_3_pulses}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_default)

        # Verify all 3 trials aligned
        assert len(offsets) == 3
        assert 1 in offsets
        assert 2 in offsets
        assert 3 in offsets

        # Trial 1: ttl_time=1.0, trial_start=0.0, sync_rel=1.0 → offset=0.0
        assert offsets[1] == pytest.approx(0.0, abs=1e-6)

        # Trial 2: ttl_time=11.2, trial_start=10.0, sync_rel=1.2 → offset=0.0
        assert offsets[2] == pytest.approx(0.0, abs=1e-6)

        # Trial 3: ttl_time=20.8, trial_start=20.0, sync_rel=0.8 → offset=0.0
        assert offsets[3] == pytest.approx(0.0, abs=1e-6)

    def test_applies_global_offset(
        self, minimal_bpod_data, ttl_data_3_pulses, sync_config_with_offset
    ):
        """Should apply global offset to all computed offsets."""
        data = {"bpod": minimal_bpod_data, "ttl": ttl_data_3_pulses}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_with_offset)

        # All offsets should be increased by global_offset=5.0
        assert offsets[1] == pytest.approx(5.0, abs=1e-6)
        assert offsets[2] == pytest.approx(5.0, abs=1e-6)
        assert offsets[3] == pytest.approx(5.0, abs=1e-6)

    def test_handles_missing_bpod_data(self, ttl_data_3_pulses, sync_config_default):
        """Should return empty offsets when Bpod data missing."""
        data = {"ttl": ttl_data_3_pulses}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_default)

        assert offsets == {}

    def test_handles_missing_ttl_data(self, minimal_bpod_data, sync_config_default):
        """Should return empty offsets when TTL data missing."""
        data = {"bpod": minimal_bpod_data}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_default)

        assert offsets == {}

    def test_raises_when_sync_config_missing(self, ttl_data_3_pulses, sync_config_default):
        """Should raise SyncError when sync_trial_types not configured."""
        bpod_no_sync = BpodData(
            data={"SessionData": {"nTrials": 1}},
            source_files=[Path("/fake/bpod.mat")],
            sync_trial_types=[],  # Empty config
        )
        data = {"bpod": bpod_no_sync, "ttl": ttl_data_3_pulses}

        with pytest.raises(SyncError, match="Bpod sync configuration missing"):
            compute_hardware_pulse_offsets_task(data, sync_config_default)

    def test_handles_partial_alignment_when_ttl_pulses_insufficient(
        self, minimal_bpod_data, sync_config_default
    ):
        """Should align available trials and skip those without TTL pulses."""
        # Only 2 TTL pulses for 3 trials
        ttl_data_partial = {
            "ttl_cue": TTLData(
                channel_id="ttl_cue",
                timestamps=[1.0, 11.2],  # Only 2 pulses
                source_files=[Path("/fake/ttl_cue.txt")],
            )
        }
        data = {"bpod": minimal_bpod_data, "ttl": ttl_data_partial}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_default)

        # Only first 2 trials should be aligned
        assert len(offsets) == 2
        assert 1 in offsets
        assert 2 in offsets
        assert 3 not in offsets

    def test_handles_extra_ttl_pulses(self, minimal_bpod_data, sync_config_default):
        """Should use only needed TTL pulses and ignore surplus."""
        # 5 TTL pulses for 3 trials
        ttl_data_extra = {
            "ttl_cue": TTLData(
                channel_id="ttl_cue",
                timestamps=[1.0, 11.2, 20.8, 30.0, 40.0],  # 2 extra
                source_files=[Path("/fake/ttl_cue.txt")],
            )
        }
        data = {"bpod": minimal_bpod_data, "ttl": ttl_data_extra}

        offsets = compute_hardware_pulse_offsets_task(data, sync_config_default)

        # All 3 trials should still align
        assert len(offsets) == 3
        assert all(trial_num in offsets for trial_num in [1, 2, 3])


# ============================================================================
# Tests: compute_rate_based_offsets_task
# ============================================================================


class TestComputeRateBasedOffsets:
    """Test rate-based synchronization (no-op for trial offsets)."""

    def test_returns_empty_offsets(self, minimal_bpod_data, sync_config_default):
        """Should return empty offsets for rate-based sync."""
        data = {"bpod": minimal_bpod_data}
        config = SynchronizationConfig(strategy="rate_based")

        offsets = compute_rate_based_offsets_task(data, config)

        assert offsets == {}


# ============================================================================
# Tests: compute_network_stream_offsets_task
# ============================================================================


class TestComputeNetworkStreamOffsets:
    """Test network stream synchronization (not implemented)."""

    def test_returns_empty_offsets(self, minimal_bpod_data, sync_config_default):
        """Should return empty offsets for network stream sync."""
        data = {"bpod": minimal_bpod_data}
        config = SynchronizationConfig(strategy="network_stream")

        offsets = compute_network_stream_offsets_task(data, config)

        assert offsets == {}


# ============================================================================
# Tests: compute_alignment_stats_task
# ============================================================================


class TestComputeAlignmentStats:
    """Test alignment statistics computation."""

    def test_computes_stats_for_valid_offsets(self, ttl_data_3_pulses):
        """Should compute correct statistics from trial offsets."""
        trial_offsets = {1: 0.0, 2: 0.1, 3: 0.2}

        stats = compute_alignment_stats_task(trial_offsets, ttl_data_3_pulses)

        assert stats["n_trials_aligned"] == 3
        assert stats["offset_mean_s"] == pytest.approx(0.1, abs=1e-6)
        assert stats["offset_std_s"] == pytest.approx(0.0816, abs=1e-3)
        assert stats["offset_min_s"] == 0.0
        assert stats["offset_max_s"] == 0.2
        assert "ttl_cue" in stats["ttl_channels"]
        assert stats["ttl_pulse_counts"]["ttl_cue"] == 3

    def test_handles_empty_offsets(self, ttl_data_3_pulses):
        """Should return zero stats when no offsets provided."""
        trial_offsets = {}

        stats = compute_alignment_stats_task(trial_offsets, ttl_data_3_pulses)

        assert stats["n_trials_aligned"] == 0
        assert stats["offset_mean_s"] == 0.0
        assert stats["offset_std_s"] == 0.0

    def test_includes_ttl_channel_info(self):
        """Should include TTL channel metadata in stats."""
        trial_offsets = {1: 1.0}
        ttl_data = {
            "ttl_camera": TTLData(
                channel_id="ttl_camera",
                timestamps=[0.0, 0.033, 0.066],
                source_files=[Path("/fake/ttl_camera.txt")],
            ),
            "ttl_cue": TTLData(
                channel_id="ttl_cue",
                timestamps=[1.0, 2.0],
                source_files=[Path("/fake/ttl_cue.txt")],
            ),
        }

        stats = compute_alignment_stats_task(trial_offsets, ttl_data)

        assert len(stats["ttl_channels"]) == 2
        assert "ttl_camera" in stats["ttl_channels"]
        assert "ttl_cue" in stats["ttl_channels"]
        assert stats["ttl_pulse_counts"]["ttl_camera"] == 3
        assert stats["ttl_pulse_counts"]["ttl_cue"] == 2
