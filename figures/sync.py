"""Visualization module for timebase synchronization and alignment phase.

Provides plotting functions for:
- Jitter distributions and histograms
- Alignment diagnostics and quality metrics
- Timeline overlays showing data stream alignment
- Budget threshold comparisons

All functions consume AlignmentStats domain models and alignment_stats.json sidecars.
"""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import add_phase_annotation, add_threshold_line, ensure_output_dir, get_phase_color, make_deterministic_filename, make_figure_grid, save_figure
from w2t_bkin.domain.alignment import AlignmentStats

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_jitter_histogram(
    alignment_stats: AlignmentStats,
    jitter_samples: Optional[np.ndarray] = None,
    jitter_budget_s: Optional[float] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot histogram of jitter distribution with budget threshold.

    Args:
        alignment_stats: AlignmentStats with max_jitter_s and p95_jitter_s
        jitter_samples: Optional array of per-sample jitter values (if available)
        jitter_budget_s: Optional jitter budget threshold in seconds
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Note:
        If jitter_samples is not provided, the function creates a
        synthetic histogram based on max_jitter_s and p95_jitter_s
        for visualization purposes only.

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_jitter_histogram(stats, jitter_samples=jitter_data, jitter_budget_s=0.001, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # If no jitter samples provided, create synthetic distribution for visualization
    if jitter_samples is None:
        # Create synthetic distribution based on stats
        # Assume roughly Gaussian with mean ~ p95/2, std ~ p95/2
        n_samples = 10000
        mean_jitter = alignment_stats.p95_jitter_s / 2
        std_jitter = alignment_stats.p95_jitter_s / 2
        jitter_samples = np.abs(np.random.normal(mean_jitter, std_jitter, n_samples))
        # Clip to max
        jitter_samples = np.clip(jitter_samples, 0, alignment_stats.max_jitter_s)
        synthetic_note = " (synthetic for visualization)"
    else:
        synthetic_note = ""

    # Plot histogram
    n_bins = 50
    ax.hist(jitter_samples, bins=n_bins, alpha=0.7, color=get_phase_color("sync"), edgecolor="black", linewidth=0.5, label="Jitter Distribution")

    # Add vertical lines for statistics
    ax.axvline(alignment_stats.p95_jitter_s, color="orange", linestyle="--", linewidth=2, label=f"P95: {alignment_stats.p95_jitter_s*1000:.3f} ms")
    ax.axvline(alignment_stats.max_jitter_s, color="red", linestyle="--", linewidth=2, label=f"Max: {alignment_stats.max_jitter_s*1000:.3f} ms")

    # Add budget threshold if provided
    if jitter_budget_s is not None:
        add_threshold_line(ax, jitter_budget_s, orientation="vertical", label=f"Budget: {jitter_budget_s*1000:.3f} ms", color="darkred", linestyle=":", alpha=0.9)

        # Check if budget exceeded
        if alignment_stats.max_jitter_s > jitter_budget_s:
            budget_status = "EXCEEDED"
            budget_color = "red"
        else:
            budget_status = "OK"
            budget_color = "green"

        add_phase_annotation(ax, f"Budget: {budget_status}", location="top-right", bbox_alpha=0.9)

    # Styling
    ax.set_xlabel("Jitter (seconds)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title(f"Jitter Distribution{synthetic_note}\n{alignment_stats.timebase_source} | {alignment_stats.mapping} mapping", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    return ax


def plot_jitter_cdf(
    alignment_stats: AlignmentStats,
    jitter_samples: Optional[np.ndarray] = None,
    jitter_budget_s: Optional[float] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot cumulative distribution function (CDF) of jitter.

    Args:
        alignment_stats: AlignmentStats with max_jitter_s and p95_jitter_s
        jitter_samples: Optional array of per-sample jitter values (if available)
        jitter_budget_s: Optional jitter budget threshold in seconds
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_jitter_cdf(stats, jitter_samples=jitter_data, jitter_budget_s=0.001, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # If no jitter samples provided, create synthetic distribution
    if jitter_samples is None:
        n_samples = 10000
        mean_jitter = alignment_stats.p95_jitter_s / 2
        std_jitter = alignment_stats.p95_jitter_s / 2
        jitter_samples = np.abs(np.random.normal(mean_jitter, std_jitter, n_samples))
        jitter_samples = np.clip(jitter_samples, 0, alignment_stats.max_jitter_s)
        synthetic_note = " (synthetic)"
    else:
        synthetic_note = ""

    # Sort for CDF
    sorted_jitter = np.sort(jitter_samples)
    cdf = np.arange(1, len(sorted_jitter) + 1) / len(sorted_jitter)

    # Plot CDF
    ax.plot(sorted_jitter, cdf, linewidth=2, color=get_phase_color("sync"), label="Jitter CDF")

    # Mark P95
    ax.axvline(alignment_stats.p95_jitter_s, color="orange", linestyle="--", linewidth=2, label=f"P95: {alignment_stats.p95_jitter_s*1000:.3f} ms")
    ax.axhline(0.95, color="orange", linestyle=":", linewidth=1, alpha=0.5)

    # Mark max
    ax.axvline(alignment_stats.max_jitter_s, color="red", linestyle="--", linewidth=2, label=f"Max: {alignment_stats.max_jitter_s*1000:.3f} ms")

    # Add budget threshold if provided
    if jitter_budget_s is not None:
        add_threshold_line(ax, jitter_budget_s, orientation="vertical", label=f"Budget: {jitter_budget_s*1000:.3f} ms", color="darkred", linestyle=":", alpha=0.9)

    # Styling
    ax.set_xlabel("Jitter (seconds)", fontsize=11)
    ax.set_ylabel("Cumulative Probability", fontsize=11)
    ax.set_title(f"Jitter CDF{synthetic_note}", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)

    return ax


def plot_alignment_summary_panel(
    alignment_stats: AlignmentStats,
    jitter_samples: Optional[np.ndarray] = None,
    jitter_budget_s: Optional[float] = None,
) -> plt.Figure:
    """Create multi-panel alignment diagnostics figure.

    Creates a 2x2 panel with:
    - Top-left: Jitter histogram
    - Top-right: Jitter CDF
    - Bottom-left: Alignment summary stats table
    - Bottom-right: Timebase configuration info

    Args:
        alignment_stats: AlignmentStats domain object
        jitter_samples: Optional array of per-sample jitter values
        jitter_budget_s: Optional jitter budget threshold in seconds

    Returns:
        Matplotlib Figure object

    Example:
        >>> fig = plot_alignment_summary_panel(stats, jitter_budget_s=0.001)
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: Jitter histogram
    plot_jitter_histogram(alignment_stats, jitter_samples, jitter_budget_s, ax=axes[0, 0])

    # Top-right: Jitter CDF
    plot_jitter_cdf(alignment_stats, jitter_samples, jitter_budget_s, ax=axes[0, 1])

    # Bottom-left: Summary stats table
    ax_table = axes[1, 0]
    ax_table.axis("off")

    table_data = [
        ["Metric", "Value"],
        ["Timebase Source", alignment_stats.timebase_source],
        ["Mapping Strategy", alignment_stats.mapping],
        ["Offset (s)", f"{alignment_stats.offset_s:.6f}"],
        ["Max Jitter (ms)", f"{alignment_stats.max_jitter_s*1000:.3f}"],
        ["P95 Jitter (ms)", f"{alignment_stats.p95_jitter_s*1000:.3f}"],
        ["Aligned Samples", f"{alignment_stats.aligned_samples:,}"],
    ]

    if jitter_budget_s is not None:
        budget_ok = alignment_stats.max_jitter_s <= jitter_budget_s
        budget_status = "✓ OK" if budget_ok else "✗ EXCEEDED"
        budget_color = "green" if budget_ok else "red"
        table_data.append(["Budget Check", budget_status])

    table = ax_table.table(cellText=table_data, cellLoc="left", loc="center", colWidths=[0.6, 0.4])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)

    # Style header row
    for i in range(2):
        table[(0, i)].set_facecolor("#4CAF50")
        table[(0, i)].set_text_props(weight="bold", color="white")

    # Style budget row if present
    if jitter_budget_s is not None:
        budget_row_idx = len(table_data) - 1
        table[(budget_row_idx, 1)].set_text_props(color=budget_color, weight="bold")

    ax_table.set_title("Alignment Summary Statistics", fontsize=12, fontweight="bold", pad=20)

    # Bottom-right: Timebase configuration
    ax_info = axes[1, 1]
    ax_info.axis("off")

    info_text = f"""Timebase Configuration

Source: {alignment_stats.timebase_source.upper()}
Mapping: {alignment_stats.mapping.upper()}

Alignment Quality:
• Max Jitter: {alignment_stats.max_jitter_s*1000:.3f} ms
• P95 Jitter: {alignment_stats.p95_jitter_s*1000:.3f} ms
• Aligned Samples: {alignment_stats.aligned_samples:,}
"""

    if jitter_budget_s is not None:
        info_text += f"\nBudget: {jitter_budget_s*1000:.3f} ms"
        if alignment_stats.max_jitter_s > jitter_budget_s:
            info_text += "\n⚠ Budget EXCEEDED"
        else:
            info_text += "\n✓ Budget OK"

    ax_info.text(
        0.1, 0.5, info_text, transform=ax_info.transAxes, fontsize=10, verticalalignment="center", fontfamily="monospace", bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3)
    )

    fig.suptitle("Timebase Alignment Diagnostics", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


def plot_jitter_vs_time(
    jitter_samples: np.ndarray,
    alignment_stats: AlignmentStats,
    sample_rate_hz: Optional[float] = None,
    jitter_budget_s: Optional[float] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot jitter magnitude over time (sample index or time).

    Useful for detecting temporal patterns, drift, or anomalies in alignment quality.

    Args:
        jitter_samples: Array of per-sample jitter values (seconds)
        alignment_stats: AlignmentStats for context
        sample_rate_hz: Optional sample rate to convert to time axis
        jitter_budget_s: Optional jitter budget threshold
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_jitter_vs_time(jitter_data, stats, sample_rate_hz=30.0, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="wide")

    n_samples = len(jitter_samples)

    # Determine x-axis (sample index or time)
    if sample_rate_hz is not None:
        x = np.arange(n_samples) / sample_rate_hz
        xlabel = "Time (s)"
    else:
        x = np.arange(n_samples)
        xlabel = "Sample Index"

    # Plot jitter
    ax.plot(x, jitter_samples * 1000, linewidth=0.5, alpha=0.7, color=get_phase_color("sync"))

    # Add statistics lines
    ax.axhline(alignment_stats.p95_jitter_s * 1000, color="orange", linestyle="--", linewidth=1, label=f"P95: {alignment_stats.p95_jitter_s*1000:.3f} ms")
    ax.axhline(alignment_stats.max_jitter_s * 1000, color="red", linestyle="--", linewidth=1, label=f"Max: {alignment_stats.max_jitter_s*1000:.3f} ms")

    # Add budget threshold if provided
    if jitter_budget_s is not None:
        add_threshold_line(ax, jitter_budget_s * 1000, orientation="horizontal", label=f"Budget: {jitter_budget_s*1000:.3f} ms", color="darkred", linestyle=":", alpha=0.9)

    # Styling
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel("Jitter (ms)", fontsize=11)
    ax.set_title(f"Jitter vs Time\n{alignment_stats.timebase_source} | {alignment_stats.mapping} mapping", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return ax


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_sync_figures(
    alignment_stats: Union[AlignmentStats, str, Path],
    output_dir: Union[str, Path],
    jitter_samples: Optional[np.ndarray] = None,
    jitter_budget_s: Optional[float] = None,
    sample_rate_hz: Optional[float] = None,
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all sync/alignment phase figures.

    Creates:
    - Multi-panel alignment diagnostics (histogram, CDF, stats, config)
    - Jitter vs time plot (if jitter_samples provided)

    Args:
        alignment_stats: AlignmentStats object or path to alignment_stats.json
        output_dir: Output directory for figures
        jitter_samples: Optional array of per-sample jitter values
        jitter_budget_s: Optional jitter budget threshold in seconds
        sample_rate_hz: Optional sample rate for time axis conversion
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Raises:
        FileNotFoundError: If JSON path doesn't exist

    Example:
        >>> paths = render_sync_figures(
        ...     alignment_stats='data/interim/alignment_stats.json',
        ...     output_dir='reports/figures/sync',
        ...     jitter_budget_s=0.001
        ... )
    """
    # Load object if path provided
    if isinstance(alignment_stats, (str, Path)):
        import json

        with open(alignment_stats, "r") as f:
            alignment_stats = AlignmentStats(**json.load(f))

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # Determine session_id (use timebase_source as proxy if not available)
    session_id = f"session_{alignment_stats.timebase_source}"

    # 1. Multi-panel alignment diagnostics
    fig1 = plot_alignment_summary_panel(alignment_stats, jitter_samples, jitter_budget_s)
    filename1 = make_deterministic_filename(session_id, "sync", "alignment_summary", ext=formats[0])
    paths1 = save_figure(fig1, output_dir, filename1, formats=formats)
    saved_paths.extend(paths1)

    # 2. Jitter vs time (only if jitter_samples provided)
    if jitter_samples is not None:
        fig2, ax2 = make_figure_grid(1, 1, figsize="wide")
        plot_jitter_vs_time(jitter_samples, alignment_stats, sample_rate_hz, jitter_budget_s, ax=ax2)
        filename2 = make_deterministic_filename(session_id, "sync", "jitter_vs_time", ext=formats[0])
        paths2 = save_figure(fig2, output_dir, filename2, formats=formats)
        saved_paths.extend(paths2)

    return saved_paths
