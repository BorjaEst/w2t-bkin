"""Synthetic TTL pulse generation utilities.

Generates deterministic TTL pulse timestamp files compatible with the
loader in `w2t_bkin.sync.ttl`. Intended for tests, demos, and synthetic
end-to-end pipeline runs.

Features:
- `TTLGenerationOptions` Pydantic model grouping generation knobs.
- Deterministic pulse sequences (seeded RNG) with optional jitter.
- Per-TTL overrides for pulse counts and rates.
- Writer that respects session TTL glob pattern conventions.
- Convenience function to generate & write for a `Session` model.

TTL File Format:
        One floating-point timestamp per line (seconds). Lines are sorted.

Example:
        from synthetic.session_synth import build_session
        from synthetic.ttl_synth import TTLGenerationOptions, generate_and_write_ttls_for_session

        session = build_session()  # contains TTL definitions (e.g., ttl_sync)
        opts = TTLGenerationOptions(pulses_per_ttl=100, rate_hz=30.0, jitter_s=0.0005)
        mapping = generate_and_write_ttls_for_session(session, base_dir='temp/Session-SYNTH-0001', options=opts)
        print(mapping['ttl_sync'])  # path to generated pulse file

Smoke test (combined with loader):
        from w2t_bkin.config import load_session
        from w2t_bkin.sync import get_ttl_pulses
        session = load_session('temp/Session-SYNTH-0001/session.toml')
        pulses = get_ttl_pulses(session)
        print(len(pulses['ttl_sync']))  # 100
"""

from __future__ import annotations

from pathlib import Path
import random
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from synthetic.utils import deterministic_rng, write_float_lines
from w2t_bkin.domain.session import Session as SessionModel


class TTLGenerationOptions(BaseModel):
    """Knobs controlling synthetic TTL pulse generation.

    Fields mirror typical acquisition properties while remaining
    lightweight. All pulses are generated with a deterministic RNG
    initialized from `seed` and TTL id to ensure reproducibility.
    """

    pulses_per_ttl: int = Field(default=60, ge=0, description="Default number of pulses per TTL channel")
    rate_hz: float = Field(default=30.0, gt=0, description="Nominal pulse rate (interval = 1/rate_hz) if used")
    start_time_s: float = Field(default=0.0, ge=0, description="Start time for first pulse")
    jitter_s: float = Field(default=0.0, ge=0, description="Uniform jitter magnitude applied per pulse (±jitter_s)")
    seed: int = Field(default=12345, description="Base RNG seed for deterministic generation")
    pulses_per_ttl_overrides: Dict[str, int] = Field(default_factory=dict, description="Per-TTL pulse count overrides")
    rate_overrides_hz: Dict[str, float] = Field(default_factory=dict, description="Per-TTL rate overrides")
    multi_file: bool = Field(default=False, description="If True, split pulses into two files per TTL (even/odd)")


def generate_ttl_pulses(ttl_ids: List[str], *, options: Optional[TTLGenerationOptions] = None, **overrides) -> Dict[str, List[float]]:
    """Generate synthetic TTL pulse timestamps for provided TTL IDs.

    Preferred: pass `options=TTLGenerationOptions(...)`.
    Convenience: overrides accepted as kwargs (merged into options).
    """
    base = options or TTLGenerationOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    pulses: Dict[str, List[float]] = {}
    for tid in ttl_ids:
        count = base.pulses_per_ttl_overrides.get(tid, base.pulses_per_ttl)
        rate = base.rate_overrides_hz.get(tid, base.rate_hz)
        interval = 1.0 / rate
        rng = deterministic_rng(base.seed, tid)

        channel_pulses: List[float] = []
        for i in range(count):
            t = base.start_time_s + i * interval
            if base.jitter_s > 0:
                t += rng.uniform(-base.jitter_s, base.jitter_s)
            if t < 0:
                t = 0.0
            channel_pulses.append(t)

        channel_pulses.sort()
        pulses[tid] = channel_pulses
    return pulses


def _derive_output_paths(pattern: str, ttl_id: str, multi_file: bool) -> List[Path]:
    """Derive concrete output file paths from a session TTL glob pattern.

    Strategy:
    - Replace wildcard '*' with a deterministic suffix.
    - If no wildcard present, append an index for multi-file scenario.
    """
    # Example pattern: 'TTLs/ttl_sync_*.txt'
    path = Path(pattern)
    parent = path.parent
    stem = path.name

    if "*" in stem:
        base_stem = stem.replace("*", "")
        if multi_file:
            return [parent / f"{base_stem}partA.txt", parent / f"{base_stem}partB.txt"]
        return [parent / f"{base_stem}0001.txt"]
    else:
        if multi_file:
            return [parent / f"{stem}.partA", parent / f"{stem}.partB"]
        return [parent / stem]


def write_ttl_pulse_files(
    session: SessionModel,
    pulses: Dict[str, List[float]],
    base_dir: Union[str, Path],
    *,
    multi_file: bool = False,
    overwrite: bool = True,
) -> Dict[str, List[Path]]:
    """Write TTL pulse lists to disk matching session TTL patterns.

    Returns mapping TTL id -> list of written file paths.
    """
    base_dir = Path(base_dir)
    output: Dict[str, List[Path]] = {}

    for ttl_cfg in session.TTLs:
        tid = ttl_cfg.id
        channel_pulses = pulses.get(tid, [])
        pattern = ttl_cfg.paths
        paths = _derive_output_paths(pattern, tid, multi_file)
        concrete_paths: List[Path] = []
        for p in paths:
            full = base_dir / p
            full.parent.mkdir(parents=True, exist_ok=True)
            if not overwrite and full.exists():
                concrete_paths.append(full)
                continue
            write_float_lines(full, channel_pulses, decimals=6, overwrite=True)
            concrete_paths.append(full)
        output[tid] = concrete_paths
    return output


def generate_and_write_ttls_for_session(
    session: SessionModel,
    base_dir: Union[str, Path],
    *,
    options: Optional[TTLGenerationOptions] = None,
    **overrides,
) -> Dict[str, List[Path]]:
    """Generate pulses for each TTL in `session` and write them to disk."""
    ttl_ids = [ttl.id for ttl in session.TTLs]
    pulses = generate_ttl_pulses(ttl_ids, options=options, **overrides)
    multi_file = options.multi_file if options else False
    return write_ttl_pulse_files(session, pulses, base_dir, multi_file=multi_file)


if __name__ == "__main__":
    from synthetic.session_synth import build_session

    out_dir = Path("temp/Session-SYNTH-TTL")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths_map = generate_and_write_ttls_for_session(
        session=build_session(),
        base_dir=out_dir,
        options=TTLGenerationOptions(pulses_per_ttl=10, rate_hz=20.0),
    )
    for tid, paths in paths_map.items():
        print(f"TTL {tid} -> {', '.join(str(p) for p in paths)}")
