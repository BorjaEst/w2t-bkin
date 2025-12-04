"""Pipeline profiling and diagnostic figures.

This module generates diagnostic plots and profiling information for
pipeline execution to help understand performance and validate results.

Key figures generated:
- pipeline_execution.png: Combined timing and timeline visualization
- synchronization_stats.png: Jitter, offset, and alignment quality metrics
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
except ImportError:
    plt = None
    GridSpec = None


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
        f"Pipeline Execution: {profile.subject_id} / {profile.session_id}\n"
        f"Total: {profile.total_duration:.2f}s",
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
    if plt is None or GridSpec is None:
        return None

    if alignment_stats is None:
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract data
    trial_offsets = alignment_stats.get("trial_offsets", {})
    ttl_channels = alignment_stats.get("ttl_channels", {})
    statistics = alignment_stats.get("statistics", {})

    if not trial_offsets and not ttl_channels and not statistics:
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
