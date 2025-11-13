---
post_title: "Requirements — W2T Body Kinematics Pipeline (Design Phase)"
author1: "Project Team"
post_slug: "requirements-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "validation", "testing"]
tags: ["requirements", "EARS", "design-phase"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Functional and non-functional requirements in EARS notation for a modular multi-camera behavioral pipeline producing NWB with hardware-based frame timing (no software timestamp sync stage)."
post_date: "2025-11-08"
---

## Overview

The pipeline transforms multi-camera behavioral recordings plus timing and event logs into a
validated NWB dataset. The following requirements reflect a clean-slate design-phase view with a
modular architecture and a CLI-first user experience.

## Functional Requirements (EARS)

- FR-1 — Ubiquitous: THE SYSTEM SHALL ingest all camera video files declared for the session and
  discover the associated TTL pulse log files and the Bpod behavioral file via the session TOML.
- FR-2 — Event-driven: WHEN ingestion completes, THE SYSTEM SHALL verify that each camera's video
  frame count equals the corresponding TTL pulse count and record a mismatch value.
- FR-3 — Unwanted behavior: IF any camera exhibits a frame/TTL mismatch strictly greater than
  `verification.mismatch_tolerance_frames`, THEN THE SYSTEM SHALL abort ingestion with a diagnostic
  summary (counts, deltas, camera_id, ttl_id).
- FR-4 — Optional: WHERE transcoding is enabled in configuration, THE SYSTEM SHALL transcode videos
  to a mezzanine format; OTHERWISE THE SYSTEM SHALL operate directly on raw videos.
- FR-5 — Optional: WHERE pose results from DeepLabCut and/or SLEAP are supplied, THE SYSTEM SHALL
  import and harmonize them to a canonical skeleton and the session reference timebase, preserving
  confidence scores.
- FR-6 — Optional: WHERE Facemap inputs are supplied or enabled, THE SYSTEM SHALL import or compute
  facial metrics and align them to the session reference timebase using frame index mapping.
- FR-7 — Ubiquitous: THE SYSTEM SHALL export one NWB file per session containing: Devices for all
  declared cameras; one ImageSeries per camera with external_file links and rate-based timing by
  default (no per-frame timestamp arrays); ndx-pose containers for pose (if present); and
  BehavioralTimeSeries for Facemap metrics (if present). ImageSeries remain rate-based regardless of
  timebase source; timebase choice affects alignment of derived data only.
- FR-8 — Ubiquitous: THE SYSTEM SHALL generate a QC HTML report summarizing verification results
  (frame vs TTL counts), pose confidence distributions, and Facemap signal previews.
- FR-9 — Ubiquitous: THE SYSTEM SHALL validate the NWB output with nwbinspector and persist its
  report alongside the NWB file.
- FR-10 — Ubiquitous: THE SYSTEM SHALL be configuration-driven via TOML validated by Pydantic
  models with environment overrides.
- FR-11 — Optional: WHERE a Bpod MATLAB .mat file is present, THE SYSTEM SHALL parse it into a
  Trials TimeIntervals table and TrialEvents without using it for video timing.
- FR-12 — Ubiquitous (modularity): THE SYSTEM SHALL organize implementation into modular Python
  subpackages with clear contracts and minimal coupling. Package boundaries MAY align with
  configuration groups where practical (e.g., labels/pose), and naming MAY evolve as the design
  matures. Cross-stage imports remain prohibited; composition occurs via files and domain contracts.
- FR-13 — Ubiquitous: THE SYSTEM SHALL persist a `verification_summary.json` capturing per-camera
  counts and mismatches.
- FR-14 — Optional: WHERE a Bpod .mat file is present, THE SYSTEM SHALL include trial/event summaries
  in the QC report.
- FR-15 — Ubiquitous: THE SYSTEM SHALL validate that each declared camera references an existing
  `ttl_id` from the session TOML; cameras without a match are flagged as unverifiable with a warning.
- FR-16 — Ubiquitous: IF a camera's mismatch is ≤ `verification.mismatch_tolerance_frames`, THE SYSTEM
  SHALL proceed; WHERE `verification.warn_on_mismatch=true` it SHALL log a warning, OTHERWISE it SHALL
  remain silent.
- FR-17 — Ubiquitous: THE SYSTEM SHALL persist the chosen `timebase_source` and any synthesis
  assumptions inside provenance per FR-TB-5.

## Non-Functional Requirements (NFR)

- NFR-1 — Reproducibility: Given identical inputs/configuration, artifacts SHALL be identical where
  feasible (external tool nondeterminism excepted).
- NFR-2 — Idempotence: Re-running a stage without input changes SHALL be a no-op unless forced.
- NFR-3 — Observability: Each stage SHALL emit structured logs and a JSON summary (e.g.,
  verification_summary.json) to support QC and debugging.
- NFR-4 — Performance: A typical one-hour session SHOULD complete within practical lab
  time budgets; compute-heavy steps SHOULD support parallelization; verification MUST be O(n) over
  frame counts without per-frame timestamp generation.
- NFR-5 — Portability: The pipeline SHALL run on Linux and macOS; Windows is best-effort.
- NFR-6 — Compatibility: Outputs SHALL be readable by pynwb and pass nwbinspector without critical
  issues; ImageSeries SHALL use rate-based timing.
- NFR-7 — Modularity: Optional stages (pose, facemap, bpod) SHALL be pluggable and import
  precomputed results without requiring inference.
- NFR-8 — Data integrity: Input existence SHALL be verified; checksums MAY be recorded for
  provenance.
- NFR-9 — Privacy: The system SHALL avoid PII and support anonymized subject IDs.
- NFR-10 — Type safety and configurability: All file patterns, paths, and toggles SHALL be enforced
  by Pydantic; environment overrides SHALL be supported via pydantic-settings.
- NFR-11 — Provenance: The pipeline SHALL embed configuration and software versions into the NWB or
  sidecar metadata.
- NFR-12 — Testability/CI: The repository SHALL include pytest tests with small synthetic fixtures
  and support CI that runs linting, type-checking, and tests.
- NFR-13 — Timebase versatility: The design SHALL be change-tolerant to alternate reference timebases
  (e.g., high-rate Neuropixels or designated TTL), and SHALL record the chosen timebase source in provenance.

### Timebase Strategy (Config-Driven)

- FR-TB-1 — Ubiquitous: THE SYSTEM SHALL designate a single reference timebase per session for
  aligning derived data (pose, facemap, Bpod-derived metrics), driven by configuration
  `timebase.source`.
- FR-TB-2 — Ubiquitous: WHERE `timebase.source = "neuropixels"`, THE SYSTEM SHALL use the declared
  Neuropixels/DAQ clock as the session reference timebase.
- FR-TB-3 — Ubiquitous: WHERE `timebase.source = "ttl"`, THE SYSTEM SHALL use the declared TTL channel
  (`timebase.ttl_id`) as the session reference timebase.
- FR-TB-4 — Ubiquitous: WHERE `timebase.source = "nominal_rate"`, THE SYSTEM SHALL synthesize the
  session reference timebase from a nominal acquisition rate (starting_time + rate) without
  per-frame timestamps, independent of specific video file timing semantics.
- FR-TB-5 — Ubiquitous: THE SYSTEM SHALL record in provenance the chosen `timebase_source` and any
  synthesis assumptions (`timebase.offset_s`, mapping strategy) used for alignment.
- FR-TB-6 — Ubiquitous: THE SYSTEM SHALL apply the configured `timebase.mapping` strategy (`nearest`
  or `linear`) to align video-derived samples, keeping misalignment within
  `timebase.jitter_budget_s`.

## Out of scope (OOS)

- OOS-1: Camera calibration (intrinsic/extrinsic) is not performed.
- OOS-2: Cross-camera optical fusion/triangulation is not included.
- OOS-3: Embedding raw videos into NWB by default (external links are preferred).

## Removed / Replaced Requirements

- Legacy per-frame timestamp computation removed (former FR-2/FR-3 about drift/drop statistics).
- Drift thresholds and timestamp mismatch errors replaced by frame/TTL count verification.

## Config file (TOML) strict schema

- The config file MUST contain exactly these sections and keys (no additional or missing keys):

  - `[project]`: name
  - `[paths]`: raw_root, intermediate_root, output_root, metadata_file, models_root
  - `[timebase]`: source, mapping, jitter_budget_s, offset_s, ttl_id?, neuropixels_stream?
  - `[acquisition]`: concat_strategy
  - `[verification]`: mismatch_tolerance_frames, warn_on_mismatch
  - `[bpod]`: parse
  - `[video.transcode]`: enabled, codec, crf, preset, keyint
  - `[nwb]`: link_external_video, lab, institution, file_name_template, session_description_template
  - `[qc]`: generate_report, out_template, include_verification
  - `[logging]`: level, structured
  - `[labels.dlc]`: run_inference, model
  - `[labels.sleap]`: run_inference, model
  - `[facemap]`: run_inference, ROIs

  Enum constraints (strict):

  - `timebase.source` ∈ {`nominal_rate`, `ttl`, `neuropixels`}
  - `timebase.mapping` ∈ {`nearest`, `linear`}
  - `timebase.jitter_budget_s` ≥ 0 (float)
  - Conditional: IF `timebase.source = "ttl"` THEN `ttl_id` REQUIRED and MUST match a session
    `[[TTLs]].id`.
  - Conditional: IF `timebase.source = "neuropixels"` THEN `neuropixels_stream` REQUIRED and MUST
    identify the selected clock/stream.

## Session file (TOML) strict schema

- The session file MUST contain exactly these sections and keys (no additional or missing keys):
  - `[session]`: id, subject_id, date, experimenter, description, sex, age, genotype
  - `[[bpod.files]]`: path, order
  - `[[TTLs]]`: id, description, paths
  - `[[cameras]]`: id, description, paths, order, ttl_id

Multiple Bpod `.mat` files MUST be represented as a table array `[[bpod.files]]` each with a unique
integer `order` specifying concatenation sequence (ascending). Missing or duplicated orders SHALL
cause validation failure.

Violation of the schema SHALL cause validation failure with a descriptive error.

## CLI contract (subcommands)

- ingest: Build a manifest from config; fail if expected files are missing; write manifest.json with
  absolute paths and metadata.
- (no sync subcommand): Verification occurs during ingest; failures abort early.
- bpod: Parse Bpod .mat file into Trials/Events tables when present.
- transcode: Transcode videos when enabled; otherwise no-op with clear logging.
- pose: Import and harmonize pose outputs (DLC/SLEAP) to canonical schema and timebase.
- infer: Run pose inference or prepare datasets when configured.
- facemap: Run or import facial metrics.
- to-nwb: Assemble NWB with all available data; warn when optional data are missing.
- validate: Run nwbinspector and save report.
- report: Generate QC HTML summary.
- Note: If Bpod parsing is enabled and a .mat file is present, ingestion produces Trials/Events for integration into NWB.

## Acceptance Criteria

- A1: For a sample session, ingest (with verification) → to-nwb → validate → report completes
  without errors and produces an NWB with external video links, rate-based ImageSeries for all
  cameras (independent of timebase source), and optional pose/facemap when provided.
- A2: The nwbinspector report contains no critical issues.
- A3: The QC report includes per-camera frame/TTL mismatch summary and pose confidence histograms
  when pose is present.
- A4: When one or more Bpod `.mat` files are present, the QC report lists total trial counts and
  event categories aggregated across concatenated files in ascending `order`.
- A5: Provenance includes a clear `timebase_source` indicating the selected session reference
  timebase and any synthesis assumptions.
- A6: A mismatch greater than tolerance causes ingestion to abort and the diagnostic summary
  includes camera_id, ttl_id, frame_count, ttl_pulse_count, mismatch magnitude.
- A7: A mismatch within tolerance produces a warning only when `verification.warn_on_mismatch=true`;
  otherwise no warning.
- A8: Selecting an alternate timebase (`ttl` or `neuropixels`) records mapping method, source
  identifier (`ttl_id` or `neuropixels_stream`), `offset_s`, and final jitter metrics in
  provenance.
- A9: When `timebase.source="ttl"` but `timebase.ttl_id` is missing or not found in session
  `[[TTLs]]`, configuration validation fails with a descriptive error.
- A10: When `timebase.source="neuropixels"` but `timebase.neuropixels_stream` is missing,
  configuration validation fails with a descriptive error.
- A11: Invalid `timebase.mapping` or negative `timebase.jitter_budget_s` causes configuration
  validation failure.
- A12: With `timebase.source="nominal_rate"`, NWB ImageSeries remain rate-based and provenance
  records `timebase_source = "nominal_rate"` and `offset_s`.
- A13: A config TOML containing any extra key or missing required key fails validation with an error
  referencing the offending section/key.
- A14: A session TOML with an extra section/table or missing required key fails validation with an
  error listing the deviation.
- A15: A camera referencing a non-existent `ttl_id` is marked unverifiable with a warning; ingestion
  proceeds and the camera appears in `verification_summary.json` with `verifiable=false`.
- A16: Multiple Bpod files with duplicate `order` or non-contiguous ordering (e.g., 1,3 without 2)
  cause session validation failure.
- A17: Timebase jitter after alignment does not exceed `timebase.jitter_budget_s`; exceeding it
  raises a validation error before NWB assembly.
- A18: Provenance includes a deterministic hash of the config and session TOML content (excluding
  comments) to ensure reproducibility (supports NFR-1).
- A19: When `timebase.source="ttl"`, derived data sample counts are consistent with aligned TTL
  pulses; discrepancies > tolerance produce an error.
- A20: Mapping strategy `linear` produces lower cumulative jitter than `nearest` in a synthetic test
  case (documented in test fixtures) and both strategies are selectable.

## Repository conventions

- Code under `src/` (package `w2t_bkin`), tests under `tests/` (pytest), docs under `docs/`
  (MkDocs). Pretrained models under `models/` by default (overridable via `paths.models_root`).
