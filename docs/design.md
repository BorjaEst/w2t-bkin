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
- **Dotted arrows** (-.→): orchestration layer calls with primitives only (no Config models passed)
- **Low-level** tools never import `config` package or `config_loader`
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

- Low-level tools may depend on foundation layer (pynwb/ndx) + general utilities (e.g., `utils`). They produce NWB-native data structures. They MUST NOT depend on `config`, `config_loader`, or any CLI/orchestration module.
- Mid-level tools may depend on low-level tools + foundation layer + shared utilities. They MUST NOT depend on `config`, `config_loader`, or TOML parsing.
- High-level orchestration (session-aware code) may depend on any lower layer. It is the ONLY layer that touches `config.toml` and loads configuration models.

### Low-level tools (raw files, primitive options)

Low-level modules operate on raw files and simple arguments (e.g., glob patterns, sort order, ROI specs). Modules produce NWB-native data structures directly.

| Module          | Key Input                                                 | Output / Contract                                       | FR/NFR Coverage        |
| --------------- | --------------------------------------------------------- | ------------------------------------------------------- | ---------------------- |
| utils           | primitives, file paths                                    | hashing, path safety, subprocess wrappers, logging      | NFR-1/2/3              |
| bpod.code       | Bpod `.mat` file paths, `order`, trial-type specs         | Parsed Bpod data structures (raw dict format)           | FR-11                  |
| behavior        | parsed Bpod data, trial offsets                           | TaskRecording, TrialsTable (ndx-structured-behavior)    | FR-11/14               |
| dlc             | video file paths, model config path, GPU selection        | H5 pose files, inference results, batch processing      | FR-5, NFR-1/2 ✅       |
| pose            | pose result file paths, skeleton maps, frame/idx ranges   | PoseEstimation objects (ndx-pose), Skeleton definitions | FR-5                   |
| facemap         | video file paths, ROI specs, frame/idx ranges             | BehavioralTimeSeries (pynwb), motion energy traces      | FR-6                   |
| transcode       | input video file paths, codec/format options              | transcoded/mezzanine video file paths                   | FR-4, NFR-2            |
| sync.primitives | numeric sequences (timestamps, indices), timebase options | alignment indices/weights, jitter statistics            | FR-TB-1..6, FR-17, A17 |

**Note**: All neuroscience data outputs (pose, behavior, facemap) are NWB-native structures. Only infrastructure outputs (transcode paths, sync stats) remain as primitives or simple models.

Low-level APIs SHOULD offer arguments shaped to be easy to call from orchestration code (e.g., `order="name_asc"`, glob patterns, TTL IDs), but must not accept `Config` or configuration models directly.

### Mid-level tools (composition and timebase)

Mid-level modules compose low-level outputs and implement cross-cutting policies such as timebase selection, jitter budgets, and NWB layout. They also own their own models where needed (e.g., alignment stats).

| Module | Key Input                                                              | Output / Contract                                            | FR/NFR Coverage        |
| ------ | ---------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------- |
| sync   | timebase config (primitives), TTL timestamps, camera frame times       | alignment indices, alignment stats models, timebase provider | FR-TB-1..6, FR-17, A17 |
| events | TTL pulse timestamps (Dict[str, List[float]]), TTL descriptions        | EventsTable (ndx-events)                                     | FR-17                  |
| nwb    | NWB objects from processing modules, camera/video metadata, provenance | Assembled NWBFile (aggregates pre-built NWB objects)         | FR-7 NFR-6             |

Mid-level tools operate on NWB objects and primitive values only. They never load TOML or know how files are laid out on disk for a session.

**Note**: The nwb module is assembly-only; it aggregates pre-built NWB objects (PoseEstimation, TimeIntervals, TimeSeries) into a single file. No data transformation or format conversion occurs at this layer.

### High-level orchestration (session-aware)

High-level modules understand `Config` models, NWBFile, and filesystem layout per session. They are responsible for wiring together low- and mid-level tools.

| Module        | Key Input                      | Output / Contract                                                                        | FR/NFR Coverage                  |
| ------------- | ------------------------------ | ---------------------------------------------------------------------------------------- | -------------------------------- |
| config        | N/A                            | Pydantic config models (Config, PathsConfig, TimebaseConfig, etc.)                       | FR-10, FR-15, FR-TB-\* NFR-10/11 |
| config_loader | `config.toml`                  | validated `Config` instances, content hashing                                            | FR-10, FR-15, FR-TB-\* NFR-10/11 |
| session       | `Config`, metadata             | NWBFile creation, video acquisition helpers, NWB file writing                            | FR-7, NFR-6                      |
| pipeline/cli  | `Config`, NWBFile, CLI options | orchestrated runs: inline file discovery, calls low-level tools with raw paths + options | FR-1..7, FR-10/11, FR-17         |
| validate      | NWB                            | `validation_report.json` (nwbinspector report)                                           | FR-9                             |
| qc            | NWB + sidecars                 | QC HTML                                                                                  | FR-8/14 NFR-3                    |

