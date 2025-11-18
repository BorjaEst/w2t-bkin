"""Synthetic Bpod .mat file generator.

Creates minimal-yet-valid Bpod MATLAB .mat files that satisfy the
`w2t_bkin.events.bpod` loader and validators. Designed for tests,
examples, and E2E demos where real Bpod data is unavailable.

Structure written (per file):
- `SessionData` (MATLAB struct)
  - `nTrials`: int
  - `TrialStartTimestamp`: 1D float array [nTrials]
  - `TrialEndTimestamp`: 1D float array [nTrials]
  - `RawEvents`: struct
    - `Trial`: struct array length nTrials, each with:
      - `States`: struct (includes `ITI` [start, end])
      - `Events`: struct (empty arrays by default)

Notes:
- Uses `scipy.io.savemat` (scipy is declared in project dependencies).
- All generation is deterministic w.r.t. `seed`.
- Output file names follow the session's `bpod.path` glob pattern.
"""

from __future__ import annotations

from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field

from synthetic.utils import derive_sequenced_paths

try:
    from scipy.io import savemat  # type: ignore
except Exception as e:  # pragma: no cover - scipy is required by project
    savemat = None  # type: ignore

from w2t_bkin.domain.session import Session as SessionModel
from w2t_bkin.events.bpod import write_bpod_mat


class BpodSynthOptions(BaseModel):
    """Options controlling synthetic Bpod generation."""

    files: int = Field(2, ge=1, description="How many .mat files to generate")
    trials_per_file: int = Field(10, ge=0, description="Trials per generated file")
    start_time_s: float = Field(0.0, ge=0)
    trial_interval_s: float = Field(2.0, gt=0, description="Start-to-start interval between trials")
    trial_duration_s: float = Field(1.0, gt=0, description="Duration of a trial (for end timestamp)")
    jitter_s: float = Field(0.0, ge=0, description="Uniform jitter magnitude applied to start times")
    clock_jitter_ppm: float = Field(0.0, description="Clock drift in parts per million (positive = Bpod clock runs fast, negative = slow)")
    seed: int = Field(1234, description="Random seed for deterministic jitter")
    include_states: bool = Field(True, description="Include minimal States with ITI timing")
    include_events: bool = Field(True, description="Include Events struct (empty arrays by default)")
    sync_signal_name: str = Field("SyncSignal1", description="Name of the sync state (e.g., SyncSignal1)")
    sync_delay_s: float = Field(0.0, ge=0, description="Delay of sync signal within each trial (relative to trial start)")


def _derive_bpod_paths(pattern: str, files: int) -> List[Path]:
    """Derive concrete output paths from a glob pattern like `Bpod/*.mat`.

    Uses shared sequencing helper; when no wildcard is present, always
    generates a single file path (ignores `files`) to match expectations.
    """
    return derive_sequenced_paths(
        pattern,
        files,
        default_ext="mat",
        pad=4,
        dash_when_no_wildcard=False,
        single_when_no_wildcard=True,
    )


