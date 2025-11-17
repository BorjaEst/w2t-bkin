"""Visualization module for behavioral events and trials (Bpod data).

Provides plotting functions for:
- Trial timelines (state sequences)
- Event raster plots
- Event histograms (response times, inter-event intervals)
- Condition-specific summaries

All functions consume Trials and Events domain models.
"""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from figures.utils import add_phase_annotation, ensure_output_dir, get_status_color, make_deterministic_filename, make_figure_grid, save_figure
from w2t_bkin.domain.trials import BehavioralEvents, Trial, TrialOutcome, TrialSummary

# ============================================================================
# Low-Level Plotting Functions
# ============================================================================


def plot_trial_raster(
    trials: List[Trial],
    max_trials: int = 50,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot trial raster showing start/stop times and outcomes.

    Args:
        trials: List of Trial objects
        max_trials: Maximum number of trials to display
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="wide")

    if not trials:
        ax.text(0.5, 0.5, "No trials available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Limit to max_trials
    trials_to_plot = trials[:max_trials]

    for trial in trials_to_plot:
        y = trial.trial_number
        duration = trial.stop_time - trial.start_time
        color = get_status_color(trial.outcome.value if hasattr(trial.outcome, "value") else str(trial.outcome))

        # Plot trial as horizontal bar
        ax.barh(y, duration, left=trial.start_time, height=0.8, color=color, alpha=0.7, edgecolor="black", linewidth=0.5)

    # Styling
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Trial Number", fontsize=11)
    ax.set_title(f"Trial Raster\n{len(trials)} trials ({len(trials_to_plot)} shown)", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="x")
    ax.set_ylim(0.5, len(trials_to_plot) + 0.5)

    # Add legend
    unique_outcomes = list(set(trial.outcome for trial in trials_to_plot))
    handles = [plt.Rectangle((0, 0), 1, 1, fc=get_status_color(str(o)), alpha=0.7) for o in unique_outcomes]
    ax.legend(handles, [str(o) for o in unique_outcomes], loc="upper right", fontsize=8)

    return ax


def plot_outcome_distribution(
    trials: List[Trial],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot distribution of trial outcomes.

    Args:
        trials: List of Trial objects
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not trials:
        ax.text(0.5, 0.5, "No trials available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Count outcomes
    outcome_counts = {}
    for trial in trials:
        outcome_str = trial.outcome.value if hasattr(trial.outcome, "value") else str(trial.outcome)
        outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

    # Sort by count
    sorted_outcomes = sorted(outcome_counts.items(), key=lambda x: x[1], reverse=True)
    outcomes = [o[0] for o in sorted_outcomes]
    counts = [o[1] for o in sorted_outcomes]
    colors = [get_status_color(o) for o in outcomes]

    # Plot bars
    bars = ax.bar(outcomes, counts, color=colors, alpha=0.8, edgecolor="black", linewidth=1)

    # Add count labels
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height, f"{count}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Styling
    ax.set_xlabel("Outcome", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title(f"Trial Outcome Distribution\nTotal: {len(trials)} trials", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    return ax


def plot_event_raster(
    events: BehavioralEvents,
    trials: Optional[List[Trial]] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot event raster showing event occurrences across trials.

    Args:
        events: BehavioralEvents object with timestamps and trial IDs
        trials: Optional list of Trial objects for context
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="wide")

    if not events.timestamps:
        ax.text(0.5, 0.5, f"No events: {events.name}", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Plot events
    if events.trial_ids is not None:
        # Plot as scatter with trial number on y-axis
        ax.scatter(events.timestamps, events.trial_ids, alpha=0.6, s=20, color="steelblue")
        ax.set_ylabel("Trial Number", fontsize=11)
    else:
        # Plot as vertical lines
        for ts in events.timestamps:
            ax.axvline(ts, alpha=0.3, color="steelblue", linewidth=0.5)
        ax.set_ylabel("Events", fontsize=11)
        ax.set_yticks([])

    # Styling
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_title(f"Event Raster: {events.name}\n{len(events.timestamps)} events", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)

    add_phase_annotation(ax, events.description, location="top-right")

    return ax


def plot_trial_duration_histogram(
    trials: List[Trial],
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot histogram of trial durations.

    Args:
        trials: List of Trial objects
        ax: Optional existing axes to plot on

    Returns:
        Matplotlib Axes object
    """
    if ax is None:
        fig, ax = make_figure_grid(1, 1, figsize="medium")

    if not trials:
        ax.text(0.5, 0.5, "No trials available", ha="center", va="center", transform=ax.transAxes)
        return ax

    # Calculate durations
    durations = [trial.stop_time - trial.start_time for trial in trials]

    # Plot histogram
    ax.hist(durations, bins=30, alpha=0.7, color="steelblue", edgecolor="black", linewidth=0.5)

    # Add mean line
    mean_duration = np.mean(durations)
    ax.axvline(mean_duration, color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_duration:.2f} s")

    # Styling
    ax.set_xlabel("Duration (s)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title(f"Trial Duration Distribution\nn={len(trials)}", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    return ax


def plot_events_summary_panel(
    trials: List[Trial],
    events_list: Optional[List[BehavioralEvents]] = None,
) -> plt.Figure:
    """Create multi-panel events summary figure.

    Creates a 2x2 panel with:
    - Top-left: Trial raster
    - Top-right: Outcome distribution
    - Bottom-left: Trial duration histogram
    - Bottom-right: Event raster (first event type if available)

    Args:
        trials: List of Trial objects
        events_list: Optional list of BehavioralEvents

    Returns:
        Matplotlib Figure object
    """
    fig, axes = make_figure_grid(2, 2, figsize="large")

    # Top-left: Trial raster
    plot_trial_raster(trials, ax=axes[0, 0])

    # Top-right: Outcome distribution
    plot_outcome_distribution(trials, ax=axes[0, 1])

    # Bottom-left: Trial duration histogram
    plot_trial_duration_histogram(trials, ax=axes[1, 0])

    # Bottom-right: Event raster (first event type)
    if events_list and len(events_list) > 0:
        plot_event_raster(events_list[0], trials, ax=axes[1, 1])
    else:
        axes[1, 1].text(0.5, 0.5, "No events available", ha="center", va="center", transform=axes[1, 1].transAxes)
        axes[1, 1].axis("off")

    session_id = "session" if not trials else f"{len(trials)} trials"
    fig.suptitle(f"Behavioral Events Summary — {session_id}", fontsize=14, fontweight="bold")
    fig.tight_layout()

    return fig


# ============================================================================
# High-Level Phase Rendering
# ============================================================================


def render_events_figures(
    trials_events: Union[tuple, str, Path],
    output_dir: Union[str, Path],
    session_id: str = "unknown",
    formats: tuple[str, ...] = ("png",),
) -> List[Path]:
    """Render all events/trials figures.

    Creates:
    - Multi-panel summary (raster, outcomes, durations, events)
    - Individual component figures

    Args:
        trials_events: Tuple of (trials, events_list) or path to events data JSON
        output_dir: Output directory for figures
        session_id: Session identifier for deterministic filenames
        formats: Output formats (e.g., ('png', 'pdf'))

    Returns:
        List of saved figure paths

    Example:
        >>> paths = render_events_figures(
        ...     trials_events=(trials_list, events_list),
        ...     output_dir='reports/figures/events',
        ...     session_id='SNA-145518'
        ... )
    """
    # Load objects if path provided
    if isinstance(trials_events, (str, Path)):
        import json

        with open(trials_events, "r") as f:
            data = json.load(f)
            trials = [Trial(**t) for t in data.get("trials", [])]
            events_list = [BehavioralEvents(**e) for e in data.get("events", [])]
    else:
        trials, events_list = trials_events if isinstance(trials_events, tuple) else (trials_events, [])

    output_dir = ensure_output_dir(output_dir)
    saved_paths = []

    # 1. Multi-panel summary
    fig_summary = plot_events_summary_panel(trials, events_list)
    filename_summary = make_deterministic_filename(session_id, "events", "summary", ext=formats[0])
    paths_summary = save_figure(fig_summary, output_dir, filename_summary, formats=formats)
    saved_paths.extend(paths_summary)

    # 2. Individual trial raster (larger)
    fig_raster, ax_raster = make_figure_grid(1, 1, figsize="wide")
    plot_trial_raster(trials, max_trials=len(trials), ax=ax_raster)
    filename_raster = make_deterministic_filename(session_id, "events", "raster", ext=formats[0])
    paths_raster = save_figure(fig_raster, output_dir, filename_raster, formats=formats)
    saved_paths.extend(paths_raster)

    # 3. Event rasters for each event type
    if events_list:
        for events in events_list[:5]:  # Limit to first 5 event types
            fig_event, ax_event = make_figure_grid(1, 1, figsize="wide")
            plot_event_raster(events, trials, ax=ax_event)
            event_name_safe = events.name.replace(" ", "_").replace("/", "_")
            filename_event = make_deterministic_filename(session_id, "events", f"raster_{event_name_safe}", ext=formats[0])
            paths_event = save_figure(fig_event, output_dir, filename_event, formats=formats)
            saved_paths.extend(paths_event)

    return saved_paths
