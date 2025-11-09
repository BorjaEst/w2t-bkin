---
post_title: "API — Public Interfaces (W2T BKin)"
author1: "Project Team"
post_slug: "api-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "api"]
tags: ["api", "interfaces", "contracts"]
ai_note: "Generated from design and requirements; names-only, no code."
summary: "Public API specification listing modules, classes, functions, and globals with declared dependencies (no code)."
post_date: "2025-11-09"
---

<!-- markdownlint-disable MD041 -->

## API — Public Interfaces (W2T BKin)

## 1. Scope & Conventions

This document enumerates the public API of the W2T BKin pipeline based on the current design and
requirements. It lists modules, classes, functions, and globals, and states each item's dependencies
without including code. Signatures are described informally to avoid code blocks.

Conventions:

- Names refer to the `w2t_bkin` package under `src/`.
- Dependencies only include in-repo packages or domain contracts; external libraries are omitted.
- Items prefixed with "Optional" are used only when the corresponding feature is enabled.

## 2. Package Map

- Core foundations: `w2t_bkin.domain`, `w2t_bkin.utils` (no imports from other project packages)
- Configuration: `w2t_bkin.config`
- Processing stages (no cross-stage imports): `w2t_bkin.ingest`, `w2t_bkin.sync`, `w2t_bkin.transcode`,
  `w2t_bkin.pose`, `w2t_bkin.facemap`, `w2t_bkin.events`
- Assembly & reporting: `w2t_bkin.nwb`, `w2t_bkin.qc`
- Entry point: `w2t_bkin.cli`

## 3. Module APIs

### 3.1 Module: `w2t_bkin.domain`

Classes (data contracts):

- `VideoMetadata` — Fields: camera_id, path, codec, fps, duration, resolution
  - Depends on: none (primitive types only)
- `Manifest` — Fields: session_id, videos[], sync[], events[], pose[], facemap[], config_snapshot, provenance
  - Depends on: `VideoMetadata`
- `TimestampSeries` — Fields: frame_index[], timestamp_sec[]
  - Depends on: none
- `SyncSummary` — Fields: per_camera_stats, drift_stats, drop_counts, warnings
  - Depends on: none
- `PoseSample` — Fields: time, keypoint, x_px, y_px, confidence
  - Depends on: none
- `PoseTable` — Fields: records (list of `PoseSample`), skeleton_meta
  - Depends on: `PoseSample`
- `FacemapMetrics` — Fields: time[], metric_columns{ name → series }
  - Depends on: none
- `Trial` — Fields: trial_id, start_time, stop_time, phases, qc_flags
  - Depends on: none
- `Event` — Fields: time, kind, payload
  - Depends on: none
- `NWBAssemblyOptions` — Fields: link_external_video, file_name, session_description, lab, institution
  - Depends on: none
- `QCReportSummary` — Fields: sync_overview, pose_overview, facemap_overview, provenance
  - Depends on: none

Globals:

- None (contracts are class-based)

### 3.2 Module: `w2t_bkin.utils`

Functions (selected public helpers):

- `read_json(path)` / `write_json(path, obj)` — JSON IO helpers
  - Depends on: none (foundation module)
- `write_csv(path, rows)` — CSV writer for small tables
  - Depends on: none
- `file_hash(path)` — Content hash for caching/provenance
  - Depends on: none
- `get_commit()` — Git commit hash for provenance capture
  - Depends on: none
- `time_block(label)` — Context/utility for timing blocks
  - Depends on: none
- `configure_logging(level, structured=False)` — Basic logging setup
  - Depends on: none

Globals:

- None (utilities are function-based)

Dependencies:

- As a foundation module, `utils` must not import other project packages.

### 3.3 Module: `w2t_bkin.config`

Classes:

- `Settings` — Pydantic settings tree reflecting configuration keys in requirements
  - Depends on: `w2t_bkin.domain` (only for type hints where applicable) and `w2t_bkin.utils`

Functions:

- `load_settings(toml_path=None, env_prefix=None) -> Settings` — Load and validate settings
  - Depends on: `Settings`, `w2t_bkin.utils`

Globals:

- `ENV_PREFIX` — Default environment variable prefix

Dependencies:

