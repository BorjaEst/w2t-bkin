"""Visualization module for facemap data.

Provides plotting functions for:
- Face/ROI timeseries traces (PCs, motSVD)
- Activity distributions
- ROI/PC correlation heatmaps
- Event-aligned facemap averages

All functions consume FacemapBundle domain models.
"""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import add_phase_annotation, ensure_output_dir, get_camera_color, make_deterministic_filename, make_figure_grid, save_figure
from w2t_bkin.domain.facemap import FacemapBundle, FacemapROI, FacemapSignal

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_facemap_timeseries(
    facemap_bundle: FacemapBundle,
    max_signals: int = 5,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot timeseries traces for facemap signals.

    Args:
        facemap_bundle: FacemapBundle with ROI signals
        max_signals: Maximum number of signals to plot
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="wide")

    if not facemap_bundle.signals:
        ax.text(0.5, 0.5, "No facemap signals available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Plot up to max_signals
    signals_to_plot = facemap_bundle.signals[:max_signals]
    colors = plt.cm.tab10.colors

    for idx, signal in enumerate(signals_to_plot):
        color = colors[idx % len(colors)]
        # Normalize signal for stacked display
        normalized = np.array(signal.values) + idx * 0.5
        ax.plot(signal.timestamps, normalized, label=signal.roi_name, color=color, linewidth=1, alpha=0.8)

    # Styling
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Motion Energy (normalized + offset)", fontsize=11)
    ax.set_title(f"Facemap Timeseries\n{facemap_bundle.camera_id} | {len(facemap_bundle.signals)} ROIs", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    add_phase_annotation(ax, f"Session: {facemap_bundle.session_id}", location="top-right")

    return ax


def plot_facemap_distributions(
    facemap_bundle: FacemapBundle,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot distributions of motion energy across all ROIs.

    Args:
        facemap_bundle: FacemapBundle with ROI signals
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not facemap_bundle.signals:
        ax.text(0.5, 0.5, "No facemap signals available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Collect all values
    all_values = []
    roi_labels = []

    for signal in facemap_bundle.signals:
        all_values.append(signal.values)
        roi_labels.append(signal.roi_name)

    # Plot violin plot
    parts = ax.violinplot(all_values, positions=range(len(all_values)), showmeans=True, showmedians=True)

    # Color the violins
    color = get_camera_color(facemap_bundle.camera_id)
    for pc in parts["bodies"]:
        pc.set_facecolor(color)
        pc.set_alpha(0.7)

    # Styling
    ax.set_xlabel("ROI", fontsize=11)
    ax.set_ylabel("Motion Energy", fontsize=11)
    ax.set_title(f"Motion Energy Distributions\n{len(facemap_bundle.signals)} ROIs", fontsize=12, fontweight="bold")
    ax.set_xticks(range(len(roi_labels)))
    ax.set_xticklabels(roi_labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.3, axis="y")

    return ax


def plot_facemap_correlation_matrix(
    facemap_bundle: FacemapBundle,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot correlation matrix between ROI signals.

    Args:
        facemap_bundle: FacemapBundle with ROI signals
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if len(facemap_bundle.signals) < 2:
        ax.text(0.5, 0.5, "Need at least 2 signals for correlation", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Build correlation matrix
    roi_names = [sig.roi_name for sig in facemap_bundle.signals]
    n_rois = len(roi_names)

    # Align all signals to same length (use minimum length)
    min_len = min(len(sig.values) for sig in facemap_bundle.signals)
    signal_matrix = np.array([sig.values[:min_len] for sig in facemap_bundle.signals])

    # Calculate correlation
    corr_matrix = np.corrcoef(signal_matrix)

    # Plot heatmap
    im = ax.imshow(corr_matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

    # Add colorbar
    plt.colorbar(im, ax=ax, label="Correlation")

    # Add correlation values as text
    for i in range(n_rois):
        for j in range(n_rois):
            text = ax.text(j, i, f"{corr_matrix[i, j]:.2f}", ha="center", va="center", color="black", fontsize=8)

    # Styling
    ax.set_xticks(range(n_rois))
    ax.set_yticks(range(n_rois))
    ax.set_xticklabels(roi_names, rotation=45, ha="right")
    ax.set_yticklabels(roi_names)
    ax.set_title(f"ROI Correlation Matrix\n{facemap_bundle.camera_id}", fontsize=12, fontweight="bold")

    return ax


def plot_facemap_rois(
    facemap_bundle: FacemapBundle,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot ROI definitions as rectangles.

    Args:
        facemap_bundle: FacemapBundle with ROI definitions
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not facemap_bundle.rois:
        ax.text(0.5, 0.5, "No ROIs defined", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Find bounds
    max_x = max(roi.x + roi.width for roi in facemap_bundle.rois)
    max_y = max(roi.y + roi.height for roi in facemap_bundle.rois)

    # Plot ROIs as rectangles
    colors = plt.cm.tab10.colors

    for idx, roi in enumerate(facemap_bundle.rois):
        color = colors[idx % len(colors)]
        rect = plt.Rectangle((roi.x, roi.y), roi.width, roi.height, linewidth=2, edgecolor=color, facecolor=color, alpha=0.3)
        ax.add_patch(rect)

        # Add label
        ax.text(roi.x + roi.width / 2, roi.y + roi.height / 2, roi.name, ha="center", va="center", fontsize=10, fontweight="bold", color="black")

    # Styling
    ax.set_xlim(0, max_x * 1.1)
    ax.set_ylim(0, max_y * 1.1)
    ax.set_xlabel("X (pixels)", fontsize=11)
    ax.set_ylabel("Y (pixels)", fontsize=11)
    ax.set_title(f"Facemap ROI Layout\n{len(facemap_bundle.rois)} ROIs", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()  # Match image coordinates
    ax.set_aspect("equal")

    return ax


def plot_facemap_summary_panel(
    facemap_bundle: FacemapBundle,
) -> plt.Figure:
    """Create multi-panel facemap summary figure.

    Creates a 2x2 panel with:
    - Top-left: Timeseries traces
    - Top-right: Activity distributions
    - Bottom-left: Correlation matrix
    - Bottom-right: ROI layout

    Args:
        facemap_bundle: FacemapBundle with signals and ROIs

    Returns:
        Matplotlib Figure object
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: Timeseries
    plot_facemap_timeseries(facemap_bundle, ax=axes[0, 0])

    # Top-right: Distributions
    plot_facemap_distributions(facemap_bundle, ax=axes[0, 1])

    # Bottom-left: Correlation matrix
    plot_facemap_correlation_matrix(facemap_bundle, ax=axes[1, 0])

    # Bottom-right: ROI layout
    plot_facemap_rois(facemap_bundle, ax=axes[1, 1])

    fig.suptitle(f"Facemap Summary — {facemap_bundle.session_id} / {facemap_bundle.camera_id}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_facemap_figures(
    facemap_bundle: Union[FacemapBundle, str, Path],
    output_dir: Union[str, Path],
    session_id: str = "unknown",
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all facemap figures.

    Creates:
    - Multi-panel summary (timeseries, distributions, correlation, ROIs)
    - Individual component figures

    Args:
        facemap_bundle: FacemapBundle object or path to facemap data JSON
        output_dir: Output directory for figures
        session_id: Session identifier for deterministic filenames
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Example:
        >>> paths = render_facemap_figures(
        ...     facemap_bundle='data/interim/facemap_bundle.json',
        ...     output_dir='reports/figures/facemap',
        ...     session_id='SNA-145518'
        ... )
    """
    # Load object if path provided
    if isinstance(facemap_bundle, (str, Path)):
        import json

        with open(facemap_bundle, "r") as f:
            facemap_bundle = FacemapBundle(**json.load(f))

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # Use session_id from bundle if available
    if hasattr(facemap_bundle, "session_id"):
        session_id = facemap_bundle.session_id

    # 1. Multi-panel summary
    fig_summary = plot_facemap_summary_panel(facemap_bundle)
    filename_summary = make_deterministic_filename(session_id, "facemap", "summary", camera_id=facemap_bundle.camera_id, ext=formats[0])
    paths_summary = save_figure(fig_summary, output_dir, filename_summary, formats=formats)
    saved_paths.extend(paths_summary)

    # 2. Individual timeseries (larger, all signals)
    fig_ts, ax_ts = make_figure_grid(1, 1, figsize="wide")
    plot_facemap_timeseries(facemap_bundle, max_signals=len(facemap_bundle.signals), ax=ax_ts)
    filename_ts = make_deterministic_filename(session_id, "facemap", "timeseries", camera_id=facemap_bundle.camera_id, ext=formats[0])
    paths_ts = save_figure(fig_ts, output_dir, filename_ts, formats=formats)
    saved_paths.extend(paths_ts)

    return saved_paths
