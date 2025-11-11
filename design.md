---
post_title: "Design — Modular Architecture (W2T BKin)"
author1: "Project Team"
post_slug: "design-modular-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pipeline", "docs", "nwb"]
tags: ["design", "architecture", "modular"]
ai_note: "Draft produced with AI assistance, reviewed by maintainers."
summary: "Modular technical design for a multi-stage behavioral data pipeline producing NWB with hardware-based frame sync verification (no software timestamp sync), pose, facial metrics, and QC."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## 1. Architectural Overview

The system is a multi-stage, configuration-driven pipeline organized into modular Python packages.
Each stage operates independently, consuming a manifest and producing deterministic artifacts. No
camera calibration or 3D fusion is performed. Hardware guarantees frame-timing alignment; software
only verifies invariants (frame counts vs TTL pulse counts) and does not compute per-frame
timestamps.

## 2. Module Breakdown

| Package                    | Responsibility                                                   | Key Inputs                    | Key Outputs                     |
| -------------------------- | ---------------------------------------------------------------- | ----------------------------- | ------------------------------- |
| `config`                   | Load/validate TOML, provide typed settings                       | TOML env vars                 | Settings objects                |
| `ingest`                   | Discover session assets, extract video metadata, build manifest  | Raw files, settings           | `manifest.json`                 |
| (verification in `ingest`) | Verify frame counts against TTL pulses; record mismatches        | TTL logs, manifest            | `verification_summary.json`     |
| `transcode`                | Optional mezzanine encoding                                      | Raw videos, settings          | Transcoded videos + metadata    |
| `pose`                     | Import/harmonize DLC/SLEAP outputs, skeleton mapping             | Pose files/models             | Harmonized pose tables          |
| `facemap`                  | Import/compute facial metrics and align timestamps               | Face video, models            | Metrics table + metadata        |
| `bpod`                     | Parse MATLAB Bpod .mat behavioral file into Trials/Events tables | Bpod .mat file                | Normalized events, trials table |
| `nwb`                      | Assemble NWB file with all available data & provenance           | Manifest, stage outputs       | `session_id.nwb`                |
| `qc`                       | Render HTML QC report                                            | Stage summaries, NWB metadata | `index.html`                    |
| `cli`                      | Typer application exposing subcommands                           | Settings                      | User-facing CLI                 |
| `utils`                    | Shared helpers (I/O, hashing, timing)                            | Internal calls                | Reusable primitives             |

## 3. Data Contracts

### 3.00 Config (TOML) — Strict Schema

The pipeline-level configuration file MUST contain exactly the following sections and keys (no additional or missing keys):

- `[project]`: `name`
- `[paths]`: `raw_root`, `intermediate_root`, `output_root`, `metadata_file`, `models_root`
- `[acquisition]`: `concat_strategy`
- `[verification]`: `mismatch_tolerance_frames`, `warn_on_mismatch`
- `[bpod]`: `parse`
- `[video.transcode]`: `enabled`, `codec`, `crf`, `preset`, `keyint`
- `[nwb]`: `link_external_video`, `lab`, `institution`, `file_name_template`, `session_description_template`
- `[qc]`: `generate_report`, `out_template`, `include_verification`
- `[logging]`: `level`, `structured`
- `[labels.dlc]`: `run_inference`, `model`
- `[labels.sleap]`: `run_inference`, `model`
- `[facemap]`: `run_inference`, `ROIs`

Notes:

- NWB uses rate-based ImageSeries by design; there is no `image_series_timing` toggle in config.
- QC toggles include `include_verification`; there is no `include_bpod` flag at config level.

### 3.0 Session Metadata (TOML)

The session file MUST contain exactly the following sections and keys (no additional or missing keys):

- `[session]`: `id`, `subject_id`, `date`, `experimenter`, `description`, `sex`, `age`, `genotype`
- `[bpod]`: `path`, `order`
- `[[TTLs]]`: `id`, `description`, `paths`
- `[[cameras]]`: `id`, `description`, `paths`, `order`, `ttl_id`

Notes:

- `order` specifies file selection/sorting policy (e.g., `name_asc`).
- All `paths` are glob patterns resolved relative to the session directory under `paths.raw_root`.

### 3.1 Manifest (JSON)

Fields: `session_id`, `videos[{camera_id,path,codec,fps,frame_count,duration,resolution,ttl_id?}]`,
`ttls[{id,path,role}]`, `bpod{path?}`, `pose[{path,format}]`, `facemap[{path}]`, `config_snapshot`, `provenance`.
Invariant: All paths absolute; optional resources are omitted rather than null.

### 3.2 Verification Summary JSON

Fields: `per_camera[{camera_id, video_frame_count, ttl_pulse_count, mismatch, ratio}]`,
`warnings[]`, `notes`, `timing`. Invariant: `mismatch = video_frame_count - ttl_pulse_count`.

