"""Shared utilities for figures package.

Provides common functionality used across all visualization modules:
- Layout and figure grid management
- Consistent styling (colors, fonts, line styles)
- I/O helpers (deterministic filenames, multi-format saving)
- Time axis helpers for timebase-aligned plotting
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

# Type aliases
FigureSize = Literal["small", "medium", "large", "a4_landscape", "a4_portrait", "wide", "tall"]
SaveFormat = Literal["png", "pdf", "svg", "jpg"]


# ============================================================================
# Layout and Figure Grid Management
# ============================================================================


def make_figure_grid(
    nrows: int = 1,
    ncols: int = 1,
    figsize: Optional[Union[FigureSize, Tuple[float, float]]] = None,
    sharex: bool = False,
    sharey: bool = False,
    **kwargs: Any,
) -> Tuple[Figure, np.ndarray]:
    """Create a figure with a grid of subplots.

    Args:
        nrows: Number of rows in the grid
        ncols: Number of columns in the grid
        figsize: Figure size preset or explicit (width, height) in inches
        sharex: Whether to share x-axis across subplots
        sharey: Whether to share y-axis across subplots
        **kwargs: Additional arguments passed to plt.subplots()

    Returns:
        Tuple of (figure, axes_array). If nrows=ncols=1, axes_array is a single Axes object.

    Example:
        >>> fig, axes = make_figure_grid(2, 2, figsize="medium")
        >>> axes[0, 0].plot([1, 2, 3])
    """
    if figsize is None:
        figsize = "medium"

    if isinstance(figsize, str):
        figsize = _get_figsize_preset(figsize)

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, sharex=sharex, sharey=sharey, **kwargs)

    # Apply consistent styling
    _apply_default_style(fig)

    return fig, axes


def _get_figsize_preset(preset: FigureSize) -> Tuple[float, float]:
    """Convert figsize preset to (width, height) in inches."""
    presets = {
        "small": (6, 4),
        "medium": (10, 6),
        "large": (14, 8),
        "a4_landscape": (11.69, 8.27),
        "a4_portrait": (8.27, 11.69),
        "wide": (16, 6),
        "tall": (8, 12),
    }
    if preset not in presets:
        raise ValueError(f"Unknown figsize preset: {preset}. Choose from {list(presets.keys())}")
    return presets[preset]


def _apply_default_style(fig: Figure) -> None:
    """Apply consistent default styling to a figure."""
    fig.tight_layout()
    # Additional style adjustments can be added here
    # e.g., font sizes, grid styles, etc.


# ============================================================================
# Color and Style Management
# ============================================================================


def get_camera_color(camera_id: str) -> str:
    """Get consistent color for a given camera ID.

    Args:
        camera_id: Camera identifier (e.g., 'cam0', 'cam1')

    Returns:
        Hex color string

    Example:
        >>> get_camera_color('cam0')
        '#1f77b4'
    """
    # Use matplotlib's tab10 colormap for consistent colors
    colors = plt.cm.tab10.colors
    # Hash camera_id to get deterministic color
    idx = int(hashlib.md5(camera_id.encode()).hexdigest(), 16) % len(colors)
    return f"#{int(colors[idx][0]*255):02x}{int(colors[idx][1]*255):02x}{int(colors[idx][2]*255):02x}"


def get_status_color(status: str) -> str:
    """Get color for verification/validation status.

    Args:
        status: Status string (e.g., 'OK', 'WARN', 'FAIL', 'ERROR')

    Returns:
        Hex color string

    Example:
        >>> get_status_color('OK')
        '#2ca02c'
    """
    status_colors = {
        "OK": "#2ca02c",  # green
        "PASS": "#2ca02c",
        "SUCCESS": "#2ca02c",
        "WARN": "#ff7f0e",  # orange
        "WARNING": "#ff7f0e",
        "FAIL": "#d62728",  # red
        "ERROR": "#d62728",
        "CRITICAL": "#8b0000",  # dark red
        "INFO": "#1f77b4",  # blue
    }
    return status_colors.get(status.upper(), "#7f7f7f")  # gray as default


def get_phase_color(phase: str) -> str:
    """Get color for pipeline phase.

    Args:
        phase: Phase name (e.g., 'ingest', 'sync', 'pose', 'nwb')

    Returns:
        Hex color string
    """
    phase_colors = {
        "ingest": "#1f77b4",
        "verify": "#ff7f0e",
        "sync": "#2ca02c",
        "transcode": "#d62728",
        "pose": "#9467bd",
        "facemap": "#8c564b",
        "events": "#e377c2",
        "nwb": "#7f7f7f",
        "validate": "#bcbd22",
        "qc": "#17becf",
    }
    return phase_colors.get(phase.lower(), "#7f7f7f")


# ============================================================================
# I/O Helpers
# ============================================================================


def ensure_output_dir(path: Union[str, Path]) -> Path:
    """Ensure output directory exists, create if necessary.

    Args:
        path: Directory path

    Returns:
        Resolved Path object

    Raises:
        OSError: If directory cannot be created
    """
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_deterministic_filename(
    session_id: str,
    phase: str,
    data_type: str,
    camera_id: Optional[str] = None,
    suffix: str = "",
    ext: str = "png",
) -> str:
    """Generate deterministic filename for figure outputs.

    Args:
        session_id: Session identifier
        phase: Pipeline phase (ingest, sync, pose, etc.)
        data_type: Type of visualization (counts, jitter, trajectory, etc.)
        camera_id: Optional camera identifier
        suffix: Optional additional suffix
        ext: File extension (without dot)

    Returns:
        Deterministic filename string

    Example:
        >>> make_deterministic_filename('SNA-145518', 'ingest', 'counts')
        'SNA-145518_ingest_counts.png'
        >>> make_deterministic_filename('SNA-145518', 'pose', 'trajectory', camera_id='cam0')
        'SNA-145518_pose_trajectory_cam0.png'
    """
    parts = [session_id, phase, data_type]
    if camera_id:
        parts.append(camera_id)
    if suffix:
        parts.append(suffix)

    filename = "_".join(parts) + f".{ext}"
    return filename


def save_figure(
    fig: Figure,
    output_dir: Union[str, Path],
    filename: str,
    formats: Sequence[SaveFormat] = ("png",),
    dpi: int = 150,
    close: bool = True,
) -> list[Path]:
    """Save figure to one or more formats with deterministic output.

    Args:
        fig: Matplotlib Figure object
        output_dir: Directory to save figure
        filename: Base filename (without extension)
        formats: Sequence of output formats
        dpi: Resolution for raster formats
        close: Whether to close figure after saving

    Returns:
        List of saved file paths

    Example:
        >>> fig, ax = plt.subplots()
        >>> ax.plot([1, 2, 3])
        >>> paths = save_figure(fig, 'reports/figures', 'test_plot', formats=('png', 'pdf'))
    """
    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # Remove extension from filename if present
    base_name = Path(filename).stem

    for fmt in formats:
        output_path = output_dir / f"{base_name}.{fmt}"
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", format=fmt)
        saved_paths.append(output_path)

    if close:
        plt.close(fig)

    return saved_paths


# ============================================================================
# Time Axis Helpers
# ============================================================================


def make_time_axis(
    n_samples: int,
    rate_hz: float,
    offset_s: float = 0.0,
) -> np.ndarray:
    """Generate time axis for rate-based data.

    Args:
        n_samples: Number of samples
        rate_hz: Sampling rate in Hz
        offset_s: Time offset in seconds

    Returns:
        1D array of time values in seconds

    Example:
        >>> t = make_time_axis(100, 30.0, offset_s=0.5)
        >>> len(t)
        100
        >>> t[0]
        0.5
    """
    return np.arange(n_samples) / rate_hz + offset_s


def format_time_axis(ax: plt.Axes, xlabel: str = "Time (s)") -> None:
    """Apply consistent formatting to time axis.

    Args:
        ax: Matplotlib Axes object
        xlabel: Label for x-axis
    """
    ax.set_xlabel(xlabel)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# ============================================================================
# Data Loading Helpers
# ============================================================================


def load_sidecar_json(path: Union[str, Path]) -> dict[str, Any]:
    """Load and parse a sidecar JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sidecar JSON not found: {path}")

    with open(path, "r") as f:
        return json.load(f)


