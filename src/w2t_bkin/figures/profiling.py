"""Pipeline profiling and diagnostic figures.

This module generates diagnostic plots and profiling information for
pipeline execution to help understand performance and validate results.

Key figures generated:
- pipeline_execution.png: Combined timing and timeline visualization
- synchronization_stats.png: Jitter, offset, and alignment quality metrics
- ttl_inter_pulse_intervals.png: TTL pulse interval analysis (detects gaps, not missing time)
- sync_quality_and_completeness.png: Combined Bpod-TTL sync quality + trial data completeness
  - For <=100 trials: detailed heatmap with checkmarks
  - For >100 trials: summary bars and missing data timeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from matplotlib.gridspec import GridSpec
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
    GridSpec = None

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)


@dataclass
class PhaseProfile:
    """Profiling information for a single phase."""

    phase_id: int
    phase_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineProfile:
    """Complete profiling information for pipeline execution."""

    subject_id: str
    session_id: str
    config_path: str
    start_time: float = field(default_factory=lambda: time.time())
    end_time: float = 0.0
    total_duration: float = 0.0
    phases: List[PhaseProfile] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    def add_phase(self, phase: PhaseProfile) -> None:
        """Add a phase profile to the pipeline."""
        self.phases.append(phase)

    def finalize(self) -> None:
        """Finalize profiling by calculating total duration."""
        if self.end_time == 0.0:
            self.end_time = time.time()
            self.total_duration = self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "config_path": str(self.config_path),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration": self.total_duration,
            "success": self.success,
            "error": self.error,
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "phase_name": p.phase_name,
                    "duration": p.duration,
                    "success": p.success,
                    "error": p.error,
                    "metadata": p.metadata,
                }
                for p in self.phases
            ],
        }


class PhaseTimer:
    """Context manager for timing pipeline phases."""

    def __init__(self, profile: PipelineProfile, phase_index: int, phase_name: str):
        """Initialize phase timer.

        Args:
            profile: PipelineProfile to add phase timing to
            phase_index: Numeric phase identifier
            phase_name: Human-readable phase name
        """
        self.profile = profile
        self.phase_id = phase_index
        self.phase_name = phase_name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.error: Optional[str] = None

    def __enter__(self) -> PhaseTimer:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Stop timing and record phase profile."""
        self.end_time = time.perf_counter()
        duration = self.end_time - self.start_time

        if exc_type is not None:
            self.error = str(exc_val)

        # Create phase profile and add to pipeline
        phase_profile = PhaseProfile(
            phase_id=self.phase_id,
            phase_name=self.phase_name,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=duration,
            success=exc_type is None,
            error=self.error,
        )
        self.profile.add_phase(phase_profile)

        return False  # Don't suppress exceptions


def plot_pipeline_execution(profile: PipelineProfile, save_path: Path) -> Optional[Path]:
    """Plot pipeline execution with timing bar chart and Gantt timeline.

    Creates a two-panel figure:
    - Top panel: Phase timing bar chart showing duration of each phase
    - Bottom panel: Phase timeline (Gantt chart) showing execution sequence

    Args:
        profile: Pipeline profiling data
        save_path: Path where plot should be saved

    Returns:
        Path to saved plot, or None if matplotlib unavailable
    """
    if plt is None or GridSpec is None:
        return None

    if len(profile.phases) == 0:
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Create figure with two panels
    fig = plt.figure(figsize=(12, 8))
    gs = GridSpec(2, 1, height_ratios=[1, 1], hspace=0.3)

    # Top panel: Phase timing bar chart
    ax1 = fig.add_subplot(gs[0])
    phase_names = [f"Phase {p.phase_id}: {p.phase_name}" for p in profile.phases]
    durations = [p.duration for p in profile.phases]
    colors = ["green" if p.success else "red" for p in profile.phases]

    y_pos = np.arange(len(phase_names))
    bars = ax1.barh(y_pos, durations, color=colors, alpha=0.7)

    # Add duration labels
    for i, (bar, duration) in enumerate(zip(bars, durations)):
        width = bar.get_width()
        ax1.text(width, bar.get_y() + bar.get_height() / 2, f"  {duration:.2f}s", va="center", fontsize=9)

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(phase_names)
    ax1.set_xlabel("Duration (seconds)", fontsize=11)
    ax1.set_title("Phase Timing", fontsize=12, fontweight="bold")
    ax1.grid(True, axis="x", alpha=0.3)

    # Bottom panel: Phase timeline (Gantt chart)
    ax2 = fig.add_subplot(gs[1])

    # Normalize times relative to first phase start
    base_time = profile.phases[0].start_time

    for i, phase in enumerate(profile.phases):
        start = phase.start_time - base_time
        duration = phase.duration
        color = "green" if phase.success else "red"

        # Draw phase bar
        ax2.barh(i, duration, left=start, height=0.6, color=color, alpha=0.7, edgecolor="black")

        # Add phase label
        ax2.text(
            start + duration / 2,
            i,
            f"{phase.phase_name}\n{duration:.2f}s",
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
        )

    ax2.set_yticks(range(len(profile.phases)))
    ax2.set_yticklabels([f"Phase {p.phase_id}" for p in profile.phases])
    ax2.set_xlabel("Time (seconds since start)", fontsize=11)
    ax2.set_title("Phase Timeline", fontsize=12, fontweight="bold")
    ax2.grid(True, axis="x", alpha=0.3)
    ax2.set_xlim(0, profile.total_duration)

    # Overall title
    fig.suptitle(
        f"Pipeline Execution: {profile.subject_id} / {profile.session_id}\n" f"Total: {profile.total_duration:.2f}s",
        fontsize=13,
        fontweight="bold",
    )

    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    return save_path