### 3.3 Pose Harmonized Table (Parquet preferred)

Columns: `time`, `keypoint`, `x_px`, `y_px`, `confidence`, plus metadata sidecar JSON with skeleton
and model hashes. Primary key: (`time`,`keypoint`).

### 3.4 Facemap Metrics

Wide table: `time` + metric columns (e.g., `pupil_area`, `motion_energy`). Missing samples preserved
as NaN.

### 3.5 Trials Table

Columns: `trial_id`, `start_time`, `stop_time`, `phase_first`, `phase_last`, `declared_duration`,
`observed_span`, `duration_delta`, `qc_flags`.

### 3.6 QC Summary JSON

Sections: `verification`, `pose`, `facemap`, `bpod`, `provenance`, each with minimal stats + file
references.

## 4. Interfaces & Public APIs

Example (Typer CLI and Python import use):

Inputs conform to domain contracts; outputs are domain objects or file paths. No public API for
computing timestamps exists; verification is part of ingestion.

Function contract pattern:

- Inputs: Typed dataclasses / pydantic models (avoid raw dicts)
- Outputs: Tuple of domain objects + summary dataclass

## 5. Processing Flow

1. `config` loads settings → passed to `ingest`.
2. `ingest` builds `manifest.json`.
3. `ingest` verifies video frame counts vs TTL pulses → `verification_summary.json`.
4. `transcode` (optional) produces stable video derivatives (manifest extended with mezzanine refs).
5. `pose` / `facemap` import or compute features aligning to session timebase (fps-based).
6. `bpod` derives Trials/Events if present.
7. `nwb` assembles NWB; uses rate-based ImageSeries (starting_time + rate) with external_file links;
   stores provenance.
8. `validate` (subcommand) runs nwbinspector.
9. `qc` renders HTML from summaries.

## 6. Error Handling Strategy

| Error Class                | Cause                     | Response                                                  |
| -------------------------- | ------------------------- | --------------------------------------------------------- |
| MissingInputError          | Required file absent      | Fail fast, log path, suggest config key                   |
| FrameTtlCountMismatchError | Video frames ≠ TTL pulses | Abort ingestion unless policy allows; include diagnostics |
| DataIntegrityWarning       | Gaps/NaNs beyond expected | Proceed, mark in QC flags                                 |
| ConfigValidationError      | Invalid TOML field        | Abort before any stage runs                               |

All exceptions subclass a base `PipelineError` for central logging.

## 7. Logging & Diagnostics

- Structured JSON logs optional via config toggle.
- Each stage writes `{stage}_summary.json` with machine-readable stats.
- Include timing (wall + CPU), memory (approx), input counts, anomaly flags.

## 8. Performance Considerations

- Use streaming parsing for large TTL logs (iterators). Avoid loading entire video into memory.
- Parallelization: per-camera verification and optional transcode; pose/facemap inference on separate threads or processes.
- Optional caching: hashed raw file + config snapshot to skip recomputation.

## 9. Testing Strategy

- Unit tests: verification math (frame and TTL counters), skeleton mapping.
- Integration tests: miniature session pipeline end-to-end (synthetic 10-frame videos + mock TTL).
- CLI tests: invoke subcommands with temp directory; assert artifact presence.
- Property tests (optional): invariants (monotonic timestamps, confidence in [0,1]).

## 10. Modularity & Extensibility

- New stages added by creating a subpackage and registering a CLI subcommand in `cli/app.py`.
- Clear separation: no stage imports another stage's internals; only shared contracts from `utils` or `domain`.
- Domain models shared in `domain` subpackage (to be created) for types like `VideoMetadata`, `TimestampSeries`.

## 11. Provenance Capture

- Config snapshot (TOML serialized) stored in NWB `notes` or a `/processing/provenance` module.
- Git commit hash via `utils.git.get_commit()`.
- Dependency versions subset (`pip freeze` filtered) saved alongside QC summary.

## 12. Security & Privacy

- Absolute paths stored only in local artifacts; NWB uses relative paths when feasible.
- Subject identifiers anonymized; no facial images embedded.

## 13. Quality Gates

- Build: import all subpackages without ImportError.
- Lint: ruff passes (style + basic issues).
- Types: mypy passes with strict optional checks for core modules.
- Validate: nwbinspector no critical errors.
- QC: per-camera frame/TTL mismatch ≤ configured tolerance; pose/facemap quality within expected ranges.

## 14. Future Enhancements (Backlog)

-- Vectorized mismatch visualization improvements.

- Incremental re-run: stage-level dependency graph with minimal recomputation.
- Plugin system for custom behavioral event derivations.
- Streaming NWB writing for very large sessions.

## 15. Glossary (Selected)

- Mezzanine: normalized transcoded copy optimized for seeking.
- Harmonization: mapping heterogeneous pose outputs to canonical schema.

