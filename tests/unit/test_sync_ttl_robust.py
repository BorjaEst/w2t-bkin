"""Unit tests for robust Bpod↔TTL alignment with missing pulses and drift."""

from typing import Dict, List, Optional

import pytest

from w2t_bkin.sync.ttl_robust import align_bpod_trials_to_ttl_robust


def _build_bpod_data(sync_rel_times: List[Optional[float]]) -> Dict:
    """Build minimal Bpod SessionData for sync testing.

    Args:
        sync_rel_times: Relative sync times per trial (None to omit).

    Returns:
        Minimal Bpod data dictionary.
    """
    n_trials = len(sync_rel_times)
    trial_starts = [float(i * 10.0) for i in range(n_trials)]
    trials = []

    for rel in sync_rel_times:
        if rel is None:
            states = {}
        else:
            states = {"SYNC": [rel, rel + 0.1]}
        trials.append({"States": states})

    return {
        "SessionData": {
            "nTrials": n_trials,
            "TrialStartTimestamp": trial_starts,
            "TrialTypes": [1] * n_trials,
            "RawEvents": {"Trial": trials},
        }
    }


def _trial_config() -> List[Dict[str, object]]:
    """Return a single trial-type sync configuration."""
    return [{"trial_type": 1, "sync_signal": "SYNC", "sync_ttl": "ttl_sync"}]


class TestRobustTTLAlignment:
    """Tests for robust Bpod↔TTL alignment logic."""

    def test_interpolates_missing_middle_pulse(self) -> None:
        """Should interpolate offset when middle TTL pulse is missing."""
        bpod_data = _build_bpod_data([1.0, 1.0, 1.0])
        ttl_pulses = {"ttl_sync": [101.0, 121.0]}

        offsets, _, stats = align_bpod_trials_to_ttl_robust(
            trial_type_configs=_trial_config(),
            bpod_data=bpod_data,
            ttl_pulses=ttl_pulses,
            tolerance_s=0.5,
            min_matches=2,
            max_start_trial_search=3,
        )

        assert offsets[1] == pytest.approx(100.0, abs=1e-6)
        assert offsets[2] == pytest.approx(100.0, abs=1e-2)
        assert offsets[3] == pytest.approx(100.0, abs=1e-6)
        assert stats["offset_labels"]["2"] == "interpolated"

    def test_recovers_linear_drift(self) -> None:
        """Should track linear drift within tolerance on matched anchors."""
        bpod_data = _build_bpod_data([1.0, 1.0, 1.0, 1.0, 1.0])
        bpod_sync_times = [1.0 + i * 10.0 for i in range(5)]
        offsets_expected = [100.0 + 0.1 * (i + 1) for i in range(5)]
        ttl_pulses = {"ttl_sync": [t + o for t, o in zip(bpod_sync_times, offsets_expected)]}

        offsets, _, _ = align_bpod_trials_to_ttl_robust(
            trial_type_configs=_trial_config(),
            bpod_data=bpod_data,
            ttl_pulses=ttl_pulses,
            tolerance_s=0.5,
            min_matches=3,
            max_start_trial_search=5,
        )

        errors = [abs(offsets[i + 1] - offsets_expected[i]) for i in range(5)]
        assert max(errors) <= 0.2

    def test_skips_spurious_pulses(self) -> None:
        """Should skip spurious TTL pulses and still match trials."""
        bpod_data = _build_bpod_data([1.0, 1.0, 1.0])
        ttl_pulses = {"ttl_sync": [50.0, 101.0, 111.0, 121.0]}

        offsets, _, stats = align_bpod_trials_to_ttl_robust(
            trial_type_configs=_trial_config(),
            bpod_data=bpod_data,
            ttl_pulses=ttl_pulses,
            tolerance_s=0.5,
            min_matches=2,
            max_start_trial_search=3,
        )

        assert offsets[1] == pytest.approx(100.0, abs=1e-6)
        assert offsets[2] == pytest.approx(100.0, abs=1e-6)
        assert offsets[3] == pytest.approx(100.0, abs=1e-6)
        assert stats["skipped_ttl_pulses"] >= 1

    def test_fills_missing_sync_signal(self) -> None:
        """Should estimate offsets when sync_signal is missing in a trial."""
        bpod_data = _build_bpod_data([1.0, None, 1.0])
        ttl_pulses = {"ttl_sync": [101.0, 121.0]}

        offsets, _, stats = align_bpod_trials_to_ttl_robust(
            trial_type_configs=_trial_config(),
            bpod_data=bpod_data,
            ttl_pulses=ttl_pulses,
            tolerance_s=0.5,
            min_matches=2,
            max_start_trial_search=3,
        )

        assert offsets[1] == pytest.approx(100.0, abs=1e-6)
        assert offsets[2] == pytest.approx(100.0, abs=1e-2)
        assert offsets[3] == pytest.approx(100.0, abs=1e-6)
        assert stats["offset_labels"]["2"] in {"interpolated", "extrapolated"}
