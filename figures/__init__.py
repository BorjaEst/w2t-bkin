"""Visualization and plotting package for W2T-BKIN pipeline.

This package provides visualization tools for inspecting raw, synthetic, processed,
and final NWB data at every stage of the pipeline. All plotting functions consume
domain models and sidecar JSON files, respecting the no-cross-import principle.

Package Structure:
-----------------
- utils: Shared utilities (layout, styling, I/O, deterministic filenames)
- session: High-level session overview dashboard orchestrator
- ingest_verify: Visualizations for manifest, counts, verification summaries
- sync: Timebase alignment, jitter diagnostics, timeline overlays
- pose: Pose estimation QC (trajectories, skeleton overlays, quality metrics)
- facemap: Facemap timeseries, distributions, correlations
- events: Bpod/trial/event timelines, rasters, histograms
- nwb: Final NWB sanity checks and spot-check visualizations
- synthetic: Synthetic vs real data comparisons for testing

Design Principles:
------------------
1. **Read-only**: Only reads domain models, sidecars, and data files
2. **Deterministic**: Same inputs always produce identical outputs
3. **Phase-aligned**: Organized by pipeline phases (ingest→sync→optionals→nwb)
4. **Layered APIs**: Low-level plot functions → phase entrypoints → session orchestrator
5. **Sidecar-driven**: Uses verification_summary.json, alignment_stats.json, etc.

Key Features:
-------------
- **Session-level dashboards**: Multi-panel overviews linking all phases
- **Phase-specific QC**: Targeted diagnostics per pipeline stage
- **Modality-specific plots**: Pose, facemap, events, etc.
- **Synthetic validation**: Visual comparisons for test fixtures
- **CLI and notebook integration**: Reusable from scripts and interactive environments

Import Patterns:
---------------
# High-level session API
from figures import render_session_overview

# Phase-specific rendering
from figures.ingest_verify import render_ingest_figures
from figures.sync import render_sync_figures
from figures.pose import render_pose_figures

# Low-level plotting utilities
from figures.utils import save_figure, make_figure_grid

Requirements Coverage:
---------------------
- FR-8: Visual QC and reporting
- FR-14: Multi-file support and session summaries
- NFR-3: Observability through visual diagnostics
- NFR-1: Deterministic outputs for reproducibility

Acceptance Criteria:
-------------------
- All plotting functions accept domain models or sidecar paths
- Deterministic filenames based on session_id, camera_id, data_type, phase
- No modification of manifests, NWB files, or domain objects
- All outputs saved under reports/figures/ with phase-based subdirectories
"""

__version__ = "0.0.1"
__all__ = [
    # High-level API
    "render_session_overview",
    "render_phase_figures",
    # Phase-specific rendering
    "render_ingest_figures",
    "render_sync_figures",
    "render_pose_figures",
    "render_facemap_figures",
    "render_events_figures",
    "render_nwb_figures",
    # Utilities
    "save_figure",
    "make_figure_grid",
]

from figures.events import render_events_figures
from figures.facemap import render_facemap_figures
from figures.ingest_verify import render_ingest_figures
from figures.nwb import render_nwb_figures
from figures.pose import render_pose_figures

# Import high-level APIs for convenience
from figures.session import render_phase_figures, render_session_overview
from figures.sync import render_sync_figures
from figures.utils import make_figure_grid, save_figure