# ============================================================================
# Annotation Helpers
# ============================================================================


def add_threshold_line(
    ax: plt.Axes,
    threshold: float,
    orientation: Literal["horizontal", "vertical"] = "horizontal",
    label: Optional[str] = None,
    color: str = "red",
    linestyle: str = "--",
    alpha: float = 0.7,
) -> None:
    """Add a threshold line to a plot.

    Args:
        ax: Matplotlib Axes object
        threshold: Threshold value
        orientation: Line orientation
        label: Optional label for legend
        color: Line color
        linestyle: Line style
        alpha: Line transparency
    """
    if orientation == "horizontal":
        ax.axhline(threshold, color=color, linestyle=linestyle, alpha=alpha, label=label)
    else:
        ax.axvline(threshold, color=color, linestyle=linestyle, alpha=alpha, label=label)


def add_phase_annotation(
    ax: plt.Axes,
    text: str,
    location: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "top-right",
    fontsize: int = 10,
    bbox_alpha: float = 0.8,
) -> None:
    """Add a text annotation box to a plot.

    Args:
        ax: Matplotlib Axes object
        text: Annotation text
        location: Corner location
        fontsize: Font size
        bbox_alpha: Background box transparency
    """
    locations = {
        "top-left": (0.02, 0.98),
        "top-right": (0.98, 0.98),
        "bottom-left": (0.02, 0.02),
        "bottom-right": (0.98, 0.02),
    }

    ha = "left" if "left" in location else "right"
    va = "top" if "top" in location else "bottom"

    ax.text(
        locations[location][0],
        locations[location][1],
        text,
        transform=ax.transAxes,
        fontsize=fontsize,
        verticalalignment=va,
        horizontalalignment=ha,
        bbox=dict(boxstyle="round", facecolor="white", alpha=bbox_alpha),
    )