## Sidecar Schemas (summary)

### NWB-First Discovery (high-level orchestration)

File discovery and verification are **inlined in the pipeline orchestration** (pipeline.py).
The pipeline creates an NWBFile early (Phase 0) and populates it incrementally throughout
processing phases. No intermediate Manifest model exists.

**Discovery workflow** (inlined in `pipeline.run_session()`):

1. **Phase 0: Create NWBFile** — `create_nwb_file(session_path) → NWBFile`

   - Creates NWBFile from session.toml metadata
   - Populates subject, devices, and required metadata
   - Returns in-memory NWBFile ready for acquisition data

2. **Phase 1: Discover and verify** — inline in pipeline

   - Uses `discover_files(base_dir, pattern)` to find camera videos and TTL files
   - Uses `count_video_frames(video_path)` and `count_ttl_pulses(ttl_path)` for counts
   - Performs inline verification: compares frame_count vs ttl_pulse_count
   - Calls `add_video_acquisition(nwbfile, camera_id, video_files)` to add ImageSeries
   - Tracks discovered files in `discovered_cameras` list for downstream use

3. **Phase 5: Write NWBFile** — `write_nwb_file(nwbfile, output_path) → Path`
   - Embeds provenance in `nwbfile.notes` (JSON string)
   - Writes complete NWBFile to disk using NWBHDF5IO
   - Returns path to written file

Downstream stages receive NWBFile directly or primitive metadata extracted from discovered files.
No Manifest object is passed between stages.

### Sidecars

Sidecar artifacts (e.g., alignment stats, validation reports) are produced by serializing
module-local models to disk at paths chosen by high-level orchestration. Provenance is
embedded directly in `nwbfile.notes` (JSON string). Low- and mid-level tools return
in-memory models; they DO NOT infer filesystem layout or write sidecars on their own.

## Timebase Strategy (summary)

Provider (nominal|ttl|neuropixels) chosen via config; mapping strategy (nearest|linear) aligns
derived samples; jitter metrics (max, p95) compared to budget with abort prior to NWB if exceeded
per A17. ImageSeries timing remains rate-based and independent of timebase choice.

## Build Order & Dependencies

1. Foundation: pynwb, hdmf, ndx-\* extensions (available to all layers)
2. Utils, config package (15 Config models), config_loader (TOML loading + hashing)
3. Session module (NWBFile creation, video acquisition, NWB writing)
4. Sync (timebase + alignment, owns AlignmentStats model)
5. Optional modalities (transcode, pose, facemap, bpod, behavior) - produce NWB-native structures (PoseEstimation, TimeIntervals, TimeSeries, TaskRecording)
6. Pipeline orchestration (inlines file discovery, creates NWBFile early, coordinates processing)
7. Validation + QC (operate on NWB + sidecar models)

### Orchestration API (high-level entrypoints)

High-level orchestration is expected to converge on a small, explicit API
surface that owns `Config`, `Session`, and session layout. Example shapes:

- `run_session(config_path: str, session_id: str, options: RunOptions) → RunResult`

  - Loads `Config` and `Session`.
  - Creates NWBFile early via `create_nwb_file(session_path)`.
  - Inlines file discovery using `discover_files()`, `count_video_frames()`, `count_ttl_pulses()`.
  - Performs inline verification: compares frame counts vs TTL pulse counts.
  - Adds video acquisition to NWBFile via `add_video_acquisition()`.
  - Calls low-level tools (bpod, behavior, pose, facemap, transcode) with raw file paths
    and primitive options derived from `Session`.
  - Low-level tools return NWB objects (PoseEstimation, TimeIntervals, TimeSeries, TaskRecording).
  - Calls `sync` to select a timebase and compute alignment models.
  - Adds all NWB objects to the in-memory NWBFile.
  - Embeds provenance in `nwbfile.notes` and writes to disk via `write_nwb_file()`.
  - Serializes sidecar models (alignment stats, validation reports) to disk at orchestrator-chosen locations.
  - Returns `RunResult` with `nwbfile: NWBFile` and `nwb_path: Path`.

- `run_validation(nwb_path: str) → ValidationReport`
  - Runs NWB validation (e.g., nwbinspector) as a mid-level utility invoked by
    orchestration.
  - Returns a module-local `ValidationReport` model that high-level code may
    serialize to `validation_report.json`.

## Provenance (determinism)

Canonicalization: strip comments → sort keys → compact JSON → SHA256. Record timebase selection
and jitter metrics. Ensures reproducibility (NFR-1) and traceability (FR-17, A18).
