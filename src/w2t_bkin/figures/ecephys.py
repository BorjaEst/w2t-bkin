"""Plotting helpers for electrophysiology data analysis.

These functions are intentionally lightweight, with graceful fallbacks
if matplotlib is not installed (the example remains runnable without plots).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:  # Optional dependency for examples
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - optional
    plt = None  # type: ignore


def _ensure_parent(path: Path) -> Path:
    """Ensure parent directory exists for the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def plot_electrode_locations(
    electrodes_df: pd.DataFrame,
    *,
    out_path: Path,
) -> Optional[Path]:
    """Plot 2D electrode locations from electrodes table.

    Visualizes the spatial layout of recording electrodes using x/y coordinates.
    Points are colored by channel index to show probe geometry.

    Args:
        electrodes_df: DataFrame from nwbfile.electrodes.to_dataframe()
                       Expected columns: x, y, (optionally: z, location, group)
        out_path: Path where plot should be saved

    Returns:
        Path to saved plot, or None if matplotlib is unavailable
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_electrode_locations: matplotlib not available")
        return None

    _ensure_parent(out_path)

    # Extract coordinates
    x = electrodes_df["x"].values
    y = electrodes_df["y"].values
    n_channels = len(electrodes_df)

    # Create figure
    fig, ax = plt.subplots(figsize=(6, 10))

    # Scatter plot with color gradient
    scatter = ax.scatter(
        x,
        y,
        c=np.arange(n_channels),
        cmap="viridis",
        s=50,
        alpha=0.7,
        edgecolors="k",
        linewidth=0.5,
    )

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, label="Channel Index")
    cbar.ax.tick_params(labelsize=9)

    # Formatting
    ax.set_xlabel("X position (μm)", fontsize=11)
    ax.set_ylabel("Y position (μm)", fontsize=11)
    ax.set_title(f"Electrode Locations (n={n_channels})", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3, linestyle=":")
    ax.set_aspect("equal", adjustable="box")

    # Add statistics text
    x_range = x.max() - x.min()
    y_range = y.max() - y.min()
    stats_text = f"X range: {x_range:.0f} μm\nY range: {y_range:.0f} μm"
    ax.text(
        0.02,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_spike_raster(
    units_df: pd.DataFrame,
    *,
    out_path: Path,
    time_range: Optional[tuple[float, float]] = None,
    max_units: int = 20,
) -> Optional[Path]:
    """Plot spike raster for sorted units.

    Displays spike times as vertical ticks for each unit. Useful for
    visualizing temporal firing patterns and population activity.

    Args:
        units_df: DataFrame from nwbfile.units.to_dataframe()
                  Expected column: spike_times (list/array of timestamps)
        out_path: Path where plot should be saved
        time_range: Optional (start, end) in seconds to zoom into specific window
        max_units: Maximum number of units to display (default: 20)

    Returns:
        Path to saved plot, or None if matplotlib is unavailable
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_spike_raster: matplotlib not available")
        return None

    _ensure_parent(out_path)

    # Limit number of units
    n_units = min(len(units_df), max_units)
    units_to_plot = units_df.iloc[:n_units]

    # Determine time range
    if time_range is None:
        all_spike_times = np.concatenate([row["spike_times"] for _, row in units_to_plot.iterrows()])
        time_range = (0, all_spike_times.max()) if len(all_spike_times) > 0 else (0, 1)

    # Create figure
    fig, ax = plt.subplots(figsize=(12, max(4, n_units * 0.3)))

    # Plot each unit's spikes
    for unit_idx, (idx, row) in enumerate(units_to_plot.iterrows()):
        spike_times = row["spike_times"]
        # Filter to time range
        mask = (spike_times >= time_range[0]) & (spike_times <= time_range[1])
        filtered_spikes = spike_times[mask]

        # Plot vertical lines
        ax.vlines(
            filtered_spikes,
            unit_idx + 0.5,
            unit_idx + 1.5,
            colors="black",
            alpha=0.6,
            linewidth=0.8,
        )

    # Formatting
    ax.set_xlim(time_range)
    ax.set_ylim(0.5, n_units + 0.5)
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Unit ID", fontsize=11)
    ax.set_title(f"Spike Raster (n={n_units} units)", fontsize=13, fontweight="bold")
    ax.set_yticks(np.arange(1, n_units + 1))
    ax.set_yticklabels([str(idx) for idx, _ in units_to_plot.iterrows()])
    ax.grid(True, axis="x", alpha=0.3, linestyle=":")

    # Add statistics
    total_spikes = sum(len(row["spike_times"]) for _, row in units_to_plot.iterrows())
    duration = time_range[1] - time_range[0]
    mean_rate = total_spikes / duration / n_units if duration > 0 else 0
    stats_text = f"Time: {time_range[0]:.1f}-{time_range[1]:.1f}s\n"
    stats_text += f"Total spikes: {total_spikes:,}\n"
    stats_text += f"Mean rate: {mean_rate:.2f} Hz"
    ax.text(
        0.98,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_firing_rate_distribution(
    units_df: pd.DataFrame,
    *,
    out_path: Path,
    recording_duration: float,
) -> Optional[Path]:
    """Plot histogram of firing rates across all units.

    Shows the distribution of mean firing rates, which is useful for
    assessing unit quality and population statistics.

    Args:
        units_df: DataFrame from nwbfile.units.to_dataframe()
                  Expected column: spike_times (list/array of timestamps)
        out_path: Path where plot should be saved
        recording_duration: Duration of recording in seconds (for rate calculation)

    Returns:
        Path to saved plot, or None if matplotlib is unavailable
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_firing_rate_distribution: matplotlib not available")
        return None

    _ensure_parent(out_path)

    # Calculate firing rates
    firing_rates = np.array([len(row["spike_times"]) / recording_duration for _, row in units_df.iterrows()])

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 5))

    # Histogram
    ax.hist(firing_rates, bins=30, color="steelblue", alpha=0.7, edgecolor="black", linewidth=0.5)

    # Add median line
    median_rate = np.median(firing_rates)
    ax.axvline(median_rate, color="red", linestyle="--", linewidth=2, label=f"Median: {median_rate:.2f} Hz")

    # Formatting
    ax.set_xlabel("Firing Rate (Hz)", fontsize=11)
    ax.set_ylabel("Number of Units", fontsize=11)
    ax.set_title(f"Firing Rate Distribution (n={len(units_df)} units)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3, linestyle=":")

    # Add statistics text
    stats_text = f"Mean: {np.mean(firing_rates):.2f} Hz\n"
    stats_text += f"Std: {np.std(firing_rates):.2f} Hz\n"
    stats_text += f"Range: {np.min(firing_rates):.2f}-{np.max(firing_rates):.2f} Hz"
    ax.text(
        0.98,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_unit_quality_metrics(
    units_df: pd.DataFrame,
    *,
    out_path: Path,
) -> Optional[Path]:
    """Plot quality metrics scatter plot (contamination vs amplitude).

    Visualizes unit quality by plotting contamination percentage against
    amplitude. If quality labels exist, points are colored by label.

    Args:
        units_df: DataFrame from nwbfile.units.to_dataframe()
                  Required columns: contamination_pct, amplitude
                  Optional column: quality (for color coding)
        out_path: Path where plot should be saved

    Returns:
        Path to saved plot, or None if matplotlib is unavailable or required columns missing
    """
    import logging

    logger = logging.getLogger(__name__)

    if plt is None:  # pragma: no cover
        logger.info("plot_unit_quality_metrics: matplotlib not available")
        return None

    # Check for required columns
    required_cols = ["contamination_pct", "amplitude"]
    if not all(col in units_df.columns for col in required_cols):
        logger.info(f"plot_unit_quality_metrics: missing required columns {required_cols} (available: {list(units_df.columns)})")
        return None

    _ensure_parent(out_path)

    # Extract data
    contamination = units_df["contamination_pct"].values
    amplitude = units_df["amplitude"].values
    has_quality = "quality" in units_df.columns

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 6))

    if has_quality:
        # Color by quality label
        quality = units_df["quality"].values
        quality_colors = {"good": "green", "mua": "orange", "noise": "red"}
        quality_labels = sorted(set(quality))

        # Plot each quality group
        for label in quality_labels:
            mask = quality == label
            ax.scatter(
                contamination[mask],
                amplitude[mask],
                c=quality_colors.get(label, "gray"),
                label=f"{label} (n={mask.sum()})",
                s=60,
                alpha=0.6,
                edgecolors="k",
                linewidth=0.5,
            )
    else:
        # Single color if no quality labels
        ax.scatter(
            contamination,
            amplitude,
            c="steelblue",
            s=60,
            alpha=0.6,
            edgecolors="k",
            linewidth=0.5,
            label=f"All units (n={len(units_df)})",
        )

    # Formatting
    ax.set_xlabel("Contamination (%)", fontsize=11)
    ax.set_ylabel("Amplitude (μV)", fontsize=11)
    ax.set_title(f"Unit Quality Metrics (n={len(units_df)} units)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, loc="best")
    ax.grid(True, alpha=0.3, linestyle=":")

    # Add reference lines for quality thresholds (typical values)
    ax.axvline(5.0, color="gray", linestyle=":", alpha=0.5, linewidth=1)
    ax.axhline(50.0, color="gray", linestyle=":", alpha=0.5, linewidth=1)
    ax.text(5.5, ax.get_ylim()[1] * 0.95, "5% contam.", fontsize=8, color="gray", alpha=0.7)
    ax.text(ax.get_xlim()[1] * 0.02, 52, "50 μV", fontsize=8, color="gray", alpha=0.7)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path