def _build_sessiondata_dict(
    n_trials: int,
    *,
    start_time_s: float,
    trial_interval_s: float,
    trial_duration_s: float,
    jitter_s: float,
    clock_jitter_ppm: float,
    rng: random.Random,
    include_states: bool,
    include_events: bool,
    trial_type_codes: Optional[List[int]] = None,
    sync_signal_name: str = "SyncSignal1",
    sync_delay_s: float = 0.0,
) -> Dict[str, object]:
    """Construct a Python dict closely matching Bpod SessionData shape.

    Includes required fields used by the events parser and reasonable
    placeholders for optional ones (TrialSettings, TrialTypes, RawData).

    Clock drift simulation:
    - clock_jitter_ppm: Parts per million clock drift (e.g., 100 ppm = 0.0001 = 0.01%)
    - Positive values: Bpod clock runs fast (timestamps advance more than real time)
    - Negative values: Bpod clock runs slow (timestamps advance less than real time)
    - Drift accumulates linearly over time
    """

    starts: List[float] = []
    ends: List[float] = []
    trials: List[Dict[str, object]] = []

    # Clock drift simulation: accumulate drift over session time
    # drift_factor = 1 + (clock_jitter_ppm / 1_000_000)
    # For each second of real time, Bpod clock advances by drift_factor seconds
    drift_factor = 1.0 + (clock_jitter_ppm / 1_000_000.0)

    for i in range(n_trials):
        # Nominal time (what TTL clock sees)
        t0_nominal = start_time_s + i * trial_interval_s

        # Apply clock drift: elapsed time from session start gets scaled by drift
        elapsed_from_start = i * trial_interval_s
        drift_offset = elapsed_from_start * (drift_factor - 1.0)
        t0 = t0_nominal + drift_offset

        if jitter_s > 0:
            t0 += rng.uniform(-jitter_s, jitter_s)

        t1 = t0 + trial_duration_s
        if t0 < 0:
            t0 = 0.0
        if t1 < 0:
            t1 = 0.0

        starts.append(float(t0))
        ends.append(float(t1))

        # Per-trial structures
        states_struct: Dict[str, object] = {}
        events_struct: Dict[str, object] = {}
        if include_states:
            # State times are relative to trial start (t0), not absolute
            # ITI runs from 0 to trial duration
            states_struct["ITI"] = np.array([0.0, trial_duration_s], dtype=float)
            # Add sync signal state at the specified delay within the trial (relative timing)
            sync_start_rel = sync_delay_s
            sync_end_rel = min(sync_start_rel + 0.1, trial_duration_s)  # 100ms sync pulse
            states_struct[sync_signal_name] = np.array([sync_start_rel, sync_end_rel], dtype=float)
        if include_events:
            # Empty arrays for optional event signals
            events_struct["Port1In"] = np.array([], dtype=float)
            events_struct["Port1Out"] = np.array([], dtype=float)

        trial_struct: Dict[str, object] = {}
        if include_states:
            trial_struct["States"] = states_struct
        if include_events:
            trial_struct["Events"] = events_struct
        trials.append(trial_struct)

    raw_events = {"Trial": np.array(trials, dtype=object)}

    # Trial settings (list of per-trial dicts; keep minimal)
    trial_settings: List[Dict[str, object]] = [{"ProtocolState": "ITI"} for _ in range(n_trials)]

    # Trial types (uint8 codes)
    if n_trials > 0:
        if trial_type_codes:
            codes = [trial_type_codes[i % len(trial_type_codes)] for i in range(n_trials)]
        else:
            codes = [1 for _ in range(n_trials)]
        trial_types = np.array(codes, dtype=np.uint8)
    else:
        trial_types = np.array([], dtype=np.uint8)

    # RawData.OriginalStateNamesByNumber is an object array; we provide a
    # simple state list per trial to mirror typical Bpod structures.
    state_names = np.array([np.array(["ITI", "End"], dtype=object) for _ in range(n_trials)], dtype=object)
    raw_data = {"OriginalStateNamesByNumber": state_names}

    session_data = {
        "nTrials": int(n_trials),
        "TrialStartTimestamp": np.array(starts, dtype=float),
        "TrialEndTimestamp": np.array(ends, dtype=float),
        "RawEvents": raw_events,
        "TrialSettings": trial_settings,
        "TrialTypes": trial_types,
        "RawData": raw_data,
    }
    return session_data


def write_bpod_mat_files_for_session(
    session: SessionModel,
    base_dir: Union[str, Path],
    *,
    options: Optional[BpodSynthOptions] = None,
    **overrides,
) -> List[Path]:
    """Generate and write Bpod .mat files based on a `Session`'s config.

    Returns list of written file paths (ordered).
    """
    base = options or BpodSynthOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    if savemat is None:
        raise RuntimeError("scipy.io.savemat is required to write Bpod .mat files")

    out_base = Path(base_dir)
    paths = _derive_bpod_paths(session.bpod.path, base.files)
    rng = random.Random(base.seed)

    written: List[Path] = []
    for idx, rel in enumerate(paths):
        full = out_base / rel
        full.parent.mkdir(parents=True, exist_ok=True)

        # Build trial type codes from session config if present
        tt_codes = [tt.trial_type for tt in session.bpod.trial_types] if session.bpod and session.bpod.trial_types else None
        # Extract sync_signal name from first trial type if available
        sync_signal = session.bpod.trial_types[0].sync_signal if session.bpod and session.bpod.trial_types else base.sync_signal_name

        session_dict = _build_sessiondata_dict(
            base.trials_per_file,
            start_time_s=base.start_time_s,
            trial_interval_s=base.trial_interval_s,
            trial_duration_s=base.trial_duration_s,
            jitter_s=base.jitter_s,
            clock_jitter_ppm=base.clock_jitter_ppm,
            rng=rng,
            include_states=base.include_states,
            include_events=base.include_events,
            trial_type_codes=tt_codes,
            sync_signal_name=sync_signal,
            sync_delay_s=base.sync_delay_s,
        )

        # Use events API to validate and write .mat in a consistent manner
        write_bpod_mat({"SessionData": session_dict}, full)
        written.append(full.resolve())

    return written


def generate_bpod_files_for_session(session: SessionModel, base_dir: Union[str, Path], **kwargs) -> List[Path]:
    """Convenience wrapper around `write_bpod_mat_files_for_session`."""
    return write_bpod_mat_files_for_session(session, base_dir, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    from synthetic.session_synth import build_session

    s = build_session()
    out = Path("temp/Session-SYNTH-BPOD")
    out.mkdir(parents=True, exist_ok=True)
    files = write_bpod_mat_files_for_session(s, out, options=BpodSynthOptions(files=2, trials_per_file=5))
    for f in files:
        print(f"Wrote: {f}")
