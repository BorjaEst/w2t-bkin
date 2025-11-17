"""Visualization module for NWB (Neurodata Without Borders) output validation.

Provides plotting functions for:
- NWB ImageSeries metadata summary
- Acquisition overview (devices, timeseries)
- Validation reports (metadata completeness)

All functions consume NWB file metadata or NWB-related domain models.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import add_phase_annotation, ensure_output_dir, get_phase_color, get_status_color, make_deterministic_filename, make_figure_grid, save_figure

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_nwb_metadata_summary(
    nwb_metadata: Dict[str, Any],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot NWB file metadata summary.

    Args:
        nwb_metadata: Dictionary with NWB file metadata (session_description, identifier, etc.)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Extract key metadata
    metadata_lines = []
    for key in ["identifier", "session_description", "session_start_time", "lab", "institution"]:
        if key in nwb_metadata:
            value = str(nwb_metadata[key])
            # Truncate long values
            if len(value) > 50:
                value = value[:47] + "..."
            metadata_lines.append(f"{key}: {value}")

    # Display metadata
    y_pos = 0.9
    for line in metadata_lines:
        ax.text(0.1, y_pos, line, transform=ax.transAxes, fontsize=10, verticalalignment="top", family="monospace")
        y_pos -= 0.15

    ax.set_title("NWB File Metadata", fontsize=12, fontweight="bold")
    ax.axis("off")

    return ax


def plot_nwb_devices_summary(
    devices: List[Dict[str, Any]],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot summary of devices (cameras) in NWB file.

    Args:
        devices: List of device metadata dictionaries
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not devices:
        ax.text(0.5, 0.5, "No devices found", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return ax

    # Create device summary table
    device_names = [d.get("name", "unknown") for d in devices]
    device_manufacturers = [d.get("manufacturer", "Unknown") for d in devices]

    y_positions = np.arange(len(devices))
    colors = [get_phase_color("nwb")] * len(devices)

    ax.barh(y_positions, [1] * len(devices), color=colors, alpha=0.7, edgecolor="black", linewidth=1)

    # Add device names
    for i, (name, manufacturer) in enumerate(zip(device_names, device_manufacturers)):
        ax.text(0.5, i, f"{name}\n({manufacturer})", ha="center", va="center", fontsize=9, fontweight="bold")

    # Styling
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"Device {i+1}" for i in range(len(devices))])
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title(f"Devices in NWB File\n{len(devices)} device(s)", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    return ax


def plot_nwb_acquisition_summary(
    acquisition_data: Dict[str, Any],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot summary of acquisition data in NWB file.

    Args:
        acquisition_data: Dictionary with acquisition objects (ImageSeries, TimeSeries, etc.)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not acquisition_data:
        ax.text(0.5, 0.5, "No acquisition data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return ax

    # Count types
    type_counts = {}
    for key, obj in acquisition_data.items():
        obj_type = obj.get("type", "Unknown")
        type_counts[obj_type] = type_counts.get(obj_type, 0) + 1

    # Sort by count
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    types = [t[0] for t in sorted_types]
    counts = [t[1] for t in sorted_types]
    colors = [get_phase_color("nwb")] * len(types)

    # Plot bars
    bars = ax.bar(types, counts, color=colors, alpha=0.8, edgecolor="black", linewidth=1)

    # Add count labels
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height, f"{count}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Styling
    ax.set_xlabel("Data Type", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title(f"Acquisition Data Summary\nTotal: {sum(counts)} objects", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    return ax


def plot_nwb_validation_report(
    validation_results: Dict[str, Any],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot NWB validation report.

    Args:
        validation_results: Dictionary with validation results (passed, warnings, errors)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Extract validation counts
    passed = validation_results.get("passed", 0)
    warnings = validation_results.get("warnings", 0)
    errors = validation_results.get("errors", 0)

    categories = ["Passed", "Warnings", "Errors"]
    counts = [passed, warnings, errors]
    colors = [get_status_color("success"), get_status_color("warning"), get_status_color("error")]

    # Plot bars
    bars = ax.bar(categories, counts, color=colors, alpha=0.8, edgecolor="black", linewidth=1)

    # Add count labels
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        if count > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, height, f"{count}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Styling
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title(f"NWB Validation Report", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    # Add overall status
    if errors > 0:
        status_text = "FAILED"
        status_color = get_status_color("error")
    elif warnings > 0:
        status_text = "WARNING"
        status_color = get_status_color("warning")
    else:
        status_text = "PASSED"
        status_color = get_status_color("success")

    add_phase_annotation(ax, f"Status: {status_text}", location="top-right", color=status_color)

    return ax


def plot_nwb_summary_panel(
    nwb_metadata: Dict[str, Any],
    devices: List[Dict[str, Any]],
    acquisition_data: Dict[str, Any],
    validation_results: Optional[Dict[str, Any]] = None,
) -> plt.Figure:
    """Create multi-panel NWB summary figure.

    Creates a 2x2 panel with:
    - Top-left: Metadata summary
    - Top-right: Devices summary
    - Bottom-left: Acquisition data summary
    - Bottom-right: Validation report

    Args:
        nwb_metadata: NWB file metadata
        devices: List of device metadata
        acquisition_data: Acquisition objects dictionary
        validation_results: Optional validation results

    Returns:
        Matplotlib Figure object
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: Metadata
    plot_nwb_metadata_summary(nwb_metadata, ax=axes[0, 0])

    # Top-right: Devices
    plot_nwb_devices_summary(devices, ax=axes[0, 1])

    # Bottom-left: Acquisition
    plot_nwb_acquisition_summary(acquisition_data, ax=axes[1, 0])

    # Bottom-right: Validation
    if validation_results is not None:
        plot_nwb_validation_report(validation_results, ax=axes[1, 1])
    else:
        axes[1, 1].text(0.5, 0.5, "No validation data", ha="center", va="center", transform=axes[1, 1].transAxes)
        axes[1, 1].axis("off")

    session_id = nwb_metadata.get("identifier", "unknown")
    fig.suptitle(f"NWB File Summary — {session_id}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_nwb_figures(
    nwb_data: Union[Dict[str, Any], str, Path],
    output_dir: Union[str, Path],
    session_id: str = "unknown",
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all NWB validation figures.

    Creates:
    - Multi-panel NWB summary (metadata, devices, acquisition, validation)
    - Individual component figures

    Args:
        nwb_data: Dictionary with NWB metadata or path to .nwb metadata JSON
        output_dir: Output directory for figures
        session_id: Session identifier for deterministic filenames
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Note:
        This function expects NWB metadata dictionaries, not actual .nwb files.
        For reading .nwb files, use pynwb.NWBHDF5IO and extract metadata first.

    Example:
        >>> nwb_metadata = {
        ...     'identifier': 'Session-000001',
        ...     'session_description': 'W2T training',
        ...     'devices': [{'name': 'camera0', 'manufacturer': 'Basler'}],
        ...     'acquisition': {'ImageSeries_camera0': {'type': 'ImageSeries'}},
        ...     'validation': {'passed': 10, 'warnings': 2, 'errors': 0}
        ... }
        >>> paths = render_nwb_figures(
        ...     nwb_data=nwb_metadata,
        ...     output_dir='reports/figures/nwb',
        ...     session_id='Session-000001'
        ... )
    """
    # Load metadata if path provided
    if isinstance(nwb_data, (str, Path)):
        import json

        with open(nwb_data, "r") as f:
            nwb_data = json.load(f)

    # Extract components
    nwb_metadata = {k: v for k, v in nwb_data.items() if k not in ["devices", "acquisition", "validation"]}
    devices = nwb_data.get("devices", [])
    acquisition_data = nwb_data.get("acquisition", {})
    validation_results = nwb_data.get("validation", None)

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # 1. Multi-panel summary
    fig_summary = plot_nwb_summary_panel(nwb_metadata, devices, acquisition_data, validation_results)
    filename_summary = make_deterministic_filename(session_id, "nwb", "summary", ext=formats[0])
    paths_summary = save_figure(fig_summary, output_dir, filename_summary, formats=formats)
    saved_paths.extend(paths_summary)

    # 2. Individual devices figure
    if devices:
        fig_devices, ax_devices = make_figure_grid(1, 1, figsize="medium")
        plot_nwb_devices_summary(devices, ax=ax_devices)
        filename_devices = make_deterministic_filename(session_id, "nwb", "devices", ext=formats[0])
        paths_devices = save_figure(fig_devices, output_dir, filename_devices, formats=formats)
        saved_paths.extend(paths_devices)

    # 3. Validation report (if available)
    if validation_results is not None:
        fig_validation, ax_validation = make_figure_grid(1, 1, figsize="medium")
        plot_nwb_validation_report(validation_results, ax=ax_validation)
        filename_validation = make_deterministic_filename(session_id, "nwb", "validation", ext=formats[0])
        paths_validation = save_figure(fig_validation, output_dir, filename_validation, formats=formats)
        saved_paths.extend(paths_validation)

    return saved_paths
    paths = save_figure(fig, output_dir, filename, formats=formats)
    saved_paths.extend(paths)

    return saved_paths
