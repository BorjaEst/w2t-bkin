"""Common utilities for synthetic data generators.

This module centralizes small, reusable helpers used by the synthetic
generators to keep the other modules focused and easier to maintain.

Utilities provided:
- Path derivation from glob-like patterns with `*` and sequencing
- Deterministic RNG creation from a base seed and components
- Clock drift helpers (ppm → time offset)
- Safe text/float writers with parent dir creation
- Minimal TOML key-value line rendering
"""

from __future__ import annotations

from pathlib import Path
import random
from typing import List, Optional, Union


def derive_sequenced_paths(
    pattern: Union[str, Path],
    count: int,
    *,
    default_ext: Optional[str] = None,
    pad: int = 4,
    dash_when_no_wildcard: bool = False,
    single_when_no_wildcard: bool = False,
) -> List[Path]:
    """Derive concrete file paths from a pattern that may include `*`.

    Behavior:
    - If the filename stem contains `*`, it will be replaced with a 1-based,
      zero-padded index of width `pad`, producing `count` paths.
    - If no wildcard is present and `single_when_no_wildcard` is True, a
      single path is returned regardless of `count`.
    - If no wildcard is present and `dash_when_no_wildcard` is True, then for
      `count > 1`, the index is appended as `-0001`, `-0002`, ... before the
      extension. For `count == 1`, no suffix is added.
    - If no wildcard and neither flag is set, a single path is returned.

    Extension handling:
    - If the name has no extension and `default_ext` is provided, it will be
      used (with leading dot). Otherwise, no extension is appended.
    """

    p = Path(pattern)
    parent = p.parent
    name = p.name

    if "." in name:
        stem, ext = name.rsplit(".", 1)
        ext = "." + ext
    else:
        stem = name
        ext = f".{default_ext}" if default_ext else ""

    paths: List[Path] = []
    if "*" in stem:
        base_stem = stem.replace("*", "")
        for i in range(1, max(1, count) + 1):
            paths.append(parent / f"{base_stem}{i:0{pad}d}{ext}")
        return paths

    # No wildcard in stem
    if single_when_no_wildcard:
        return [parent / f"{stem}{ext}"]

    if dash_when_no_wildcard and count > 1:
        for i in range(1, count + 1):
            paths.append(parent / f"{stem}-{i:0{pad}d}{ext}")
        return paths

    return [parent / f"{stem}{ext}"]


def replace_wildcard(pattern: Union[str, Path], replacement: str) -> Path:
    """Replace `*` in the filename stem with `replacement`.

    If no wildcard is present, the original path is returned.
    """

    p = Path(pattern)
    parent = p.parent
    name = p.name
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = name, ""

    if "*" in stem:
        stem = stem.replace("*", replacement)
    return parent / f"{stem}{ext}"


def ensure_parent_dir(path: Union[str, Path]) -> Path:
    """Ensure parent directory exists for the provided path and return Path."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_float_lines(
    path: Union[str, Path],
    values: List[float],
    *,
    decimals: int = 6,
    overwrite: bool = True,
) -> Path:
    """Write a list of floats to a file, one per line, formatted.

    Parent directory is created if needed. Returns the absolute Path.
    """

    p = ensure_parent_dir(path)
    if p.exists() and not overwrite:
        return p.resolve()
    fmt = f"{{:.{decimals}f}}\n"
    with open(p, "w", encoding="utf-8") as f:
        for v in values:
            f.write(fmt.format(float(v)))
    return p.resolve()


def deterministic_rng(seed: int, *components: Union[str, int]) -> random.Random:
    """Create a deterministic RNG from a base seed and additional components.

    The internal seed is a string in the form "{seed}:{comp1}:{comp2}:..." so
    that different components produce independent, reproducible streams.
    """

    joined = ":".join(str(c) for c in components)
    return random.Random(f"{seed}:{joined}")


def clock_drift_offset(elapsed_s: float, ppm: float) -> float:
    """Compute drift-induced offset (seconds) for elapsed time at given ppm.

    Positive ppm means the drifting clock runs fast.
    """

    return elapsed_s * (ppm / 1_000_000.0)


def apply_clock_drift(t_nominal_s: float, elapsed_from_start_s: float, ppm: float) -> float:
    """Apply clock drift to a nominal timestamp based on elapsed time and ppm."""

    return t_nominal_s + clock_drift_offset(elapsed_from_start_s, ppm)


def toml_kv_line(key: str, value: Union[str, int, float, bool]) -> str:
    """Render a minimal TOML key-value line for common scalar types."""

    if isinstance(value, str):
        return f'{key} = "{value}"\n'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}\n"
    return f"{key} = {value}\n"
