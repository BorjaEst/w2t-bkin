"""Plotting helpers for synchronization examples.

These functions are intentionally lightweight, with graceful fallbacks
if matplotlib is not installed (the example remains runnable without plots).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

try:  # Optional dependency for examples
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - optional
    plt = None  # type: ignore


def _ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def plot_ttl_timeline(
    ttl_pulses: Dict[str, List[float]],
    *,
    channel_order: Optional[Iterable[str]] = None,
    out_path: Path,
) -> Optional[Path]:
    """Plot TTL pulse times for selected channels on a shared timeline.

    - Draws scatter lines for each channel at a distinct y-level.
    - If matplotlib is unavailable, returns None.
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_ttl_timeline: matplotlib not available")
        return None

    _ensure_parent(out_path)
    order = list(channel_order) if channel_order else list(ttl_pulses.keys())
    ys = np.arange(len(order))[::-1]

    fig, ax = plt.subplots(figsize=(10, 2 + 0.6 * len(order)))
    for y, ch in zip(ys, order):
        ts = ttl_pulses.get(ch, [])
        if len(ts) == 0:
            continue
        ax.vlines(ts, y - 0.35, y + 0.35, colors="tab:blue" if y % 2 == 0 else "tab:orange", alpha=0.8, linewidth=1.0)
        ax.text(ts[0], y + 0.45, ch, fontsize=9, va="bottom")

    ax.set_xlabel("Time (s)")
    ax.set_yticks([])
    ax.set_title("TTL pulse timeline")
    ax.grid(True, axis="x", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_trial_offsets(
    trial_offsets: Dict[int, float],
    *,
    out_path: Path,
) -> Optional[Path]:
    """Plot per-trial offsets and a simple linear trend line.

    - X-axis is trial number; Y-axis is offset (seconds).
    - If matplotlib is unavailable, returns None.
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_trial_offsets: matplotlib not available")
        return None

    _ensure_parent(out_path)
    trials = np.array(sorted(trial_offsets.keys()), dtype=float)
    offsets = np.array([trial_offsets[int(t)] for t in trials], dtype=float)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(trials, offsets, marker="o", linestyle="-", color="tab:green", label="Offsets")
    if len(trials) >= 2:
        m, b = np.polyfit(trials, offsets, deg=1)
        ax.plot(trials, m * trials + b, linestyle="--", color="tab:red", label=f"Trend (slope={m:.4g} s/trial)")

    ax.axhline(0.0, color="k", linewidth=1, alpha=0.5)
    ax.set_xlabel("Trial number")
    ax.set_ylabel("Offset (s)")
    ax.set_title("Per-trial alignment offsets")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_alignment_example(
    *,
    trial_number: int,
    trial_start_ts: float,
    trial_end_ts: float,
    sync_time_rel: float,
    ttl_sync_time: float,
    out_path: Path,
    extra_bpod_rel: Optional[List[tuple[str, float]]] = None,
    extra_ttl_series: Optional[Dict[str, List[float]]] = None,
) -> Optional[Path]:
    """Visualize alignment for a single trial with richer context.

    Draws:
    - Trial start and end (absolute, Bpod-derived)
    - Bpod sync time (TrialStartTimestamp + sync_time_rel)
    - TTL sync pulse (absolute)
    - Optional extra Bpod-relative signals (converted to absolute)
    - Optional extra TTL series (e.g., camera TTL pulses near the trial)
    Shows the offset as the horizontal distance between Bpod sync and TTL sync.
    """

    if plt is None:  # pragma: no cover
        return None

    _ensure_parent(out_path)
    bpod_sync_time = trial_start_ts + sync_time_rel

    # Determine plot bounds using included signals
    times_for_bounds: List[float] = [trial_start_ts, trial_end_ts, bpod_sync_time, ttl_sync_time]
    if extra_bpod_rel:
        times_for_bounds += [trial_start_ts + rel for _, rel in extra_bpod_rel]
    if extra_ttl_series:
        for _, series in extra_ttl_series.items():
            times_for_bounds += series
    t_min = min(times_for_bounds) - 0.5
    t_max = max(times_for_bounds) + 0.5

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.hlines(1.0, t_min, t_max, color="0.9")

    # Trial window
    ax.vlines([trial_start_ts, trial_end_ts], 0.6, 1.4, colors=["tab:gray", "tab:gray"], linewidth=1.5)
    ax.text(trial_start_ts, 1.42, "trial start", fontsize=8, ha="center", va="bottom", color="tab:gray")
    ax.text(trial_end_ts, 1.42, "trial end", fontsize=8, ha="center", va="bottom", color="tab:gray")

    # Primary sync markers
    ax.vlines(bpod_sync_time, 0.7, 1.3, colors="tab:blue", linewidth=2.0, label="Bpod sync (Bpod time)")
    ax.vlines(ttl_sync_time, 0.7, 1.3, colors="tab:orange", linewidth=2.0, label="TTL sync (abs time)")

    # Extra Bpod-relative signals
    if extra_bpod_rel:
        for label, rel in extra_bpod_rel:
            t_abs = trial_start_ts + rel
            ax.vlines(t_abs, 0.7, 1.3, colors="tab:purple", linewidth=1.2, linestyles=":")
            ax.text(t_abs, 0.68, label, fontsize=7, ha="center", va="top", rotation=90, color="tab:purple")

    # Extra TTL series (e.g., camera TTL pulses)
    if extra_ttl_series:
        for label, series in extra_ttl_series.items():
            if not series:
                continue
            ax.vlines(series, 0.6, 0.9, colors="tab:green", alpha=0.6, linewidth=0.8)
            ax.text(series[0], 0.92, label, fontsize=8, va="bottom", color="tab:green")

    # Offset arrow
    x0, x1 = sorted([bpod_sync_time, ttl_sync_time])
    ax.annotate(
        "",
        xy=(x1, 1.25),
        xytext=(x0, 1.25),
        arrowprops=dict(arrowstyle="<->", color="tab:red"),
    )
    ax.text((x0 + x1) / 2, 1.28, f"offset = {x1 - x0:.4f} s", color="tab:red", ha="center", fontsize=9)

    ax.set_ylim(0.5, 1.5)
    ax.set_xlim(t_min, t_max)
    ax.set_yticks([])
    ax.set_xlabel("Time (s)")
    ax.set_title(f"Alignment example — Trial {trial_number}")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_alignment_grid(
    trials_info: List[Dict[str, float]],
    *,
    out_path: Path,
    cols: int = 3,
) -> Optional[Path]:
    """Small-multiples panel of alignment for multiple trials.

    Each element in `trials_info` must contain keys:
      - trial_number, trial_start_ts, trial_end_ts, sync_time_rel, ttl_sync_time
    """

    if plt is None:  # pragma: no cover
        return None

    if not trials_info:
        return None

    _ensure_parent(out_path)

    n = len(trials_info)
    cols = max(1, int(cols))
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 2.6 * rows), squeeze=False)

    for idx, info in enumerate(trials_info):
        r, c = divmod(idx, cols)
        ax = axes[r][c]
        tn = int(info["trial_number"])  # type: ignore
        t0 = float(info["trial_start_ts"])  # type: ignore
        t1 = float(info["trial_end_ts"])  # type: ignore
        sync_rel = float(info["sync_time_rel"])  # type: ignore
        ttl_sync = float(info["ttl_sync_time"])  # type: ignore
        bpod_sync = t0 + sync_rel
        offset = ttl_sync - bpod_sync

        # Bounds around window and syncs
        t_min = min(t0, bpod_sync, ttl_sync) - 0.3
        t_max = max(t1, bpod_sync, ttl_sync) + 0.3

        ax.hlines(1.0, t_min, t_max, color="0.9")
        ax.vlines([t0, t1], 0.6, 1.4, colors="tab:gray", linewidth=1.0)
        ax.vlines(bpod_sync, 0.7, 1.3, colors="tab:blue", linewidth=1.8)
        ax.vlines(ttl_sync, 0.7, 1.3, colors="tab:orange", linewidth=1.8)

        # Offset annotation
        x0, x1 = sorted([bpod_sync, ttl_sync])
        ax.annotate("", xy=(x1, 1.22), xytext=(x0, 1.22), arrowprops=dict(arrowstyle="<->", color="tab:red", lw=1))
        ax.text((x0 + x1) / 2, 1.24, f"{x1 - x0:.3f}s", color="tab:red", ha="center", fontsize=7)

        ax.set_xlim(t_min, t_max)
        ax.set_ylim(0.55, 1.45)
        ax.set_yticks([])
        ax.set_xlabel("s", fontsize=8)
        ax.set_title(f"Trial {tn}", fontsize=10)

    # Hide any unused axes
    for j in range(n, rows * cols):
        r, c = divmod(j, cols)
        axes[r][c].axis("off")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_sync_recovery(
    *,
    bpod_times: np.ndarray,
    recorded_times: np.ndarray,
    fitted_slope: float,
    fitted_intercept: float,
    valid_mask: np.ndarray,
    final_errors: np.ndarray,
    max_error_ms: float,
    rms_error_ms: float,
    out_path: Path,
) -> Optional[Path]:
    """Plot sync recovery diagnostics showing outlier detection and final alignment errors.

    Creates a two-panel figure:
    - Top: Residuals before correction (naive nearest-neighbor mapping) with outliers highlighted
    - Bottom: Final alignment errors after robust recovery

    Both plots share the same y-axis limits for easy comparison.

    Args:
        bpod_times: Bpod trial start timestamps (source timeline)
        recorded_times: Recorded TTL pulse timestamps (target timeline, with missing data)
        fitted_slope: Recovered linear model slope
        fitted_intercept: Recovered linear model intercept
        valid_mask: Boolean mask indicating inlier pairs (True = valid, False = outlier)
        final_errors: Final alignment errors after recovery (seconds)
        max_error_ms: Maximum alignment error in milliseconds
        rms_error_ms: RMS alignment error in milliseconds
        out_path: Output path for the plot

    Returns:
        Path to saved plot, or None if matplotlib unavailable
    """
    if plt is None:  # pragma: no cover
        return None

    _ensure_parent(out_path)

    # Import map_nearest locally to avoid circular dependency
    from w2t_bkin.sync import map_nearest

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Plot 1: Residuals before correction (showing outliers)
    indices = map_nearest(bpod_times.tolist(), recorded_times.tolist())
    raw_diffs = recorded_times[indices] - bpod_times

    ax1.plot(bpod_times, raw_diffs * 1000, "r.", markersize=8, label="All Pairs (Naive Mapping)", alpha=0.6)
    ax1.plot(bpod_times[valid_mask], raw_diffs[valid_mask] * 1000, "g.", markersize=8, label="Valid Pairs (Inliers)")
    ax1.axhline(fitted_intercept * 1000, color="b", linestyle="--", linewidth=2, label="Recovered Intercept")
    ax1.set_title("Outlier Detection: Missing TTL Pulses Create Obvious Mismatches", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Time Difference (ms)", fontsize=10)
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Final Alignment Error
    ax2.plot(bpod_times, final_errors * 1000, "b.-", linewidth=1, markersize=4)
    ax2.axhline(0, color="k", linestyle="--", alpha=0.3)
    ax2.set_title("Final Alignment Error After Recovery (vs Ground Truth)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Session Time (s)", fontsize=10)
    ax2.set_ylabel("Alignment Error (ms)", fontsize=10)
    ax2.grid(True, alpha=0.3)

    # Set common y-axis limits for both plots
    all_diffs_ms = np.concatenate([raw_diffs * 1000, final_errors * 1000])
    y_min = np.min(all_diffs_ms)
    y_max = np.max(all_diffs_ms)
    y_margin = (y_max - y_min) * 0.1  # Add 10% margin
    y_lim = [y_min - y_margin, y_max + y_margin]
    ax1.set_ylim(y_lim)
    ax2.set_ylim(y_lim)

    # Add error statistics to plot
    ax2.text(
        0.02,
        0.98,
        f"Max Error: {max_error_ms:.4f} ms\nRMS Error: {rms_error_ms:.4f} ms",
        transform=ax2.transAxes,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
