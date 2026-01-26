"""Robust TTL synchronization for Bpod trials.

Implements a drift-aware alignment that tolerates missing TTL pulses and
still returns a complete per-trial offset mapping.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence, Tuple

import numpy as np

from w2t_bkin.exceptions import SyncError
from w2t_bkin.sync.ttl import BpodTrialTypeConfig, get_sync_time_from_bpod_trial
from w2t_bkin.utils import convert_matlab_struct, to_scalar

logger = logging.getLogger(__name__)


def _trial_type_config_value(cfg: object, key: str):
    """Read a value from a trial-type config.

    Args:
        cfg: Trial type config (dict-like or attribute-based).
        key: Key name to read.

    Returns:
        Value for the requested key.
    """
    if hasattr(cfg, key):
        return getattr(cfg, key)
    if isinstance(cfg, dict):
        return cfg[key]
    if hasattr(cfg, "get"):
        return cfg.get(key)
    raise TypeError("Trial type config must support attribute or dict-style access; " f"missing key '{key}'.")


def _score_candidate(
    trial_times: List[float],
    pulses: List[float],
    start_idx: int,
    offset_guess: float,
    tolerance_s: float,
    window: int,
) -> Tuple[float, int]:
    """Score a bootstrap candidate start index.

    Args:
        trial_times: Bpod sync times (absolute, Bpod timeline).
        pulses: TTL pulse times (absolute).
        start_idx: Index of the candidate starting trial.
        offset_guess: Initial offset guess based on first pulse.
        tolerance_s: Match tolerance in seconds.
        window: Number of steps to evaluate.

    Returns:
        Tuple of (score, matches).
    """
    i = start_idx
    j = 0
    steps = 0
    matches = 0
    penalty = 0.0

    while i < len(trial_times) and j < len(pulses) and steps < window:
        predicted = trial_times[i] + offset_guess
        pulse = pulses[j]

        if pulse < predicted - tolerance_s:
            j += 1
            penalty += 1.0
        elif pulse > predicted + tolerance_s:
            i += 1
            penalty += 1.0
        else:
            residual = abs(pulse - predicted)
            penalty += residual / max(tolerance_s, 1e-6)
            matches += 1
            i += 1
            j += 1

        steps += 1

    if matches == 0:
        penalty += 10.0

    return penalty, matches


def _bootstrap_start_index(
    trial_times: List[float],
    pulses: List[float],
    tolerance_s: float,
    max_start_trial_search: int,
) -> int:
    """Choose a bootstrap start index for robust matching.

    Args:
        trial_times: Bpod sync times (absolute, Bpod timeline).
        pulses: TTL pulse times (absolute).
        tolerance_s: Match tolerance in seconds.
        max_start_trial_search: Max number of trials to test.

    Returns:
        Index of the selected start trial.
    """
    if not trial_times or not pulses:
        return 0

    search_limit = min(len(trial_times), max_start_trial_search)
    best_score = float("inf")
    best_idx = 0
    best_matches = -1
    window = min(20, len(trial_times), len(pulses))

    for idx in range(search_limit):
        offset_guess = pulses[0] - trial_times[idx]
        score, matches = _score_candidate(
            trial_times,
            pulses,
            idx,
            offset_guess,
            tolerance_s,
            window,
        )

        if matches > best_matches or (matches == best_matches and score < best_score):
            best_score = score
            best_matches = matches
            best_idx = idx

    return best_idx


def _match_trials_to_pulses(
    trial_nums: List[int],
    trial_times: List[float],
    pulses: List[float],
    tolerance_s: float,
    max_start_trial_search: int,
) -> Tuple[List[Tuple[int, float, float]], Dict[str, int]]:
    """Match trials to TTL pulses with tolerance and monotonic ordering.

    Args:
        trial_nums: Trial numbers for the sync times.
        trial_times: Bpod sync times (absolute, Bpod timeline).
        pulses: TTL pulse times (absolute).
        tolerance_s: Match tolerance in seconds.
        max_start_trial_search: Max number of trials to test for bootstrapping.

    Returns:
        Tuple of (anchors, counters) where anchors are
        (trial_num, pulse_time, offset) triples.
    """
    anchors: List[Tuple[int, float, float]] = []
    counters = {"skipped_trials": 0, "skipped_pulses": 0, "matched": 0}

    if not trial_times or not pulses:
        return anchors, counters

    start_idx = _bootstrap_start_index(trial_times, pulses, tolerance_s, max_start_trial_search)
    offset_guess = pulses[0] - trial_times[start_idx]

    i = start_idx
    j = 0

    while i < len(trial_times) and j < len(pulses):
        if len(anchors) >= 2:
            trial_a, _, offset_a = anchors[-2]
            trial_b, _, offset_b = anchors[-1]
            slope = (offset_b - offset_a) / max(trial_b - trial_a, 1)
            offset_pred = offset_b + slope * (trial_nums[i] - trial_b)
        elif anchors:
            offset_pred = anchors[-1][2]
        else:
            offset_pred = offset_guess

        predicted = trial_times[i] + offset_pred
        pulse = pulses[j]

        if pulse < predicted - tolerance_s:
            counters["skipped_pulses"] += 1
            j += 1
            continue

        if pulse > predicted + tolerance_s:
            counters["skipped_trials"] += 1
            i += 1
            continue

        offset = pulse - trial_times[i]
        anchors.append((trial_nums[i], pulse, offset))
        counters["matched"] += 1
        i += 1
        j += 1

    counters["skipped_trials"] += max(0, len(trial_times) - i)
    counters["skipped_pulses"] += max(0, len(pulses) - j)

    return anchors, counters


def _fill_offsets(
    trial_numbers: List[int],
    anchor_offsets: Dict[int, float],
    min_matches: int,
) -> Tuple[Dict[int, float], Dict[int, str], Dict[str, int]]:
    """Fill missing offsets with drift-aware interpolation or fallback.

    Args:
        trial_numbers: List of all trial numbers.
        anchor_offsets: Offsets for matched anchor trials.
        min_matches: Minimum anchors required for interpolation.

    Returns:
        Tuple of (offsets, labels, counts).
    """
    offsets: Dict[int, float] = {}
    labels: Dict[int, str] = {}
    counts = {
        "matched": 0,
        "interpolated": 0,
        "extrapolated": 0,
        "fallback": 0,
    }

    if not anchor_offsets:
        for trial_num in trial_numbers:
            offsets[trial_num] = 0.0
            labels[trial_num] = "fallback"
            counts["fallback"] += 1
        return offsets, labels, counts

    anchor_trials = sorted(anchor_offsets.keys())
    anchor_values = [anchor_offsets[t] for t in anchor_trials]

    if len(anchor_trials) < min_matches:
        constant_offset = float(np.median(anchor_values))
        for trial_num in trial_numbers:
            offsets[trial_num] = constant_offset
            if trial_num in anchor_offsets:
                labels[trial_num] = "matched"
                counts["matched"] += 1
            else:
                labels[trial_num] = "fallback"
                counts["fallback"] += 1
        return offsets, labels, counts

    first_trial = anchor_trials[0]
    last_trial = anchor_trials[-1]

    for trial_num in trial_numbers:
        if trial_num in anchor_offsets:
            offsets[trial_num] = anchor_offsets[trial_num]
            labels[trial_num] = "matched"
            counts["matched"] += 1
            continue

        if trial_num < first_trial:
            t1, t2 = anchor_trials[0], anchor_trials[1]
            o1, o2 = anchor_offsets[t1], anchor_offsets[t2]
            slope = (o2 - o1) / max(t2 - t1, 1)
            offsets[trial_num] = o1 + slope * (trial_num - t1)
            labels[trial_num] = "extrapolated"
            counts["extrapolated"] += 1
            continue

        if trial_num > last_trial:
            t1, t2 = anchor_trials[-2], anchor_trials[-1]
            o1, o2 = anchor_offsets[t1], anchor_offsets[t2]
            slope = (o2 - o1) / max(t2 - t1, 1)
            offsets[trial_num] = o2 + slope * (trial_num - t2)
            labels[trial_num] = "extrapolated"
            counts["extrapolated"] += 1
            continue

        idx = max(i for i, t in enumerate(anchor_trials) if t < trial_num)
        left_trial = anchor_trials[idx]
        right_trial = anchor_trials[idx + 1]
        left_offset = anchor_offsets[left_trial]
        right_offset = anchor_offsets[right_trial]
        slope = (right_offset - left_offset) / max(right_trial - left_trial, 1)
        offsets[trial_num] = left_offset + slope * (trial_num - left_trial)
        labels[trial_num] = "interpolated"
        counts["interpolated"] += 1

    return offsets, labels, counts


def align_bpod_trials_to_ttl_robust(
    trial_type_configs: Sequence[BpodTrialTypeConfig],
    bpod_data: Dict,
    ttl_pulses: Dict[str, List[float]],
    *,
    tolerance_s: float,
    min_matches: int = 3,
    max_start_trial_search: int = 50,
) -> Tuple[Dict[int, float], List[str], Dict[str, object]]:
    """Align Bpod trials to TTL pulses using a robust strategy.

    Args:
        trial_type_configs: Trial type sync configurations.
        bpod_data: Parsed Bpod data (SessionData structure).
        ttl_pulses: TTL pulse timestamps per channel (absolute time).
        tolerance_s: Match tolerance in seconds.
        min_matches: Minimum anchors required for drift fitting.
        max_start_trial_search: Max trials to search for bootstrap.

    Returns:
        Tuple of (trial_offsets, warnings, stats).
    """
    if "SessionData" not in bpod_data:
        raise SyncError("Invalid Bpod structure: missing SessionData")

    session_data = convert_matlab_struct(bpod_data["SessionData"])
    n_trials = int(session_data.get("nTrials", 0))

    if n_trials == 0:
        return {}, ["No trials available for robust alignment"], {}

    if not isinstance(trial_type_configs, (list, tuple)):
        raise TypeError("trial_type_configs must be a list or tuple, got " f"{type(trial_type_configs).__name__}.")

    trial_type_map: Dict[int, Dict[str, str]] = {}
    for cfg in trial_type_configs:
        trial_type = int(_trial_type_config_value(cfg, "trial_type"))
        trial_type_map[trial_type] = {
            "sync_signal": _trial_type_config_value(cfg, "sync_signal"),
            "sync_ttl": _trial_type_config_value(cfg, "sync_ttl"),
        }

    if not trial_type_map:
        raise SyncError("No trial_type sync configuration provided")

    raw_events = convert_matlab_struct(session_data["RawEvents"])
    trial_data_list = raw_events["Trial"]
    trial_types_array = session_data.get("TrialTypes")
    if trial_types_array is None:
        trial_types_array = [1] * n_trials
        logger.warning("TrialTypes not found in Bpod data, defaulting to type 1")

    warnings_list: List[str] = []
    missing_sync_count = 0
    missing_ttl_config = 0

    channel_trials: Dict[str, List[Tuple[int, float]]] = {}

    for i in range(n_trials):
        trial_num = i + 1
        trial_type = int(to_scalar(trial_types_array, i))

        if trial_type not in trial_type_map:
            msg = f"Trial {trial_num}: trial_type {trial_type} not in sync config"
            warnings_list.append(msg)
            logger.warning(msg)
            missing_ttl_config += 1
            continue

        sync_signal = trial_type_map[trial_type]["sync_signal"]
        sync_ttl_id = trial_type_map[trial_type]["sync_ttl"]

        trial_data = convert_matlab_struct(trial_data_list[i])
        sync_time_rel = get_sync_time_from_bpod_trial(trial_data, sync_signal)

        if sync_time_rel is None:
            msg = f"Trial {trial_num}: sync_signal '{sync_signal}' missing"
            warnings_list.append(msg)
            logger.warning(msg)
            missing_sync_count += 1
            continue

        trial_start_ts = float(to_scalar(session_data["TrialStartTimestamp"], i))
        sync_abs = trial_start_ts + sync_time_rel

        if sync_ttl_id not in ttl_pulses:
            msg = f"Trial {trial_num}: TTL channel '{sync_ttl_id}' not found"
            warnings_list.append(msg)
            logger.warning(msg)
            missing_ttl_config += 1
            continue

        channel_trials.setdefault(sync_ttl_id, []).append((trial_num, sync_abs))

    anchor_offsets: Dict[int, float] = {}
    anchor_residuals: List[float] = []
    skipped_pulses = 0
    skipped_trials = 0

    for ttl_id, trials in channel_trials.items():
        pulses = ttl_pulses.get(ttl_id, [])
        if not pulses:
            msg = f"TTL channel '{ttl_id}' has no pulses for robust alignment"
            warnings_list.append(msg)
            logger.warning(msg)
            continue

        trial_nums = [t[0] for t in trials]
        trial_times = [t[1] for t in trials]
        trial_time_map = {t[0]: t[1] for t in trials}

        anchors, counters = _match_trials_to_pulses(
            trial_nums,
            trial_times,
            pulses,
            tolerance_s,
            max_start_trial_search,
        )

        skipped_pulses += counters["skipped_pulses"]
        skipped_trials += counters["skipped_trials"]

        for trial_num, pulse_time, offset in anchors:
            anchor_offsets[trial_num] = offset
            residual = (trial_time_map[trial_num] + offset) - pulse_time
            anchor_residuals.append(float(residual))

    all_trial_numbers = list(range(1, n_trials + 1))
    offsets, labels, fill_counts = _fill_offsets(
        all_trial_numbers,
        anchor_offsets,
        min_matches,
    )

    if not anchor_offsets:
        msg = "No anchor matches found; falling back to 0.0 offsets"
        warnings_list.append(msg)
        logger.warning(msg)
    elif len(anchor_offsets) < min_matches:
        msg = f"Only {len(anchor_offsets)} anchor(s) found; " "using constant-offset fallback"
        warnings_list.append(msg)
        logger.warning(msg)

    stats: Dict[str, object] = {
        "strategy": "hardware_pulse_robust",
        "total_trials": n_trials,
        "matched_trials": fill_counts["matched"],
        "interpolated_trials": fill_counts["interpolated"],
        "extrapolated_trials": fill_counts["extrapolated"],
        "fallback_trials": fill_counts["fallback"],
        "skipped_trials_missing_sync": missing_sync_count,
        "skipped_trials_missing_ttl": missing_ttl_config,
        "skipped_trials": skipped_trials,
        "skipped_ttl_pulses": skipped_pulses,
        "anchors": {
            "trial_numbers": sorted(anchor_offsets.keys()),
            "offsets": [anchor_offsets[t] for t in sorted(anchor_offsets.keys())],
        },
        "offset_labels": {str(k): v for k, v in labels.items()},
    }

    if anchor_residuals:
        abs_residuals = np.abs(np.array(anchor_residuals))
        stats["residuals_s"] = {
            "max_abs": float(np.max(abs_residuals)),
            "p95_abs": float(np.percentile(abs_residuals, 95)),
            "rms": float(np.sqrt(np.mean(abs_residuals**2))),
        }

    logger.info(
        "Robust TTL alignment: %s matched, %s interpolated, %s extrapolated",
        fill_counts["matched"],
        fill_counts["interpolated"],
        fill_counts["extrapolated"],
    )

    return offsets, warnings_list, stats