## 16. Decision Records Placeholder

Decision records will be stored under `docs/decisions/` following the project template.

## 17. Sequence Example (Text Diagram)

```text
config → ingest → manifest.json
manifest + TTL logs → ingest (verify) → verification_summary
videos (+ optional transcode) → transcode → mezzanine/*
pose raw → pose → pose_harmonized.parquet
facemap raw → facemap → facemap_metrics.parquet
bpod .mat → bpod → trials.csv + events.csv
all artifacts → nwb → session.nwb
session.nwb → validate → nwbinspector.json
summaries → qc → index.html
```

## 18. Directory Conventions (Refined)

| Path                             | Purpose                       |
| -------------------------------- | ----------------------------- |
| `data/raw/<session>`             | Original videos and logs      |
| `data/interim/<session>/verify`  | Verification summary (JSON)   |
| `data/interim/<session>/pose`    | Harmonized pose tables        |
| `data/interim/<session>/facemap` | Facial metrics                |
| `data/interim/<session>/bpod`    | Bpod-derived events/trials    |
| `data/interim/<session>/video`   | Mezzanine videos              |
| `data/processed/<session>`       | Final NWB + validation report |
| `data/qc/<session>`              | QC HTML & assets              |

## 19. Validation Checklist

- Video frame counts equal TTL pulse counts per camera.
- Pose confidence median within expected range.
- Trials non-overlapping; flagged mismatches documented.
- NWB passes inspector.

## 20. Summary Sentence

The modular architecture cleanly partitions ingestion, verification, transformation, packaging,
validation, and reporting into isolated, testable Python subpackages producing reproducible NWB
datasets with transparent quality metrics.

## 21. Package Dependency Tree

This section defines the code-level import dependencies and the runtime/dataflow dependencies between
packages. It enforces a layered architecture with no cyclic dependencies and no cross-stage imports.

### 21.1 Code-level Import Layers (Allowable Imports Only)

- Layer 0 — Foundations (no imports between them):
  - `utils` (helpers only; does not import any stage)
  - `domain` (pure types and contracts; does not import any other project package)
- Layer 1 — Configuration:
  - `config` → may import: `domain`, `utils`
- Layer 2 — Processing Stages (parallel, must not import each other):
  - `ingest` → may import: `config`, `domain`, `utils`
  - `transcode` → may import: `config`, `domain`, `utils`
  - `pose` → may import: `config`, `domain`, `utils`
  - `facemap` → may import: `config`, `domain`, `utils`
  - `bpod` → may import: `config`, `domain`, `utils`
- Layer 3 — Assembly & Reporting:
  - `nwb` → may import: `config`, `domain`, `utils` (must not import stage internals)
  - `qc` → may import: `config`, `domain`, `utils` (must not import stage internals)
- Layer 4 — Entry Points:
  - `cli` → may import: `config`, `utils`, `domain`, and each stage package's public APIs

Import constraints:

- No stage imports another stage's internals (e.g., `pose` ✗→ `sync`, `events` ✗→ `pose`).
- `domain` and `utils` are import-only roots and must not import project packages.
- `nwb` and `qc` consume outputs via contracts/IO and must not import stage internals.
- `cli` is the only package allowed to depend on all stages for orchestration.

For quick reference, an allowable import tree (arrows point to what a package may import):

```text
utils        domain
  ↑            ↑
   \          /
    -> config
          ↑
   ┌──────┼────────────────────────────────────────────┐
   │      │        │         │       │         │       │
 ingest       transcode   pose   facemap   bpod        │
   ↑           ↑         ↑       ↑        ↑            │
    \__________|_________|_______|________|___________/
                          |
                        nwb, qc
                          ↑
                          |
                         cli
```

### 21.2 Runtime/Dataflow Dependencies (Artifacts)

The dataflow/DAG describes which stage outputs are consumed by others at runtime (not imports):

- `config` → provides settings to all stages.
- `ingest` → produces `manifest.json` and `verification_summary.json` consumed by `nwb`, `qc`, and referenced by other stages for provenance.
- `transcode` (optional) → produces mezzanine videos referenced by `nwb`.
- `pose` (optional) → produces harmonized pose tables consumed by `nwb`, summarized by `qc`.
- `facemap` (optional) → produces metrics consumed by `nwb`, summarized by `qc`.
- `bpod` (optional) → produces normalized trials/events consumed by `nwb`, summarized by `qc`.
- `nwb` → produces the NWB file and may embed provenance/snapshots; its inspector report feeds `qc`.
- `qc` → renders HTML from all stage summaries and NWB metadata.

Notes:

- Dataflow dependencies do not mandate import dependencies; they are connected via files/contracts.
- Parallelism: Layer 2 stages can run independently once `config`/`ingest` have produced inputs.
