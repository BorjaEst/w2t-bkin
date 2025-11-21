---
post_title: "Design — W2T Body Kinematics Pipeline"
author1: "Project Team"
post_slug: "design-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "validation", "testing"]
tags: ["design", "architecture", "mermaid", "timebase", "nwb"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Technical architecture, domain model, timebase strategy, interfaces, and quality gates for a modular, CLI-first pipeline that produces NWB with rate-based ImageSeries and strict verification."
post_date: "2025-11-11"
---

## Overview

Concise architecture ensuring all Functional (FR) and Non-Functional (NFR) requirements are met with minimal surface area. Core themes: strict schemas, early verification, single reference timebase for derived data (ImageSeries always rate-based), deterministic/idempotent outputs, and pluggable optional stages.

**NWB-First Foundation**: This pipeline adopts NWB (Neurodata Without Borders) as its foundational data layer. All processing modules produce NWB-native data structures (PoseEstimation, TimeIntervals, TimeSeries) directly, eliminating intermediate models and conversion layers. This maximizes interoperability with neuroscience research centers and reduces codebase complexity.

## Scope

In scope: ingest → verify → (optional: transcode | pose | facemap | bpod) → align (timebase) → assemble NWB → validate → QC. Out of scope: calibration, triangulation, embedding raw videos internally.

## NWB Foundation Layer

This pipeline uses NWB as its foundational data layer rather than treating it as an export format.

**Benefits**:

- **Standards compliance**: Direct use of community-standard data types (PoseEstimationSeries, TimeIntervals, ImageSeries)
- **Interoperability**: All processing outputs compatible with NWB ecosystem tools across research centers
- **Simplified architecture**: Eliminates intermediate models (PoseBundle, FacemapBundle, TrialSummary) and conversion layers
- **Reduced testing**: Trust well-tested pynwb/ndx libraries; focus tests on usage patterns
- **Future exports**: Tools read NWB → convert to other formats (BIDS, JSON, CSV)

**Core dependencies (foundation layer)**:

- `pynwb~=3.1.0`: Base NWB data types (TimeSeries, TimeIntervals, NWBFile, ImageSeries)
- `hdmf~=4.1.0`: Hierarchical Data Modeling Framework underlying NWB
- `ndx-pose~=0.2.0`: Pose estimation extension (PoseEstimation, PoseEstimationSeries, Skeleton)
- `ndx-events~=0.4.0`: Behavioral events extension
- `ndx-structured-behavior~=0.1.0`: Trial structure extension

**Architecture Impact**: Processing modules (pose, facemap, events) import from pynwb/ndx packages and produce NWB objects directly. The nwb module becomes an assembly-only layer that aggregates pre-built NWB objects into a single file.

## Architecture (simplified)

**Key architectural constraints:**

- **Solid arrows** (→): direct module imports allowed
- **Dotted arrows** (-.→): orchestration layer calls with primitives only (no Session/Manifest passed)
- **Low-level** tools never import `config`, `Session`, or `Manifest`
- **Mid-level** tools never load TOML or know filesystem layout
- **High-level** is the only layer that understands session structure

Principles:

1. No cross-imports between sibling service packages.
2. Composition through files + NWB-native data structures.
3. Fail fast before heavy processing.
4. Sidecars for observability (verification, alignment, provenance, validation).
5. All outputs deterministic when inputs unchanged.
6. NWB data models (pynwb, ndx extensions) serve as foundational data layer across all processing modules.

## Layering and Module Responsibilities (target)

### Allowed Dependencies

**Foundation layer**: `pynwb`, `hdmf`, `ndx-*` extensions are foundational dependencies available to all layers.

- Low-level tools may depend on foundation layer (pynwb/ndx) + general utilities (e.g., `utils`). They produce NWB-native data structures. They MUST NOT depend on `config`, `Session`, `Manifest`, or any CLI/orchestration module.
- Mid-level tools may depend on low-level tools + foundation layer + shared utilities. They MUST NOT depend on `config`, `Session`, or TOML parsing.
- High-level orchestration (session-aware code) may depend on any lower layer. It is the ONLY layer that touches `config.toml`, `session.toml`, `Session`, or `Manifest`.

### Low-level tools (raw files, primitive options)

Low-level modules operate on raw files and simple arguments (e.g., glob patterns, sort order, ROI specs) and never see `Session` or `Manifest`. Modules produce NWB-native data structures directly.

| Module          | Key Input                                                 | Output / Contract                                       | FR/NFR Coverage        |
| --------------- | --------------------------------------------------------- | ------------------------------------------------------- | ---------------------- |
| utils           | primitives, file paths                                    | hashing, path safety, subprocess wrappers, logging      | NFR-1/2/3              |
| events.bpod     | Bpod `.mat` file paths, `order`, trial-type specs         | TimeIntervals (pynwb), parsed trial structures          | FR-11                  |
| events.trials   | parsed Bpod data, trial-type specs                        | TimeIntervals with trial metadata                       | FR-11/14               |
| dlc             | video file paths, model config path, GPU selection        | H5 pose files, inference results, batch processing      | FR-5, NFR-1/2 ✅       |
| pose            | pose result file paths, skeleton maps, frame/idx ranges   | PoseEstimation objects (ndx-pose), Skeleton definitions | FR-5                   |
| facemap         | video file paths, ROI specs, frame/idx ranges             | BehavioralTimeSeries (pynwb), motion energy traces      | FR-6                   |
| transcode       | input video file paths, codec/format options              | transcoded/mezzanine video file paths                   | FR-4, NFR-2            |
| sync.primitives | numeric sequences (timestamps, indices), timebase options | alignment indices/weights, jitter statistics            | FR-TB-1..6, FR-17, A17 |

**Note**: All neuroscience data outputs (pose, events, facemap) are NWB-native structures. Only infrastructure outputs (transcode paths, sync stats) remain as primitives or simple models.

Low-level APIs SHOULD offer arguments shaped to be easy to call from `Session` (e.g., `order="name_asc"`, glob patterns, TTL IDs), but must not accept `Session` instances directly.

### Mid-level tools (composition and timebase)

Mid-level modules compose low-level outputs and implement cross-cutting policies such as timebase selection, jitter budgets, and NWB layout. They also own their own models where needed (e.g., alignment stats).

| Module | Key Input                                                              | Output / Contract                                            | FR/NFR Coverage        |
| ------ | ---------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------- |
| sync   | timebase config (primitives), TTL timestamps, camera frame times       | alignment indices, alignment stats models, timebase provider | FR-TB-1..6, FR-17, A17 |
| nwb    | NWB objects from processing modules, camera/video metadata, provenance | Assembled NWBFile (aggregates pre-built NWB objects)         | FR-7 NFR-6             |

Mid-level tools operate on NWB objects and primitive values only. They never load TOML or know how files are laid out on disk for a session.

**Note**: The nwb module is assembly-only; it aggregates pre-built NWB objects (PoseEstimation, TimeIntervals, TimeSeries) into a single file. No data transformation or format conversion occurs at this layer.

### High-level orchestration (session-aware)

High-level modules understand `Config`, `Session`, and filesystem layout per session. They are responsible for wiring together low- and mid-level tools.

| Module        | Key Input                        | Output / Contract                                                                               | FR/NFR Coverage                  |
| ------------- | -------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------- |
| config        | `config.toml`, `session.toml`    | validated `Config`, `Session`, hashes                                                           | FR-10, FR-15, FR-TB-\* NFR-10/11 |
| ingest+verify | `Config`, `Session`              | discovered raw file paths, `Manifest` (internal), `verification_summary.json`                   | FR-1/2/3/13/15/16                |
| pipeline/cli  | `Config`, `Session`, CLI options | orchestrated runs: calls low-level tools with raw paths + options, calls `sync` and `nwb`, etc. | FR-1..7, FR-10/11, FR-17         |
| validate      | NWB                              | `validation_report.json` (nwbinspector report)                                                  | FR-9                             |
| qc            | NWB + sidecars                   | QC HTML                                                                                         | FR-8/14 NFR-3                    |

## Sidecar & Manifest Schemas (summary)

### Manifest (high-level orchestration model)

The `Manifest` model is **owned by the ingest layer** and treated as a
high-level orchestration artifact rather than a mid-level contract.
It is populated by the ingest module using a two-step workflow and
is never passed directly into low- or mid-level tools.

1. **Fast discovery** — `discover_files(config, session) → Manifest`

   - Resolves `config.paths.raw_root` and `session.session.id` into a session directory.
   - Discovers camera video files, TTL files, and Bpod files using glob patterns.
   - Populates `ManifestCamera.video_files`, `ManifestTTL.files`, and `Manifest.bpod_files`.
   - Leaves `frame_count` and `ttl_pulse_count` as `None` (no counting, O(n) in file count only).

2. **Slow counting** — `populate_manifest_counts(manifest) → Manifest`
   - Iterates over discovered TTL files and uses `count_ttl_pulses()` to build a map of
     `ttl_id → total_pulses`.
   - Iterates over all camera videos and uses `count_video_frames()` (ffprobe) to compute total
     frame counts per camera.
   - Returns a **new** `Manifest` with `frame_count`/`ttl_pulse_count` populated on each camera.

For convenience, `build_and_count_manifest(config, session)` performs both steps in one call.
It is a **high-level helper** and must only be used from orchestration code that already
owns `Config` and `Session`. Downstream stages (e.g., `sync`, `nwb`) receive primitive
metadata and module-local models derived from `Manifest`, not the `Manifest` itself.

### Sidecars

Sidecar artifacts (e.g., `verification_summary.json`, alignment stats, provenance,
validation reports) are produced by serializing module-local models to disk at
paths chosen by high-level orchestration. Low- and mid-level tools return
in-memory models; they DO NOT infer filesystem layout or write sidecars on
their own.

## Timebase Strategy (summary)

Provider (nominal|ttl|neuropixels) chosen via config; mapping strategy (nearest|linear) aligns
derived samples; jitter metrics (max, p95) compared to budget with abort prior to NWB if exceeded
per A17. ImageSeries timing remains rate-based and independent of timebase choice.

## Build Order & Dependencies

1. Foundation: pynwb, hdmf, ndx-\* extensions (available to all layers)
2. Utils, config (legacy `domain` models are transitional only)
3. Ingest+Verify (owns `Manifest` and other ingest-local models)
4. Sync (timebase + alignment, owns alignment/timebase models)
5. Optional modalities (transcode, pose, facemap, events) - produce NWB-native structures (PoseEstimation, TimeIntervals, TimeSeries)
6. NWB assembly (aggregates NWB objects, adds provenance, no conversion logic)
7. Validation + QC (operate on NWB + sidecar models, no direct knowledge of `Session`)

### Orchestration API (high-level entrypoints)

High-level orchestration is expected to converge on a small, explicit API
surface that owns `Config`, `Session`, and session layout. Example shapes:

- `run_session(config_path: str, session_id: str, options: RunOptions) → RunResult`

  - Loads `Config` and `Session`.
  - Builds and counts `Manifest`.
  - Calls low-level tools (events, pose, facemap, transcode) with raw file paths
    and primitive options derived from `Session`.
  - Low-level tools return NWB objects (PoseEstimation, TimeIntervals, TimeSeries).
  - Calls `sync` to select a timebase and compute alignment models.
  - Calls `nwb` to assemble the NWB file by aggregating pre-built NWB objects.
  - Serializes sidecar models (verification, alignment, provenance, validation) to
    disk at orchestrator-chosen locations.

- `run_validation(nwb_path: str) → ValidationReport`
  - Runs NWB validation (e.g., nwbinspector) as a mid-level utility invoked by
    orchestration.
  - Returns a module-local `ValidationReport` model that high-level code may
    serialize to `validation_report.json`.

## Provenance (determinism)

Canonicalization: strip comments → sort keys → compact JSON → SHA256. Record timebase selection
and jitter metrics. Ensures reproducibility (NFR-1) and traceability (FR-17, A18).