def plot_synchronization_stats(alignment_stats: Optional[Dict[str, Any]], save_path: Path) -> Optional[Path]:
    """Plot synchronization quality statistics in a 4-panel figure.

    Creates a figure with:
    - Panel 1 (top-left): Trial offset histogram showing distribution
    - Panel 2 (top-right): Trial offset over trial number (drift/trends)
    - Panel 3 (bottom-left): Jitter statistics summary (text box)
    - Panel 4 (bottom-right): TTL channel pulse counts (bar chart)

    Args:
        alignment_stats: Alignment statistics from synchronization phase
            Expected structure:
            {
                "trial_offsets": {trial_num: offset_seconds, ...},
                "ttl_channels": {channel_name: pulse_count, ...},
                "statistics": {
                    "n_trials_aligned": int,
                    "mean_offset_s": float,
                    "std_offset_s": float,
                    "min_offset_s": float,
                    "max_offset_s": float,
                    "p95_jitter_s": float (optional),
                    "max_jitter_s": float (optional)
                }
            }
        save_path: Path where plot should be saved

    Returns:
        Path to saved plot, or None if matplotlib unavailable or no data
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None or GridSpec is None:
        logger.info("plot_synchronization_stats: matplotlib or GridSpec not available")
        return None

    if alignment_stats is None:
        logger.info("plot_synchronization_stats: alignment_stats is None")
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract data
    trial_offsets = alignment_stats.get("trial_offsets", {})
    ttl_channels = alignment_stats.get("ttl_channels", {})
    statistics = alignment_stats.get("statistics", {})

    if not trial_offsets and not ttl_channels and not statistics:
        logger.info(f"plot_synchronization_stats: all data fields empty (trial_offsets={len(trial_offsets)}, ttl_channels={len(ttl_channels)}, statistics={bool(statistics)})")
        return None

    # Create figure with 4 panels
    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 2, hspace=0.3, wspace=0.3)

    # Panel 1 (top-left): Trial offset histogram
    ax1 = fig.add_subplot(gs[0, 0])
    if trial_offsets:
        offsets = list(trial_offsets.values())
        ax1.hist(offsets, bins=30, color="steelblue", alpha=0.7, edgecolor="black")
        ax1.set_xlabel("Offset (seconds)", fontsize=10)
        ax1.set_ylabel("Frequency", fontsize=10)
        ax1.set_title("Trial Offset Distribution", fontsize=11, fontweight="bold")
        ax1.grid(True, alpha=0.3)
        ax1.axvline(np.mean(offsets), color="red", linestyle="--", linewidth=2, label=f"Mean: {np.mean(offsets):.4f}s")
        ax1.legend()
    else:
        ax1.text(0.5, 0.5, "No trial offset data", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Trial Offset Distribution", fontsize=11, fontweight="bold")

    # Panel 2 (top-right): Trial offset over trial number
    ax2 = fig.add_subplot(gs[0, 1])
    if trial_offsets:
        trial_numbers = sorted(trial_offsets.keys())
        offsets = [trial_offsets[tn] for tn in trial_numbers]
        ax2.scatter(trial_numbers, offsets, color="steelblue", alpha=0.6, s=50)
        ax2.plot(trial_numbers, offsets, color="steelblue", alpha=0.3, linewidth=1)
        ax2.set_xlabel("Trial Number", fontsize=10)
        ax2.set_ylabel("Offset (seconds)", fontsize=10)
        ax2.set_title("Trial Offset over Time", fontsize=11, fontweight="bold")
        ax2.grid(True, alpha=0.3)

        # Add trend line if enough data points
        if len(trial_numbers) > 2:
            z = np.polyfit(trial_numbers, offsets, 1)
            p = np.poly1d(z)
            ax2.plot(trial_numbers, p(trial_numbers), "r--", linewidth=2, label=f"Trend: {z[0]:.2e}s/trial")
            ax2.legend()
    else:
        ax2.text(0.5, 0.5, "No trial offset data", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("Trial Offset over Time", fontsize=11, fontweight="bold")

    # Panel 3 (bottom-left): Jitter statistics summary
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.axis("off")
    if statistics:
        stats_text = "Synchronization Statistics\n" + "=" * 30 + "\n\n"
        stats_text += f"Trials aligned:     {statistics.get('n_trials_aligned', 'N/A')}\n"
        stats_text += f"Mean offset:        {statistics.get('mean_offset_s', 0):.4f} s\n"
        stats_text += f"Std offset:         {statistics.get('std_offset_s', 0):.4f} s\n"
        stats_text += f"Min offset:         {statistics.get('min_offset_s', 0):.4f} s\n"
        stats_text += f"Max offset:         {statistics.get('max_offset_s', 0):.4f} s\n"

        # Optional jitter metrics
        if "p95_jitter_s" in statistics:
            stats_text += f"P95 jitter:         {statistics['p95_jitter_s']:.4f} s\n"
        if "max_jitter_s" in statistics:
            stats_text += f"Max jitter:         {statistics['max_jitter_s']:.4f} s\n"
    else:
        stats_text = "No synchronization statistics available"

    ax3.text(
        0.5,
        0.5,
        stats_text,
        transform=ax3.transAxes,
        fontsize=10,
        verticalalignment="center",
        horizontalalignment="center",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5, pad=1),
    )

    # Panel 4 (bottom-right): TTL channel pulse counts
    ax4 = fig.add_subplot(gs[1, 1])
    if ttl_channels:
        channels = list(ttl_channels.keys())
        counts = list(ttl_channels.values())

        bars = ax4.bar(range(len(channels)), counts, color="steelblue", alpha=0.7, edgecolor="black")
        ax4.set_xticks(range(len(channels)))
        ax4.set_xticklabels(channels, rotation=45, ha="right")
        ax4.set_xlabel("TTL Channel", fontsize=10)
        ax4.set_ylabel("Pulse Count", fontsize=10)
        ax4.set_title("TTL Channel Pulse Counts", fontsize=11, fontweight="bold")
        ax4.grid(True, axis="y", alpha=0.3)

        # Add count labels on bars
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width() / 2, height, f"{count}", ha="center", va="bottom", fontsize=9)
    else:
        ax4.text(0.5, 0.5, "No TTL channel data", ha="center", va="center", transform=ax4.transAxes)
        ax4.set_title("TTL Channel Pulse Counts", fontsize=11, fontweight="bold")

    # Overall title
    fig.suptitle("Synchronization Quality Metrics", fontsize=14, fontweight="bold")

    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    return save_path


def plot_ttl_inter_pulse_intervals(
    ttl_pulses: Dict[str, List[float]],
    expected_fps: Optional[Dict[str, float]],
    save_path: Path,
) -> Optional[Path]:
    """Plot inter-pulse interval (IPI) analysis to detect lost TTL pulses.

    Creates a three-panel figure for each TTL channel:
    - Panel A: IPI histogram showing interval distribution and outliers
    - Panel B: IPI over time showing when pulse loss occurs
    - Panel C: Cumulative missing pulse count

    Args:
        ttl_pulses: Dictionary mapping channel names to pulse timestamps
        expected_fps: Optional dictionary mapping channel names to expected sampling rate
            If None, attempts to infer from median IPI
        save_path: Path where plot should be saved

    Returns:
        Path to saved plot, or None if matplotlib unavailable or no data

    Example:
        >>> ttl_pulses = {"ttl_camera": [0.0, 0.0067, 0.0133, ...]}
        >>> expected_fps = {"ttl_camera": 150.0}
        >>> plot_ttl_inter_pulse_intervals(ttl_pulses, expected_fps, Path("ipi.png"))
    """
    if plt is None or GridSpec is None:
        return None

    if not ttl_pulses:
        return None

    # Filter channels with enough data
    valid_channels = {k: v for k, v in ttl_pulses.items() if len(v) > 10}
    if not valid_channels:
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Create figure with 3 rows per channel
    n_channels = len(valid_channels)
    fig = plt.figure(figsize=(14, 4 * n_channels))
    gs = GridSpec(n_channels, 3, hspace=0.4, wspace=0.3)

    for row_idx, (channel_name, pulses) in enumerate(sorted(valid_channels.items())):
        pulses_array = np.array(sorted(pulses))

        # Compute inter-pulse intervals
        ipis = np.diff(pulses_array)

        # Determine expected interval
        if expected_fps and channel_name in expected_fps:
            expected_interval = 1.0 / expected_fps[channel_name]
        else:
            # Infer from median IPI
            expected_interval = np.median(ipis)

        # Detect outliers (gaps > 1.5x expected = likely missing pulse)
        outlier_threshold = expected_interval * 1.5
        outliers_mask = ipis > outlier_threshold
        n_outliers = np.sum(outliers_mask)

        # Estimate missing pulses from gap sizes
        missing_pulses = []
        for ipi in ipis[outliers_mask]:
            # How many pulses should fit in this gap?
            n_missing = int(np.round(ipi / expected_interval)) - 1
            missing_pulses.append(max(0, n_missing))
        total_missing = sum(missing_pulses)

        # Panel A: IPI Histogram (log-log scale)
        ax_hist = fig.add_subplot(gs[row_idx, 0])

        # Use log bins for histogram
        ipi_min = max(ipis.min() * 1000, 0.1)  # Avoid zero/negative
        ipi_max = ipis.max() * 1000
        log_bins = np.logspace(np.log10(ipi_min), np.log10(ipi_max), 40)

        # Plot normal IPIs
        normal_ipis = ipis[~outliers_mask]
        if len(normal_ipis) > 0:
            ax_hist.hist(normal_ipis * 1000, bins=log_bins, color="steelblue", alpha=0.7, edgecolor="black", label=f"Normal ({len(normal_ipis)})")

        # Plot outlier IPIs in red
        outlier_ipis = ipis[outliers_mask]
        if len(outlier_ipis) > 0:
            ax_hist.hist(outlier_ipis * 1000, bins=log_bins, color="red", alpha=0.7, edgecolor="black", label=f"Gaps ({len(outlier_ipis)})")

        ax_hist.axvline(expected_interval * 1000, color="green", linestyle="--", linewidth=2, label=f"Expected: {expected_interval*1000:.1f}ms")
        ax_hist.axvline(outlier_threshold * 1000, color="orange", linestyle=":", linewidth=2, label=f"Gap threshold: {outlier_threshold*1000:.1f}ms")

        # Set log scales
        ax_hist.set_xscale("log")
        ax_hist.set_yscale("log")

        ax_hist.set_xlabel("Inter-Pulse Interval (ms, log scale)", fontsize=10)
        ax_hist.set_ylabel("Frequency (log scale)", fontsize=10)
        ax_hist.set_title(f"{channel_name}: IPI Distribution", fontsize=11, fontweight="bold")
        ax_hist.legend(fontsize=8, loc="best")
        ax_hist.grid(True, alpha=0.3, which="both", linestyle=":")

        # Panel B: IPI over time (log y-axis)
        ax_time = fig.add_subplot(gs[row_idx, 1])

        pulse_indices = np.arange(len(ipis))
        colors = np.where(outliers_mask, "red", "steelblue")

        ax_time.scatter(pulse_indices, ipis * 1000, c=colors, alpha=0.6, s=20)
        ax_time.axhline(expected_interval * 1000, color="green", linestyle="--", linewidth=2, alpha=0.7, label=f"Expected")
        ax_time.axhline(outlier_threshold * 1000, color="orange", linestyle=":", linewidth=2, alpha=0.7, label=f"Gap threshold")

        # Set log scale on y-axis only (x is pulse index, linear makes sense)
        ax_time.set_yscale("log")

        ax_time.set_xlabel("Pulse Index", fontsize=10)
        ax_time.set_ylabel("Inter-Pulse Interval (ms, log scale)", fontsize=10)
        ax_time.set_title(f"{channel_name}: IPI Over Time", fontsize=11, fontweight="bold")
        ax_time.legend(fontsize=8, loc="best")
        ax_time.grid(True, alpha=0.3, which="both", linestyle=":")

        # Highlight regions with outliers (light background)
        for idx in np.where(outliers_mask)[0]:
            ax_time.axvspan(idx, idx + 1, alpha=0.1, color="red")

        # Panel C: Cumulative missing pulse count
        ax_cumulative = fig.add_subplot(gs[row_idx, 2])

        # Build cumulative count
        cumulative_missing = np.zeros(len(ipis))
        missing_idx = 0
        for i, is_outlier in enumerate(outliers_mask):
            if is_outlier and missing_idx < len(missing_pulses):
                cumulative_missing[i:] += missing_pulses[missing_idx]
                missing_idx += 1

        ax_cumulative.plot(pulse_indices, cumulative_missing, color="red", linewidth=2)
        ax_cumulative.fill_between(pulse_indices, 0, cumulative_missing, alpha=0.3, color="red")

        ax_cumulative.set_xlabel("Pulse Index", fontsize=10)
        ax_cumulative.set_ylabel("Cumulative Missing Pulses", fontsize=10)
        ax_cumulative.set_title(f"{channel_name}: Pulse Loss Accumulation", fontsize=11, fontweight="bold")
        ax_cumulative.grid(True, alpha=0.3)

        # Add statistics text box (removed misleading total time estimate)
        stats_text = f"Recorded pulses: {len(pulses)}\n" f"Detected gaps: {n_outliers}\n" f"Est. missing: {total_missing}\n" f"\nNote: Gaps include\nexperiment pauses"
        ax_cumulative.text(
            0.98,
            0.98,
            stats_text,
            transform=ax_cumulative.transAxes,
            fontsize=9,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    # Overall title
    fig.suptitle("TTL Inter-Pulse Interval Analysis (Pulse Loss Detection)", fontsize=14, fontweight="bold")

    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    return save_path


def plot_sync_quality_and_completeness(
    trial_offsets: Dict[int, float],
    data_streams: Optional[Dict[str, List[bool]]],
    save_path: Path,
    csv_output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Plot combined sync quality and trial completeness analysis.

    Enhanced diagnostics for TTL false positive/negative detection:
    - Panel A: Alignment offset over trials with rolling statistics bands
    - Panel A2: Offset delta (trial-to-trial changes) for spike detection
    - Panel B: Offset distribution histogram
    - Panel C: Inter-trial interval residuals
    - Panel D+: Data stream completeness (when available)

    Also generates a validation CSV file with per-trial diagnostics.

    Args:
        trial_offsets: Dictionary mapping trial number to alignment offset (seconds)
            Offset = time difference between Bpod timestamp and TTL recording
        data_streams: Optional dict of stream names to boolean availability per trial
            Example: {"Bpod": [True, True, ...], "ttl_camera": [True, False, ...]}
        save_path: Path where plot should be saved
        csv_output_dir: Optional directory for CSV file. If None, saves to same dir as plot

    Returns:
        Path to saved plot, or None if matplotlib unavailable or insufficient data

    Note:
        Detects alignment issues:
        - False negative (missed TTL): Large positive delta spike
        - False positive (extra TTL): Large negative delta spike
        - Session pause: Step change with new stable baseline
        - Good alignment: Low rolling STD, small deltas
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None or GridSpec is None:
        logger.info("plot_sync_quality_and_completeness: matplotlib or GridSpec not available")
        return None

    if not trial_offsets or len(trial_offsets) < 3:
        logger.info(f"plot_sync_quality_and_completeness: insufficient trial_offsets (count={len(trial_offsets) if trial_offsets else 0}, minimum=3)")
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare sync quality data
    trial_numbers = np.array(sorted(trial_offsets.keys()))
    offsets = np.array([trial_offsets[tn] for tn in trial_numbers])
    n_trials_aligned = len(trial_numbers)

    # Determine layout based on TOTAL trial count (not just aligned)
    has_completeness = data_streams is not None and len(data_streams) > 0
    if has_completeness:
        first_stream = list(data_streams.values())[0]
        n_trials_total = len(first_stream)
    else:
        n_trials_total = n_trials_aligned

    many_trials = n_trials_total > 100

    # Enhanced layout with offset delta and IPI residuals
    if has_completeness and many_trials:
        # 3x3 grid: sync diagnostics (left 2 cols) + completeness (right col)
        fig = plt.figure(figsize=(20, 14))
        gs = GridSpec(3, 3, hspace=0.35, wspace=0.4, height_ratios=[2, 1, 1.5])
    elif has_completeness:
        # 3x3 grid: sync diagnostics + completeness heatmap
        fig = plt.figure(figsize=(20, max(12, len(data_streams) * 0.5)))
        gs = GridSpec(3, 3, hspace=0.35, wspace=0.4, height_ratios=[2, 1, 1.5])
    else:
        # 3x2 grid: sync diagnostics only (no completeness)
        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(3, 2, hspace=0.35, wspace=0.4, height_ratios=[2, 1, 1.5])

    # ===== PANEL A: Sync offsets over trials WITH ROLLING STATS =====
    ax_sync_time = fig.add_subplot(gs[0, :2])  # Span first 2 columns

    # Calculate rolling statistics (window = 10 trials)
    window_size = min(10, max(3, len(offsets) // 10))
    offsets_series = pd.Series(offsets) if pd is not None else None

    if offsets_series is not None:
        rolling_mean = offsets_series.rolling(window=window_size, center=True, min_periods=1).mean()
        rolling_std = offsets_series.rolling(window=window_size, center=True, min_periods=1).std()
        rolling_q1 = offsets_series.rolling(window=window_size, center=True, min_periods=1).quantile(0.25)
        rolling_q3 = offsets_series.rolling(window=window_size, center=True, min_periods=1).quantile(0.75)
        rolling_iqr = rolling_q3 - rolling_q1
        rolling_lower = rolling_q1 - 1.5 * rolling_iqr
        rolling_upper = rolling_q3 + 1.5 * rolling_iqr
    else:
        # Fallback if pandas not available
        rolling_mean = np.full_like(offsets, np.mean(offsets))
        rolling_std = np.full_like(offsets, np.std(offsets))
        rolling_lower = np.full_like(offsets, np.percentile(offsets, 25) - 1.5 * (np.percentile(offsets, 75) - np.percentile(offsets, 25)))
        rolling_upper = np.full_like(offsets, np.percentile(offsets, 75) + 1.5 * (np.percentile(offsets, 75) - np.percentile(offsets, 25)))

    # Detect outliers using rolling IQR method
    outliers_mask = (offsets < rolling_lower) | (offsets > rolling_upper)

    # Global IQR for reference
    q1, q3 = np.percentile(offsets, [25, 75])
    iqr = q3 - q1
    outlier_threshold = 1.5 * iqr
    lower_bound = q1 - outlier_threshold
    upper_bound = q3 + outlier_threshold

    # Calculate reasonable y-axis limits (clip to show normal variation)
    mean_offset = np.mean(offsets)
    std_offset = np.std(offsets)
    # Use 99th percentile or mean ± 4*std, whichever is smaller (captures ~99.99% of normal data)
    p1, p99 = np.percentile(offsets, [1, 99])
    y_min_clip = max(p1 * 1000, (mean_offset - 4 * std_offset) * 1000)
    y_max_clip = min(p99 * 1000, (mean_offset + 4 * std_offset) * 1000)

    # Add some padding (10% of range)
    y_range = y_max_clip - y_min_clip
    y_padding = max(y_range * 0.1, 2.0)  # At least 2ms padding
    y_min_plot = y_min_clip - y_padding
    y_max_plot = y_max_clip + y_padding

    # Separate in-range and clipped points
    offsets_ms = offsets * 1000
    in_range_mask = (offsets_ms >= y_min_clip) & (offsets_ms <= y_max_clip)
    clipped_above = offsets_ms > y_max_clip
    clipped_below = offsets_ms < y_min_clip

    # Plot in-range offsets
    normal_in_range = in_range_mask & ~outliers_mask
    outlier_in_range = in_range_mask & outliers_mask

    if np.any(normal_in_range):
        ax_sync_time.scatter(trial_numbers[normal_in_range], offsets_ms[normal_in_range], c="steelblue", alpha=0.6, s=50, label="Normal sync")
    if np.any(outlier_in_range):
        ax_sync_time.scatter(trial_numbers[outlier_in_range], offsets_ms[outlier_in_range], c="red", alpha=0.7, s=50, label="Outliers")

    # Plot clipped outliers at boundaries with special markers
    if np.any(clipped_above):
        ax_sync_time.scatter(
            trial_numbers[clipped_above],
            np.full(np.sum(clipped_above), y_max_plot - 0.5),
            c="red",
            marker="^",
            s=100,
            alpha=0.8,
            label=f"Clipped above ({np.sum(clipped_above)} trials)",
        )
        # Annotate max value
        max_idx = np.argmax(offsets_ms)
        max_trial = trial_numbers[max_idx]
        max_val = offsets_ms[max_idx]
        ax_sync_time.annotate(
            f"Max: {max_val:.1f}ms\n(trial {max_trial})",
            xy=(max_trial, y_max_plot - 0.5),
            xytext=(10, -20),
            textcoords="offset points",
            fontsize=8,
            color="red",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
            arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
        )

    if np.any(clipped_below):
        ax_sync_time.scatter(
            trial_numbers[clipped_below],
            np.full(np.sum(clipped_below), y_min_plot + 0.5),
            c="red",
            marker="v",
            s=100,
            alpha=0.8,
            label=f"Clipped below ({np.sum(clipped_below)} trials)",
        )
        # Annotate min value
        min_idx = np.argmin(offsets_ms)
        min_trial = trial_numbers[min_idx]
        min_val = offsets_ms[min_idx]
        ax_sync_time.annotate(
            f"Min: {min_val:.1f}ms\n(trial {min_trial})",
            xy=(min_trial, y_min_plot + 0.5),
            xytext=(10, 20),
            textcoords="offset points",
            fontsize=8,
            color="red",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
            arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
        )

    # Plot line connecting all points (clipped to visible range)
    offsets_ms_clipped = np.clip(offsets_ms, y_min_plot, y_max_plot)
    ax_sync_time.plot(trial_numbers, offsets_ms_clipped, alpha=0.3, linewidth=1, color="steelblue", zorder=1)

    # Add rolling mean and confidence bands
    rolling_mean_ms = rolling_mean.values * 1000 if hasattr(rolling_mean, "values") else rolling_mean * 1000
    rolling_lower_ms = rolling_lower.values * 1000 if hasattr(rolling_lower, "values") else rolling_lower * 1000
    rolling_upper_ms = rolling_upper.values * 1000 if hasattr(rolling_upper, "values") else rolling_upper * 1000

    rolling_mean_clipped = np.clip(rolling_mean_ms, y_min_plot, y_max_plot)
    rolling_lower_clipped = np.clip(rolling_lower_ms, y_min_plot, y_max_plot)
    rolling_upper_clipped = np.clip(rolling_upper_ms, y_min_plot, y_max_plot)

    ax_sync_time.plot(trial_numbers, rolling_mean_clipped, "b-", linewidth=2, label=f"Rolling mean (window={window_size})", zorder=2)
    ax_sync_time.fill_between(trial_numbers, rolling_lower_clipped, rolling_upper_clipped, alpha=0.2, color="blue", label="Rolling IQR ±1.5", zorder=0)

    # Add global trend line (use all data for calculation, clip for display)
    if len(trial_numbers) > 2:
        z = np.polyfit(trial_numbers, offsets_ms, 1)
        p = np.poly1d(z)
        trend_vals = p(trial_numbers)
        trend_vals_clipped = np.clip(trend_vals, y_min_plot, y_max_plot)
        ax_sync_time.plot(trial_numbers, trend_vals_clipped, "g--", linewidth=2, label=f"Global drift: {z[0]:.3f} ms/trial", zorder=2)

    # Add reference lines
    ax_sync_time.axhline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.7, label="Perfect sync")
    if y_min_plot <= lower_bound * 1000 <= y_max_plot:
        ax_sync_time.axhline(lower_bound * 1000, color="orange", linestyle=":", linewidth=2, alpha=0.7, label=f"Outlier threshold")
    if y_min_plot <= upper_bound * 1000 <= y_max_plot:
        ax_sync_time.axhline(upper_bound * 1000, color="orange", linestyle=":", linewidth=2, alpha=0.7)

    # Set clipped y-limits
    ax_sync_time.set_ylim(y_min_plot, y_max_plot)

    ax_sync_time.set_xlabel("Trial Number", fontsize=11)
    ax_sync_time.set_ylabel("Alignment Offset (ms)\n← TTL early | TTL late →", fontsize=11)
    ax_sync_time.set_title("Bpod-TTL Alignment Over Time with Rolling Statistics\n(Y-axis clipped, blue band = local IQR tolerance)", fontsize=12, fontweight="bold")
    ax_sync_time.legend(loc="best", fontsize=8, ncol=2)
    ax_sync_time.grid(True, alpha=0.3)

    # Highlight outlier regions (only for visible outliers)
    for trial_idx in np.where(outlier_in_range)[0]:
        ax_sync_time.axvspan(trial_numbers[trial_idx] - 0.5, trial_numbers[trial_idx] + 0.5, alpha=0.1, color="red")

    # ===== PANEL A2: Offset Delta (Trial-to-Trial Changes) =====
    ax_delta = fig.add_subplot(gs[1, :2])  # Below Panel A, span 2 columns

    if len(offsets) > 1:
        offset_deltas = np.diff(offsets) * 1000  # Convert to ms
        delta_trial_numbers = trial_numbers[1:]  # Deltas are between trials

        # Calculate delta statistics for coloring
        delta_std = np.std(offset_deltas)
        delta_threshold_1 = 3 * delta_std  # Yellow threshold
        delta_threshold_2 = 5 * delta_std  # Red threshold

        # Color code bars based on magnitude
        colors = ["green" if abs(d) < delta_threshold_1 else "orange" if abs(d) < delta_threshold_2 else "red" for d in offset_deltas]

        ax_delta.bar(delta_trial_numbers, offset_deltas, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)
        ax_delta.axhline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.5)
        ax_delta.axhline(delta_threshold_1, color="orange", linestyle=":", linewidth=1.5, alpha=0.7, label=f"±3σ = ±{delta_threshold_1:.1f}ms")
        ax_delta.axhline(-delta_threshold_1, color="orange", linestyle=":", linewidth=1.5, alpha=0.7)
        ax_delta.axhline(delta_threshold_2, color="red", linestyle=":", linewidth=1.5, alpha=0.7, label=f"±5σ = ±{delta_threshold_2:.1f}ms")
        ax_delta.axhline(-delta_threshold_2, color="red", linestyle=":", linewidth=1.5, alpha=0.7)

        # Detect and annotate patterns
        for i, (trial_num, delta) in enumerate(zip(delta_trial_numbers, offset_deltas)):
            if abs(delta) > delta_threshold_2:
                # Check pattern: spike or step change
                if i < len(offset_deltas) - 1:
                    next_delta = offset_deltas[i + 1]
                    if delta > 0 and next_delta < -delta_threshold_1:  # Up then down
                        label = "⚠ False Positive?"
                        color = "red"
                    elif delta < 0 and next_delta > delta_threshold_1:  # Down then up
                        label = "⚠ Missed TTL?"
                        color = "red"
                    elif abs(next_delta) < delta_threshold_1:  # Step, then stable
                        label = "ℹ Pause/Resume"
                        color = "blue"
                    else:
                        label = "⚠ Check trial"
                        color = "purple"
                else:
                    label = "⚠ Check trial"
                    color = "purple"

                ax_delta.annotate(
                    label,
                    xy=(trial_num, delta),
                    xytext=(0, 10 if delta > 0 else -15),
                    textcoords="offset points",
                    fontsize=7,
                    color=color,
                    fontweight="bold",
                    ha="center",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
                )

        ax_delta.set_xlabel("Trial Number", fontsize=10)
        ax_delta.set_ylabel("Offset Change (ms)\n← Earlier | Later →", fontsize=10)
        ax_delta.set_title("Trial-to-Trial Offset Changes (Δ)\n(Detects false positives/negatives)", fontsize=11, fontweight="bold")
        ax_delta.legend(loc="best", fontsize=8)
        ax_delta.grid(True, alpha=0.3, axis="y")

    # ===== PANEL B: Offset distribution =====
    ax_sync_hist = fig.add_subplot(gs[0, 2])  # Top right

    # Plot histogram
    normal_offsets = offsets[~outliers_mask] * 1000
    outlier_offsets = offsets[outliers_mask] * 1000

    if len(normal_offsets) > 0:
        ax_sync_hist.hist(normal_offsets, bins=30, color="steelblue", alpha=0.7, edgecolor="black", label=f"Normal ({len(normal_offsets)} trials)")

    if len(outlier_offsets) > 0:
        ax_sync_hist.hist(outlier_offsets, bins=10, color="red", alpha=0.7, edgecolor="black", label=f"Outliers ({len(outlier_offsets)} trials)")

    # Add statistics lines
    mean_offset = np.mean(offsets) * 1000
    std_offset = np.std(offsets) * 1000
    ax_sync_hist.axvline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.5, label="Perfect sync")
    ax_sync_hist.axvline(mean_offset, color="green", linestyle="--", linewidth=2, label=f"Mean: {mean_offset:.2f} ms")
    ax_sync_hist.axvline(mean_offset - std_offset, color="orange", linestyle=":", linewidth=2, alpha=0.7)
    ax_sync_hist.axvline(mean_offset + std_offset, color="orange", linestyle=":", linewidth=2, alpha=0.7, label=f"±1 SD: {std_offset:.2f} ms")

    ax_sync_hist.set_xlabel("Alignment Offset (ms)", fontsize=11)
    ax_sync_hist.set_ylabel("Number of Trials", fontsize=11)
    ax_sync_hist.set_title("Offset Distribution\n(Narrow peak = consistent sync)", fontsize=12, fontweight="bold")
    ax_sync_hist.legend(fontsize=9, loc="best")
    ax_sync_hist.grid(True, alpha=0.3)

    # Add sync quality assessment
    sync_quality = "Excellent" if std_offset < 1.0 else "Good" if std_offset < 5.0 else "Fair" if std_offset < 10.0 else "Poor"
    stats_text = (
        f"Sync Quality: {sync_quality}\n"
        f"\n"
        f"Trials: {len(trial_numbers)}\n"
        f"Mean offset: {mean_offset:.3f} ms\n"
        f"Std dev: {std_offset:.3f} ms\n"
        f"Range: [{offsets.min()*1000:.1f}, {offsets.max()*1000:.1f}] ms\n"
        f"Outliers: {np.sum(outliers_mask)} ({100*np.sum(outliers_mask)/len(offsets):.1f}%)"
    )
    ax_sync_hist.text(
        0.98,
        0.98,
        stats_text,
        transform=ax_sync_hist.transAxes,
        fontsize=9,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.8),
    )

    # ===== PANEL C: Inter-Trial Interval Residuals =====
    ax_iti = fig.add_subplot(gs[1, 2])  # Middle right

    # Use offset deltas as proxy for timing mismatches
    if len(offsets) > 1:
        # Plot absolute residuals (reusing delta data)
        abs_deltas = np.abs(offset_deltas)
        residual_colors = ["green" if d < delta_threshold_1 else "orange" if d < delta_threshold_2 else "red" for d in abs_deltas]

        ax_iti.scatter(delta_trial_numbers, abs_deltas, c=residual_colors, alpha=0.7, s=30)
        ax_iti.axhline(delta_threshold_1, color="orange", linestyle=":", linewidth=1.5, alpha=0.7, label=f"3σ = {delta_threshold_1:.1f}ms")
        ax_iti.axhline(delta_threshold_2, color="red", linestyle=":", linewidth=1.5, alpha=0.7, label=f"5σ = {delta_threshold_2:.1f}ms")

        ax_iti.set_xlabel("Trial Number", fontsize=10)
        ax_iti.set_ylabel("|Offset Change| (ms)", fontsize=10)
        ax_iti.set_title("Offset Change Magnitude\n(Proxy for timing mismatches)", fontsize=11, fontweight="bold")
        ax_iti.legend(loc="best", fontsize=8)
        ax_iti.grid(True, alpha=0.3)
        ax_iti.set_yscale("log")
    else:
        ax_iti.text(0.5, 0.5, "Insufficient data\nfor ITI analysis", ha="center", va="center", fontsize=10, transform=ax_iti.transAxes)

    # ===== PANELS D+: Trial completeness (if data available) =====
    if has_completeness:
        stream_names = list(data_streams.keys())
        n_streams = len(stream_names)

        # Get the actual trial numbers from the data_streams
        # (data_streams arrays should all have the same length)
        first_stream = list(data_streams.values())[0]
        n_trials_completeness = len(first_stream)

        # Generate trial numbers for completeness (should match data_streams length)
        # Assuming trials are numbered 1 to n
        completeness_trial_numbers = list(range(1, n_trials_completeness + 1))

        # Build data matrix
        data_matrix = np.zeros((n_streams, n_trials_completeness))
        for i, stream_name in enumerate(stream_names):
            availability = data_streams[stream_name]
            if len(availability) != n_trials_completeness:
                # Warn if mismatch
                logger.warning(f"Stream {stream_name} has {len(availability)} values, expected {n_trials_completeness}")
                availability = availability[:n_trials_completeness] + [False] * max(0, n_trials_completeness - len(availability))
            data_matrix[i, :] = [1.0 if avail else 0.0 for avail in availability]

        if n_trials_completeness > 100:
            # Summary view for many trials
            _add_completeness_summary(fig, gs, stream_names, data_matrix, completeness_trial_numbers)
        else:
            # Detailed heatmap for few trials
            _add_completeness_heatmap(fig, gs, stream_names, data_matrix, completeness_trial_numbers)

    # Overall title
    title = "Synchronization Quality & Trial Completeness" if has_completeness else "Synchronization Quality"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    # Generate validation CSV with per-trial diagnostics
    csv_dir = csv_output_dir if csv_output_dir is not None else save_path.parent
    csv_path = csv_dir / f"{save_path.stem}_validation.csv"
    try:
        with open(csv_path, "w") as f:
            # Write header
            f.write("trial_number,offset_ms,delta_ms,z_score_global,z_score_rolling,outlier,status,notes\n")

            # Write data for each trial
            for idx, trial_num in enumerate(trial_numbers):
                offset_ms_val = offsets[idx] * 1000

                # Delta (if available)
                if idx < len(offset_deltas):
                    delta_val = offset_deltas[idx]
                else:
                    delta_val = 0.0

                # Global z-score
                z_global = (offsets[idx] - mean_offset) / std_offset if std_offset > 0 else 0.0

                # Rolling z-score (using rolling std)
                if offsets_series is not None and hasattr(rolling_std, "values"):
                    roll_mean_val = rolling_mean.values[idx] if hasattr(rolling_mean, "values") else rolling_mean[idx]
                    roll_std_val = rolling_std.values[idx] if hasattr(rolling_std, "values") else rolling_std[idx]
                    z_rolling = (offsets[idx] - roll_mean_val) / roll_std_val if roll_std_val > 0 else 0.0
                else:
                    z_rolling = z_global

                # Outlier status
                is_outlier = outliers_mask[idx]

                # Status and notes
                if is_outlier:
                    status = "SUSPECT"
                    if idx < len(offset_deltas):
                        if abs(delta_val) > delta_threshold_2:
                            if idx < len(offset_deltas) - 1:
                                next_d = offset_deltas[idx + 1]
                                if delta_val > 0 and next_d < -delta_threshold_1:
                                    notes = "Possible false positive TTL"
                                elif delta_val < 0 and next_d > delta_threshold_1:
                                    notes = "Possible missed TTL"
                                elif abs(next_d) < delta_threshold_1:
                                    notes = "Session pause/resume"
                                else:
                                    notes = "Large offset change"
                            else:
                                notes = "Large offset change (end of session)"
                        else:
                            notes = "Outside rolling IQR tolerance"
                    else:
                        notes = "Outside rolling IQR tolerance"
                else:
                    status = "OK"
                    notes = ""

                # Write row
                f.write(f'{trial_num},{offset_ms_val:.3f},{delta_val:.3f},{z_global:.3f},{z_rolling:.3f},{is_outlier},{status},"{notes}"\n')

        logger.info(f"Trial validation CSV saved to: {csv_path}")
    except Exception as e:
        logger.warning(f"Failed to save validation CSV: {e}")

    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    return save_path


def _add_completeness_summary(fig, gs, stream_names, data_matrix, trial_numbers):
    """Add completeness summary panels (for many trials)."""
    n_streams, n_trials = data_matrix.shape

    # Calculate completeness percentages
    completeness_per_stream = np.mean(data_matrix, axis=1) * 100

    # Panel D: Completeness bars (bottom left)
    ax_complete_bars = fig.add_subplot(gs[2, 0])

    y_pos = np.arange(n_streams)
    colors = plt.cm.RdYlGn(completeness_per_stream / 100)
    bars = ax_complete_bars.barh(y_pos, completeness_per_stream, color=colors, edgecolor="black", linewidth=1)

    # Add percentage labels
    for i, (bar, pct) in enumerate(zip(bars, completeness_per_stream)):
        ax_complete_bars.text(pct + 1, i, f"{pct:.1f}%", va="center", fontsize=9, fontweight="bold")

    ax_complete_bars.set_yticks(y_pos)
    ax_complete_bars.set_yticklabels(stream_names, fontsize=10)
    ax_complete_bars.set_xlabel("Completeness (%)", fontsize=11)
    ax_complete_bars.set_title(f"Data Stream Completeness\n({n_trials} trials)", fontsize=12, fontweight="bold")
    ax_complete_bars.set_xlim(0, 105)
    ax_complete_bars.axvline(100, color="green", linestyle="--", linewidth=2, alpha=0.5)
    ax_complete_bars.grid(True, axis="x", alpha=0.3)

    # Panel E: Missing data timeline (bottom middle+right, span 2 columns)
    ax_complete_timeline = fig.add_subplot(gs[2, 1:])

    for i, stream_name in enumerate(stream_names):
        missing_indices = np.where(data_matrix[i, :] == 0)[0]
        if len(missing_indices) > 0:
            missing_trials = [trial_numbers[idx] for idx in missing_indices]
            ax_complete_timeline.scatter(missing_trials, [i] * len(missing_trials), color="red", s=60, alpha=0.7, marker="|", linewidths=2)

    ax_complete_timeline.set_yticks(range(n_streams))
    ax_complete_timeline.set_yticklabels(stream_names, fontsize=10)
    ax_complete_timeline.set_xlabel("Trial Number", fontsize=11)
    ax_complete_timeline.set_title("Missing Data Timeline\n(Red marks = missing)", fontsize=12, fontweight="bold")
    ax_complete_timeline.set_xlim(trial_numbers[0] - 10, trial_numbers[-1] + 10)
    ax_complete_timeline.grid(True, alpha=0.3)


def _add_completeness_heatmap(fig, gs, stream_names, data_matrix, trial_numbers):
    """Add completeness heatmap panel (for few trials)."""
    n_streams, n_trials = data_matrix.shape

    # Span bottom row (row 2, all columns)
    ax_heatmap = fig.add_subplot(gs[2, :])

    # Create heatmap
    cmap = plt.cm.colors.ListedColormap(["#ff6b6b", "#51cf66"])  # Red=missing, Green=present
    im = ax_heatmap.imshow(data_matrix, cmap=cmap, aspect="auto", interpolation="nearest")

    # Add checkmarks for complete data
    for i in range(n_streams):
        for j in range(n_trials):
            if data_matrix[i, j] == 1.0:
                ax_heatmap.text(j, i, "✓", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    # Configure axes
    ax_heatmap.set_xticks(np.arange(n_trials))
    ax_heatmap.set_xticklabels(trial_numbers, fontsize=8, rotation=90)
    ax_heatmap.set_yticks(np.arange(n_streams))
    ax_heatmap.set_yticklabels(stream_names, fontsize=10)
    ax_heatmap.set_xlabel("Trial Number", fontsize=11)
    ax_heatmap.set_title(f"Trial Completeness Heatmap\n(Green ✓ = complete, Red = missing)", fontsize=12, fontweight="bold")

    # Add grid
    ax_heatmap.set_xticks(np.arange(n_trials + 1) - 0.5, minor=True)
    ax_heatmap.set_yticks(np.arange(n_streams + 1) - 0.5, minor=True)
    ax_heatmap.grid(which="minor", color="gray", linestyle="-", linewidth=0.5, alpha=0.3)


# Keep old function name for backward compatibility (deprecated)
def plot_bpod_ttl_sync_residuals(
    trial_offsets: Dict[int, float],
    bpod_sync_times: Optional[Dict[int, float]],
    ttl_sync_times: Optional[Dict[int, float]],
    save_path: Path,
) -> Optional[Path]:
    """Deprecated: Use plot_sync_quality_and_completeness instead."""
    return plot_sync_quality_and_completeness(trial_offsets, None, save_path)


def plot_trial_completeness(
    trial_numbers: List[int],
    data_streams: Dict[str, List[bool]],
    save_path: Path,
) -> Optional[Path]:
    """Deprecated: Use plot_sync_quality_and_completeness instead.

    This function creates a simple heatmap without sync quality metrics.
    For the full combined view, use plot_sync_quality_and_completeness.
    """
    if plt is None or GridSpec is None:
        return None

    if not trial_numbers or not data_streams:
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Create dummy offsets (all zeros) to use the new combined function
    # This allows old code to continue working
    trial_offsets = {tn: 0.0 for tn in trial_numbers}

    return plot_sync_quality_and_completeness(trial_offsets, data_streams, save_path)
