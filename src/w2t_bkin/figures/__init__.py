"""Figures package: plotting helpers for pipeline diagnostics and analysis.

This package provides utilities for generating diagnostic plots and
profiling visualizations to understand pipeline execution and validate results.
"""


def configure_matplotlib_backend(backend: str = "Agg") -> None:
    """Configure matplotlib to use non-interactive backend for server environments.

    This should be called early in worker initialization, before any plotting occurs.
    Safe to call in interactive environments - will only set backend if not already set.

    Args:
        backend: Matplotlib backend to use (default: 'Agg' for non-interactive)
    """
    try:
        import matplotlib

        # Only set if not already configured to allow interactive use
        if matplotlib.get_backend() != backend:
            matplotlib.use(backend, force=False)
    except ImportError:
        pass  # matplotlib not installed, figures will be skipped


from w2t_bkin.figures.ecephys import plot_electrode_locations, plot_firing_rate_distribution, plot_spike_raster, plot_unit_quality_metrics
from w2t_bkin.figures.pose import plot_pose_keypoints_grid, plot_ttl_detection_from_pose
from w2t_bkin.figures.profiling import (
    PhaseProfile,
    PhaseTimer,
    PipelineProfile,
    plot_bpod_ttl_sync_residuals,
    plot_pipeline_execution,
    plot_sync_quality_and_completeness,
    plot_synchronization_stats,
    plot_trial_completeness,
    plot_ttl_inter_pulse_intervals,
)
from w2t_bkin.figures.sync import plot_alignment_example, plot_alignment_grid, plot_sync_recovery, plot_trial_offsets, plot_ttl_timeline

__all__ = [
    # Utilities
    "configure_matplotlib_backend",
    # Synchronization plots
    "plot_ttl_timeline",
    "plot_trial_offsets",
    "plot_alignment_example",
    "plot_alignment_grid",
    "plot_sync_recovery",
    # Pose plots
    "plot_ttl_detection_from_pose",
    "plot_pose_keypoints_grid",
    # Ecephys plots
    "plot_electrode_locations",
    "plot_spike_raster",
    "plot_firing_rate_distribution",
    "plot_unit_quality_metrics",
    # Profiling
    "PhaseProfile",
    "PhaseTimer",
    "PipelineProfile",
    "plot_pipeline_execution",
    "plot_synchronization_stats",
    # Enhanced diagnostics
    "plot_ttl_inter_pulse_intervals",
    "plot_sync_quality_and_completeness",
    # Deprecated (for backward compatibility)
    "plot_bpod_ttl_sync_residuals",
    "plot_trial_completeness",
]