- May import: `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.4 Module: `w2t_bkin.ingest`

Functions:

- `build_manifest(session_dir, config_source, output_dir) -> manifest_path`
  - Purpose: Discover inputs, collect video metadata, persist manifest.json
  - Depends on: `w2t_bkin.config.Settings`, `w2t_bkin.domain.Manifest`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.5 Module: `w2t_bkin.sync`

Functions:

- `compute_timestamps(manifest_path, output_dir, primary_clock=None) -> (timestamps_dir, SyncSummary)`
  - Purpose: Derive per-frame timestamps, drift and drop statistics
  - Depends on: `w2t_bkin.domain.TimestampSeries`, `w2t_bkin.domain.SyncSummary`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.6 Module: `w2t_bkin.transcode` (optional)

Functions:

- `transcode_videos(manifest_path, output_dir, codec=None) -> transcode_summary`
  - Purpose: Produce mezzanine videos and metadata
  - Depends on: `w2t_bkin.domain.VideoMetadata`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.7 Module: `w2t_bkin.pose` (optional)

Functions:

- `harmonize_pose(input_path, format, output_dir, skeleton_map=None) -> pose_table_path`
  - Purpose: Import/harmonize DLC or SLEAP outputs to canonical schema and timebase
  - Depends on: `w2t_bkin.domain.PoseTable`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.8 Module: `w2t_bkin.facemap` (optional)

Functions:

- `compute_facemap(face_video, output_dir, model_path=None) -> facemap_metrics_path`
  - Purpose: Compute or import facial metrics aligned to session timebase
  - Depends on: `w2t_bkin.domain.FacemapMetrics`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.9 Module: `w2t_bkin.events` (optional)

Functions:

- `normalize_events(input_paths, output_dir, schema="trials_events") -> events_outputs`
  - Purpose: Normalize NDJSON behavioral logs to Trials/Events tables
  - Depends on: `w2t_bkin.domain.Trial`, `w2t_bkin.domain.Event`, `w2t_bkin.utils`

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils`

### 3.10 Module: `w2t_bkin.nwb`

Functions:

- `assemble_nwb(manifest_path, timestamps_dir, output_dir, pose_dir=None, facemap_dir=None, events_dir=None, options=None) -> nwb_path`
  - Purpose: Assemble the NWB file using available artifacts and provenance
  - Depends on: `w2t_bkin.domain.NWBAssemblyOptions`, `w2t_bkin.utils`, file-based outputs of stages

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils` (must not import stage internals)

### 3.11 Module: `w2t_bkin.qc`

Functions:

- `generate_report(sync_summary, nwb_path, output_dir, pose_dir=None, facemap_dir=None) -> report_html_path`
  - Purpose: Render QC HTML report from stage summaries and NWB metadata
  - Depends on: `w2t_bkin.domain.SyncSummary`, `w2t_bkin.domain.QCReportSummary`, `w2t_bkin.utils`, NWB metadata

Globals:

- None

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.domain`, `w2t_bkin.utils` (must not import stage internals)

### 3.12 Module: `w2t_bkin.cli`

Commands (Typer-based):

- `ingest`, `sync`, `transcode`, `pose`, `infer`, `facemap`, `to-nwb`, `validate`, `report`
  - Purpose: Orchestrate per-stage operations and full sessions
  - Depends on: all stage public functions, plus `w2t_bkin.config`, `w2t_bkin.utils`

Globals:

- `app` — Typer application instance

Dependencies:

- May import: `w2t_bkin.config`, `w2t_bkin.utils`, `w2t_bkin.domain`, and public APIs of all stages

## 4. Dependency Summary (per module)

- `domain` — depends on: none
- `utils` — depends on: none
- `config` — depends on: `domain`, `utils`
- `ingest` — depends on: `config`, `domain`, `utils`
- `sync` — depends on: `config`, `domain`, `utils`
- `transcode` — depends on: `config`, `domain`, `utils`
- `pose` — depends on: `config`, `domain`, `utils`
- `facemap` — depends on: `config`, `domain`, `utils`
- `events` — depends on: `config`, `domain`, `utils`
- `nwb` — depends on: `config`, `domain`, `utils` (stage outputs via files/contracts only)
- `qc` — depends on: `config`, `domain`, `utils` (stage outputs via files/contracts only)
- `cli` — depends on: `config`, `domain`, `utils`, and stage public APIs

## 5. Notes

- Cross-stage imports are not permitted; dataflow between stages occurs via files and domain
  contracts. The `cli` module is the only entry point that may orchestrate multiple stages directly.
