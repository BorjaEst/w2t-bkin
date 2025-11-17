# Figures Package

**Location**: Root-level package (not inside `src/`)

Visualization and plotting tools for the W2T-BKIN pipeline.

## Overview

The `figures` package provides comprehensive visualization capabilities for inspecting data at every stage of the pipeline:

- **Raw data**: Video/TTL discovery, frame counts, verification status
- **Sync**: Timebase alignment, jitter diagnostics, budget compliance
- **Optional modalities**: Pose trajectories, facemap traces, behavioral events
- **Final outputs**: NWB sanity checks, validation summaries
- **Testing**: Synthetic vs real data comparisons

## Design Principles

1. **Read-only**: Only reads domain models, sidecars, and data files (never modifies them)
2. **Deterministic**: Same inputs always produce identical outputs
3. **Phase-aligned**: Organized by pipeline phases (ingest→sync→optionals→nwb)
4. **Layered APIs**: Low-level plot functions → phase entrypoints → session orchestrator
5. **Sidecar-driven**: Uses `verification_summary.json`, `alignment_stats.json`, etc.

## Package Structure

```
figures/
├── __init__.py              # Package root with high-level API exports
├── utils.py                 # Shared utilities (layout, styling, I/O)
├── session.py               # Session-level orchestration
├── ingest_verify.py         # Ingest/verification phase figures
├── sync.py                  # Timebase/alignment phase figures
├── pose.py                  # Pose estimation figures (stub)
├── facemap.py               # Facemap figures (stub)
├── events.py                # Behavioral events figures (stub)
├── nwb.py                   # Final NWB figures (stub)
└── synthetic.py             # Synthetic vs real comparisons (stub)
```

## Usage

### High-Level Session Overview

Render all available figures for a session:

```python
from figures import render_session_overview
from w2t_bkin.config import load_config, load_session

config = load_config('config.toml')
session = load_session('session.toml')

results = render_session_overview(
    config=config,
    session=session,
    outputs_root='data/interim',
    formats=('png', 'pdf')
)

print(f"Generated {sum(len(v) for v in results.values())} figures")
```

### Phase-Specific Rendering

Render figures for a specific pipeline phase:

```python
from figures import render_phase_figures

paths = render_phase_figures(
    phase='ingest',
    session_id='SNA-145518',
    outputs_root='data/interim',
    output_dir='reports/figures/ingest',
    formats=('png',)
)
```

Or use phase-specific functions directly:

```python
from figures import render_ingest_figures, render_sync_figures

# Ingest figures
ingest_paths = render_ingest_figures(
    manifest='data/interim/manifest.json',
    verification_summary='data/interim/verification_summary.json',
    output_dir='reports/figures/ingest',
    tolerance=1
)

# Sync figures
sync_paths = render_sync_figures(
    alignment_stats='data/interim/alignment_stats.json',
    output_dir='reports/figures/sync',
    jitter_budget_s=0.001
)
```

### Low-Level Plotting

Use low-level functions for custom visualizations:

```python
from figures.ingest_verify import plot_frame_vs_ttl_counts
from figures.utils import save_figure
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
plot_frame_vs_ttl_counts(manifest, verification_summary, tolerance=1, ax=ax)
save_figure(fig, 'reports/figures', 'custom_plot.png')
```

### In Notebooks

```python
# Interactive exploration
from figures.sync import plot_jitter_histogram
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))
plot_jitter_histogram(alignment_stats, jitter_budget_s=0.001, ax=ax)
plt.show()
```

## Module Responsibilities

| Module          | Purpose                                  | Status      |
| --------------- | ---------------------------------------- | ----------- |
| `utils`         | Shared layout, styling, I/O helpers      | ✅ Complete |
| `session`       | High-level session orchestration         | ✅ Complete |
| `ingest_verify` | Frame vs TTL, verification status        | ✅ Complete |
| `sync`          | Jitter histograms, alignment diagnostics | ✅ Complete |
| `pose`          | Skeleton overlays, trajectories          | 🚧 Stub     |
| `facemap`       | PC traces, ROI correlations              | 🚧 Stub     |
| `events`        | Trial timelines, event rasters           | 🚧 Stub     |
| `nwb`           | ImageSeries samples, validation overlays | 🚧 Stub     |
| `synthetic`     | Synthetic vs real comparisons            | 🚧 Stub     |

