"""Visualization module for ingest and verification phase.

Provides plotting functions for:
- Frame vs TTL count comparisons
- Verification status summaries
- File discovery overviews
- Per-camera mismatch diagnostics

All functions consume Manifest and VerificationSummary domain models.
"""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import (
    add_phase_annotation,
    add_threshold_line,
    ensure_output_dir,
    get_camera_color,
    get_status_color,
    make_deterministic_filename,
    make_figure_grid,
    save_figure,
)
from w2t_bkin.domain.manifest import CameraVerificationResult, Manifest, VerificationSummary

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_frame_vs_ttl_counts(
    manifest: Manifest,
    verification_summary: VerificationSummary,
    tolerance: int = 1,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot frame count vs TTL count comparison for all cameras.

    Creates a grouped bar chart showing frame_count and ttl_pulse_count
    for each camera, with visual indication of mismatch status.

    Args:
        manifest: Manifest with counted cameras
        verification_summary: Verification summary with per-camera results
        tolerance: Mismatch tolerance threshold
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Raises:
        ValueError: If manifest cameras are not counted (frame_count is None)

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_frame_vs_ttl_counts(manifest, verification_summary, tolerance=1, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Extract data from verification summary
    camera_ids = []
    frame_counts = []
    ttl_counts = []
    statuses = []

    for cam_result in verification_summary.cameras:
        camera_ids.append(cam_result.camera_id)
        frame_counts.append(cam_result.frame_count)
        ttl_counts.append(cam_result.ttl_pulse_count)
        statuses.append(cam_result.status)

    if not camera_ids:
        ax.text(0.5, 0.5, "No cameras to verify", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Create bar positions
    x = np.arange(len(camera_ids))
    width = 0.35

    # Plot bars
    bars1 = ax.bar(x - width / 2, frame_counts, width, label="Frame Count", color="steelblue", alpha=0.8)
    bars2 = ax.bar(x + width / 2, ttl_counts, width, label="TTL Pulse Count", color="orange", alpha=0.8)

    # Add mismatch annotations
    for i, (fc, tc, status) in enumerate(zip(frame_counts, ttl_counts, statuses)):
        mismatch = abs(fc - tc)
        if mismatch > 0:
            y_pos = max(fc, tc) * 1.02
            color = get_status_color(status)
            ax.text(x[i], y_pos, f"Δ{mismatch}", ha="center", va="bottom", fontsize=8, color=color, fontweight="bold")

    # Styling
    ax.set_xlabel("Camera ID", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title(f"Frame vs TTL Count Comparison\n(Tolerance: ±{tolerance})", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(camera_ids, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # Add phase annotation
    add_phase_annotation(ax, f"Session: {manifest.session_id}", location="top-left")

    return ax


def plot_verification_status_summary(
    verification_summary: VerificationSummary,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot verification status summary as horizontal bar chart.

    Shows mismatch magnitude sorted by severity, color-coded by status.

    Args:
        verification_summary: Verification summary with per-camera results
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_verification_status_summary(verification_summary, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Sort cameras by mismatch (descending)
    sorted_results = sorted(verification_summary.cameras, key=lambda x: x.mismatch, reverse=True)

    if not sorted_results:
        ax.text(0.5, 0.5, "No verification results", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Extract data
    camera_ids = [r.camera_id for r in sorted_results]
    mismatches = [r.mismatch for r in sorted_results]
    statuses = [r.status for r in sorted_results]
    colors = [get_status_color(s) for s in statuses]

    # Plot horizontal bars
    y = np.arange(len(camera_ids))
    bars = ax.barh(y, mismatches, color=colors, alpha=0.8)

    # Add value labels
    for i, (bar, mismatch, status) in enumerate(zip(bars, mismatches, statuses)):
        ax.text(bar.get_width() + max(mismatches) * 0.01, bar.get_y() + bar.get_height() / 2, f"{mismatch} ({status.upper()})", va="center", fontsize=9)

    # Styling
    ax.set_yticks(y)
    ax.set_yticklabels(camera_ids)
    ax.set_xlabel("Mismatch (|frame_count - ttl_pulse_count|)", fontsize=11)
    ax.set_title("Verification Status Summary\n(sorted by mismatch)", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="x")
    ax.invert_yaxis()  # Highest mismatch at top

    return ax


def plot_discovery_overview(
    manifest: Manifest,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot file discovery overview showing counts of discovered files.

    Creates a bar chart showing number of video files, TTL files, and
    Bpod files discovered for the session.

    Args:
        manifest: Manifest with discovered files
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object

    Example:
        >>> fig, ax = plt.subplots()
        >>> plot_discovery_overview(manifest, ax=ax)
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="small")

    # Count discovered files
    total_video_files = sum(len(cam.video_files) for cam in manifest.cameras)
    total_ttl_files = sum(len(ttl.files) for ttl in manifest.ttls)
    total_bpod_files = len(manifest.bpod_files) if manifest.bpod_files else 0

    categories = ["Video Files", "TTL Files", "Bpod Files"]
    counts = [total_video_files, total_ttl_files, total_bpod_files]
    colors = ["steelblue", "orange", "green"]

    # Plot bars
    bars = ax.bar(categories, counts, color=colors, alpha=0.8)

    # Add count labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height, f"{count}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Styling
    ax.set_ylabel("Number of Files", fontsize=11)
    ax.set_title(f"File Discovery Overview\nSession: {manifest.session_id}", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0, max(counts) * 1.15 if max(counts) > 0 else 1)

    return ax


def plot_per_camera_details(
    manifest: Manifest,
    verification_summary: VerificationSummary,
    tolerance: int = 1,
) -> plt.Figure:
    """Create multi-panel figure with per-camera details.

    Creates a figure with one panel per camera showing:
    - Frame and TTL counts
    - Mismatch status
    - Number of video files

    Args:
        manifest: Manifest with counted cameras
        verification_summary: Verification summary with per-camera results
        tolerance: Mismatch tolerance threshold

    Returns:
        Matplotlib Figure object

    Example:
        >>> fig = plot_per_camera_details(manifest, verification_summary, tolerance=1)
    """
    n_cameras = len(verification_summary.cameras)
    if n_cameras == 0:
        fig, ax = make_figure_grid(1, 1, figsize="small")
        ax.text(0.5, 0.5, "No cameras to display", ha="center", va="center", transform=ax.transAxes)
        return fig

    # Create grid layout
    ncols = min(3, n_cameras)
    nrows = (n_cameras + ncols - 1) // ncols

    fig, axes = make_figure_grid(nrows, ncols, figsize="large")
    axes_flat = axes.flatten() if n_cameras > 1 else [axes]

    # Plot each camera
    for idx, cam_result in enumerate(verification_summary.cameras):
        ax = axes_flat[idx]

        # Find camera in manifest
        cam_manifest = next((c for c in manifest.cameras if c.camera_id == cam_result.camera_id), None)

        if cam_manifest is None:
            ax.text(0.5, 0.5, f"Camera {cam_result.camera_id}\nNot in manifest", ha="center", va="center", transform=ax.transAxes)
            continue

        # Bar data
        categories = ["Frames", "TTL\nPulses", "Video\nFiles"]
        values = [cam_result.frame_count, cam_result.ttl_pulse_count, len(cam_manifest.video_files)]

        # Plot bars
        color = get_camera_color(cam_result.camera_id)
        bars = ax.bar(categories, values, color=color, alpha=0.8)

        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height, f"{val}", ha="center", va="bottom", fontsize=9)

        # Styling
        status_color = get_status_color(cam_result.status)
        ax.set_title(f"{cam_result.camera_id}\nMismatch: {cam_result.mismatch} ({cam_result.status.upper()})", fontsize=10, color=status_color, fontweight="bold")
        ax.set_ylabel("Count", fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")

    # Hide unused subplots
    for idx in range(n_cameras, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle(f"Per-Camera Details — Session: {manifest.session_id}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_ingest_figures(
    manifest: Union[Manifest, str, Path],
    verification_summary: Union[VerificationSummary, str, Path],
    output_dir: Union[str, Path],
    tolerance: int = 1,
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all ingest/verification phase figures.

    Creates:
    - Frame vs TTL count comparison
    - Verification status summary
    - File discovery overview
    - Per-camera details multi-panel

    Args:
        manifest: Manifest object or path to manifest.json
        verification_summary: VerificationSummary object or path to verification_summary.json
        output_dir: Output directory for figures
        tolerance: Mismatch tolerance threshold
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Raises:
        FileNotFoundError: If JSON paths don't exist
        ValueError: If manifest cameras are not counted

    Example:
        >>> paths = render_ingest_figures(
        ...     manifest='data/interim/manifest.json',
        ...     verification_summary='data/interim/verification_summary.json',
        ...     output_dir='reports/figures/ingest'
        ... )
    """
    # Load objects if paths provided
    if isinstance(manifest, (str, Path)):
        import json

        with open(manifest, "r") as f:
            manifest = Manifest(**json.load(f))

    if isinstance(verification_summary, (str, Path)):
        import json

        with open(verification_summary, "r") as f:
            verification_summary = VerificationSummary(**json.load(f))

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # 1. Frame vs TTL count comparison
    fig1, ax1 = make_figure_grid(1, 1, figsize="medium")
    plot_frame_vs_ttl_counts(manifest, verification_summary, tolerance=tolerance, ax=ax1)
    filename1 = make_deterministic_filename(manifest.session_id, "ingest", "counts", ext=formats[0])
    paths1 = save_figure(fig1, output_dir, filename1, formats=formats)
    saved_paths.extend(paths1)

    # 2. Verification status summary
    fig2, ax2 = make_figure_grid(1, 1, figsize="medium")
    plot_verification_status_summary(verification_summary, ax=ax2)
    filename2 = make_deterministic_filename(manifest.session_id, "ingest", "status", ext=formats[0])
    paths2 = save_figure(fig2, output_dir, filename2, formats=formats)
    saved_paths.extend(paths2)

    # 3. File discovery overview
    fig3, ax3 = make_figure_grid(1, 1, figsize="small")
    plot_discovery_overview(manifest, ax=ax3)
    filename3 = make_deterministic_filename(manifest.session_id, "ingest", "discovery", ext=formats[0])
    paths3 = save_figure(fig3, output_dir, filename3, formats=formats)
    saved_paths.extend(paths3)

    # 4. Per-camera details
    fig4 = plot_per_camera_details(manifest, verification_summary, tolerance=tolerance)
    filename4 = make_deterministic_filename(manifest.session_id, "ingest", "cameras", ext=formats[0])
    paths4 = save_figure(fig4, output_dir, filename4, formats=formats)
    saved_paths.extend(paths4)

    return saved_paths
