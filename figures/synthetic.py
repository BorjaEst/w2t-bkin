"""Visualization module for synthetic vs real data comparisons.

Provides plotting functions for:
- Distribution comparisons (KDE plots, histograms)
- Statistical test results (KS tests, t-tests)
- Per-modality fixture validations

All functions compare synthetic test fixtures against real data expectations.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from figures.utils import add_phase_annotation, add_threshold_line, ensure_output_dir, get_status_color, make_deterministic_filename, make_figure_grid, save_figure

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_distribution_comparison(
    real_data: np.ndarray,
    synthetic_data: np.ndarray,
    label: str = "Value",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot KDE comparison between real and synthetic distributions.

    Args:
        real_data: Real data array
        synthetic_data: Synthetic data array
        label: Data label for axis
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Plot histograms
    ax.hist(real_data, bins=30, alpha=0.5, color="steelblue", label="Real", density=True, edgecolor="black", linewidth=0.5)
    ax.hist(synthetic_data, bins=30, alpha=0.5, color="coral", label="Synthetic", density=True, edgecolor="black", linewidth=0.5)

    # Plot KDE
    if len(real_data) > 1:
        kde_real = stats.gaussian_kde(real_data)
        x_range = np.linspace(min(real_data.min(), synthetic_data.min()), max(real_data.max(), synthetic_data.max()), 200)
        ax.plot(x_range, kde_real(x_range), color="steelblue", linewidth=2, label="Real KDE")

    if len(synthetic_data) > 1:
        kde_synthetic = stats.gaussian_kde(synthetic_data)
        x_range = np.linspace(min(real_data.min(), synthetic_data.min()), max(real_data.max(), synthetic_data.max()), 200)
        ax.plot(x_range, kde_synthetic(x_range), color="coral", linewidth=2, linestyle="--", label="Synthetic KDE")

    # Styling
    ax.set_xlabel(label, fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.set_title(f"Distribution Comparison: {label}", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return ax


def plot_statistical_test_results(
    test_results: Dict[str, Dict[str, Any]],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot statistical test results (KS, t-test).

    Args:
        test_results: Dictionary with test names and results (statistic, p_value)
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not test_results:
        ax.text(0.5, 0.5, "No test results", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return ax

    # Extract test names and p-values
    test_names = list(test_results.keys())
    p_values = [test_results[name].get("p_value", 1.0) for name in test_names]

    # Color by significance (alpha=0.05)
    colors = [get_status_color("success") if p > 0.05 else get_status_color("error") for p in p_values]

    # Plot bars
    bars = ax.bar(test_names, p_values, color=colors, alpha=0.8, edgecolor="black", linewidth=1)

    # Add significance line
    add_threshold_line(ax, 0.05, label="α = 0.05", color="red", linestyle="--")

    # Add p-value labels
    for bar, p_val in zip(bars, p_values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height, f"{p_val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Styling
    ax.set_ylabel("p-value", fontsize=11)
    ax.set_title("Statistical Test Results\n(p > 0.05 = distributions similar)", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3, axis="y")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    return ax


def plot_qqplot(
    real_data: np.ndarray,
    synthetic_data: np.ndarray,
    label: str = "Value",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot Q-Q plot comparing real vs synthetic distributions.

    Args:
        real_data: Real data array
        synthetic_data: Synthetic data array
        label: Data label for title
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    # Compute quantiles
    n = min(len(real_data), len(synthetic_data))
    quantiles_real = np.percentile(real_data, np.linspace(0, 100, n))
    quantiles_synthetic = np.percentile(synthetic_data, np.linspace(0, 100, n))

    # Plot Q-Q
    ax.scatter(quantiles_real, quantiles_synthetic, alpha=0.6, s=20, color="steelblue")

    # Plot diagonal reference line
    min_val = min(quantiles_real.min(), quantiles_synthetic.min())
    max_val = max(quantiles_real.max(), quantiles_synthetic.max())
    ax.plot([min_val, max_val], [min_val, max_val], "r--", linewidth=2, label="Perfect match")

    # Styling
    ax.set_xlabel(f"Real {label} Quantiles", fontsize=11)
    ax.set_ylabel(f"Synthetic {label} Quantiles", fontsize=11)
    ax.set_title(f"Q-Q Plot: {label}", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return ax


def plot_fixture_validation_summary(
    validation_results: Dict[str, bool],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot validation summary for fixtures.

    Args:
        validation_results: Dictionary with fixture names and pass/fail status
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not validation_results:
        ax.text(0.5, 0.5, "No validation results", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return ax

    # Count passed/failed
    passed = sum(1 for status in validation_results.values() if status)
    failed = len(validation_results) - passed

    # Plot pie chart
    sizes = [passed, failed]
    labels = [f"Passed ({passed})", f"Failed ({failed})"]
    colors = [get_status_color("success"), get_status_color("error")]
    explode = (0.05, 0) if failed > 0 else (0, 0)

    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct="%1.1f%%", shadow=True, startangle=90, textprops={"fontsize": 11, "fontweight": "bold"})

    ax.set_title(f"Fixture Validation Summary\n{len(validation_results)} fixtures", fontsize=12, fontweight="bold")

    return ax


def plot_synthetic_comparison_panel(
    real_data: np.ndarray,
    synthetic_data: np.ndarray,
    test_results: Dict[str, Dict[str, Any]],
    validation_results: Dict[str, bool],
    label: str = "Value",
) -> plt.Figure:
    """Create multi-panel synthetic comparison figure.

    Creates a 2x2 panel with:
    - Top-left: Distribution comparison (KDE + histograms)
    - Top-right: Q-Q plot
    - Bottom-left: Statistical test results
    - Bottom-right: Fixture validation summary

    Args:
        real_data: Real data array
        synthetic_data: Synthetic data array
        test_results: Statistical test results
        validation_results: Fixture validation results
        label: Data label

    Returns:
        Matplotlib Figure object
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: Distribution comparison
    plot_distribution_comparison(real_data, synthetic_data, label, ax=axes[0, 0])

    # Top-right: Q-Q plot
    plot_qqplot(real_data, synthetic_data, label, ax=axes[0, 1])

    # Bottom-left: Statistical tests
    plot_statistical_test_results(test_results, ax=axes[1, 0])

    # Bottom-right: Fixture validation
    plot_fixture_validation_summary(validation_results, ax=axes[1, 1])

    fig.suptitle(f"Synthetic vs Real Data Comparison — {label}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_synthetic_comparison_figures(
    comparison_data: Union[Dict[str, Any], str, Path],
    output_dir: Union[str, Path],
    session_id: str = "unknown",
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all synthetic vs real comparison figures.

    Creates:
    - Multi-panel summary (distributions, Q-Q, tests, validation)
    - Per-modality comparison figures (pose, facemap, trials)

    Args:
        comparison_data: Dictionary with real/synthetic data or path to comparison JSON
        output_dir: Output directory for figures
        session_id: Session identifier for deterministic filenames
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Example:
        >>> comparison_data = {
        ...     'pose': {
        ...         'real': np.array([...]),
        ...         'synthetic': np.array([...]),
        ...         'tests': {'ks_test': {'p_value': 0.12}},
        ...         'validation': {'fixture_1': True, 'fixture_2': True}
        ...     },
        ...     'facemap': {...},
        ...     'trials': {...}
        ... }
        >>> paths = render_synthetic_comparison_figures(
        ...     comparison_data=comparison_data,
        ...     output_dir='reports/figures/synthetic',
        ...     session_id='synthetic-001'
        ... )
    """
    # Load data if path provided
    if isinstance(comparison_data, (str, Path)):
        import json

        with open(comparison_data, "r") as f:
            data = json.load(f)
            # Convert lists back to numpy arrays
            comparison_data = {}
            for modality, modality_data in data.items():
                comparison_data[modality] = {
                    "real": np.array(modality_data["real"]),
                    "synthetic": np.array(modality_data["synthetic"]),
                    "tests": modality_data.get("tests", {}),
                    "validation": modality_data.get("validation", {}),
                }

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # Generate figures for each modality
    for modality, modality_data in comparison_data.items():
        real_data = modality_data["real"]
        synthetic_data = modality_data["synthetic"]
        test_results = modality_data.get("tests", {})
        validation_results = modality_data.get("validation", {})

        # Multi-panel summary
        fig_summary = plot_synthetic_comparison_panel(real_data, synthetic_data, test_results, validation_results, label=modality.capitalize())
        filename_summary = make_deterministic_filename(session_id, "synthetic", f"{modality}_summary", ext=formats[0])
        paths_summary = save_figure(fig_summary, output_dir, filename_summary, formats=formats)
        saved_paths.extend(paths_summary)

        # Individual distribution comparison
        fig_dist, ax_dist = make_figure_grid(1, 1, figsize="wide")
        plot_distribution_comparison(real_data, synthetic_data, modality.capitalize(), ax=ax_dist)
        filename_dist = make_deterministic_filename(session_id, "synthetic", f"{modality}_distribution", ext=formats[0])
        paths_dist = save_figure(fig_dist, output_dir, filename_dist, formats=formats)
        saved_paths.extend(paths_dist)

    return saved_paths