## API Contracts

### High-Level APIs

- `render_session_overview(config, session, outputs_root, ...) → Dict[str, List[Path]]`

  - Orchestrates all phase-specific renderers
  - Auto-discovers sidecars and data products
  - Returns map of phase → saved figure paths

- `render_phase_figures(phase, session_id, outputs_root, output_dir, ...) → List[Path]`
  - Convenience function for single-phase rendering
  - Supports: 'ingest', 'sync', 'pose', 'facemap', 'events', 'nwb'

### Phase-Specific APIs

Each phase module exports a `render_*_figures()` function:

- `render_ingest_figures(manifest, verification_summary, output_dir, ...) → List[Path]`
- `render_sync_figures(alignment_stats, output_dir, ...) → List[Path]`
- `render_pose_figures(pose_bundle, output_dir, ...) → List[Path]`
- `render_facemap_figures(facemap_bundle, output_dir, ...) → List[Path]`
- `render_events_figures(trials_events, output_dir, ...) → List[Path]`
- `render_nwb_figures(nwb_path, output_dir, ...) → List[Path]`

All accept:

- Domain objects or paths to JSON/NWB files
- `output_dir` for saved figures
- `formats` tuple (e.g., `('png', 'pdf')`)

### Utilities

- `make_figure_grid(nrows, ncols, figsize, ...) → (Figure, Axes)`
- `save_figure(fig, output_dir, filename, formats, ...) → List[Path]`
- `make_deterministic_filename(session_id, phase, data_type, ...) → str`
- `get_camera_color(camera_id) → str`
- `get_status_color(status) → str`
- `add_threshold_line(ax, threshold, ...)`
- `add_phase_annotation(ax, text, location, ...)`

## Output Structure

Figures are saved with deterministic filenames under phase-specific subdirectories:

```
reports/figures/
├── ingest/
│   ├── SNA-145518_ingest_counts.png
│   ├── SNA-145518_ingest_status.png
│   ├── SNA-145518_ingest_discovery.png
│   └── SNA-145518_ingest_cameras.png
├── sync/
│   ├── session_ttl_sync_alignment_summary.png
│   └── session_ttl_sync_jitter_vs_time.png
├── pose/
│   └── SNA-145518_pose_placeholder.png
├── facemap/
│   └── SNA-145518_facemap_placeholder.png
├── events/
│   └── SNA-145518_events_placeholder.png
└── nwb/
    └── SNA-145518_nwb_placeholder.png
```

## Requirements Coverage

| Requirement | Coverage                                  |
| ----------- | ----------------------------------------- |
| FR-8        | Visual QC and reporting                   |
| FR-14       | Multi-file support and session summaries  |
| NFR-3       | Observability through visual diagnostics  |
| NFR-1       | Deterministic outputs for reproducibility |

## Future Extensions

Stub modules (`pose`, `facemap`, `events`, `nwb`, `synthetic`) can be implemented with:

1. **Pose**: DLC/SLEAP skeleton overlays, per-joint trajectories, quality metrics
2. **Facemap**: PC/motSVD traces, ROI correlations, event-aligned averages
3. **Events**: Trial timelines, event rasters, response time distributions
4. **NWB**: ImageSeries spot checks, timeseries traces, validation overlays
5. **Synthetic**: Distribution comparisons, statistical tests, fixture validation

## Dependencies

- `matplotlib` (plotting backend)
- `numpy` (data manipulation)
- Domain models from `w2t_bkin.domain`

## Testing

Unit tests in `tests/unit/test_figures_*.py` will validate:

- Deterministic filename generation
- Figure creation without errors
- Proper handling of missing data
- Synthetic fixture visualizations

## Notes

- All plotting functions are **pure** (no global state)
- Figures are **closed automatically** after saving (can be disabled)
- **Deterministic coloring** ensures consistent visual identity per camera/phase
- **Sidecar JSON** files are the primary input (not internal state)
