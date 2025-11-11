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

## Functional requirements (EARS)

- FR-1 — Ubiquitous: THE SYSTEM SHALL ingest five camera video files per session and discover
  associated TTL pulse log files and Bpod behavioral file via the session TOML.
- FR-2 — Event-driven: WHEN ingestion completes, THE SYSTEM SHALL verify that each camera's video
  frame count equals the corresponding TTL pulse count and record a mismatch value.
- FR-3 — Unwanted behavior: IF any camera exhibits a non-zero frame/TTL mismatch beyond a configured
  tolerance, THEN THE SYSTEM SHALL abort ingestion with a diagnostic summary.
- FR-4 — Optional: WHERE transcoding is enabled in configuration, THE SYSTEM SHALL transcode videos
  to a mezzanine format; OTHERWISE THE SYSTEM SHALL operate directly on raw videos.
- FR-5 — Optional: WHERE pose results from DeepLabCut and/or SLEAP are supplied, THE SYSTEM SHALL
  import and harmonize them to a canonical skeleton and the session timebase (fps-derived), preserving confidence scores.
- FR-6 — Optional: WHERE Facemap inputs are supplied or enabled, THE SYSTEM SHALL import or compute
  facial metrics and align them to the session timebase (fps-derived) using frame index mapping.
- FR-7 — Ubiquitous: THE SYSTEM SHALL export one NWB file per session containing:
  Devices for five cameras; one ImageSeries per camera with external_file links and rate-based
  timing (no per-frame timestamp arrays); ndx-pose containers for pose (if present); and
  BehavioralTimeSeries for Facemap metrics (if present).
- FR-8 — Ubiquitous: THE SYSTEM SHALL generate a QC HTML report summarizing verification results
  (frame vs TTL counts), pose confidence distributions, and Facemap signal previews.
- FR-9 — Ubiquitous: THE SYSTEM SHALL validate the NWB output with nwbinspector and persist its
  report alongside the NWB file.
- FR-10 — Ubiquitous: THE SYSTEM SHALL be configuration-driven via TOML validated by Pydantic
  models with environment overrides.
- FR-11 — Optional: WHERE a Bpod MATLAB .mat file is present, THE SYSTEM SHALL parse it into a
  Trials TimeIntervals table and BehavioralEvents without using it for video timing.
- FR-12 — Ubiquitous (modularity): THE SYSTEM SHALL organize implementation into modular Python
  subpackages per stage (ingest, transcode, pose, facemap, bpod, nwb, qc, config, cli,
  utils) with clear contracts and minimal coupling.
- FR-13 — Ubiquitous: THE SYSTEM SHALL persist a `verification_summary.json` capturing per-camera
  counts and mismatches.
- FR-14 — Optional: WHERE a Bpod .mat file is present, THE SYSTEM SHALL include trial/event summaries in the QC report.

## Non-functional requirements (NFR)

- NFR-1 — Reproducibility: Given identical inputs/configuration, artifacts SHALL be identical where
  feasible (external tool nondeterminism excepted).
- NFR-2 — Idempotence: Re-running a stage without input changes SHALL be a no-op unless forced.
- NFR-3 — Observability: Each stage SHALL emit structured logs and a JSON summary (e.g.,
  verification_summary.json) to support QC and debugging.
- NFR-4 — Performance: A typical one-hour, five-camera session SHOULD complete within practical lab
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

## Session file (TOML) strict schema

- The session file MUST contain exactly these sections and keys (no additional or missing keys):
  - `[session]`: id, subject_id, date, experimenter, description, sex, age, genotype
  - `[bpod]`: path, order
  - `[[TTLs]]`: id, description, paths
  - `[[cameras]]`: id, description, paths, order, ttl_id

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

## Acceptance criteria

- A1: For a sample session, ingest (with verification) → to-nwb → validate → report completes without errors and
  produces an NWB with external video links, rate-based timing, and optional pose/facemap when
  provided.
- A2: The nwbinspector report contains no critical issues.
- A3: The QC report includes per-camera frame/TTL mismatch summary and pose confidence histograms when pose is present.
- A4: When a Bpod .mat file is present, the QC report lists trial counts and event categories.

## Repository conventions

- Code under `src/` (package `w2t_bkin`), tests under `tests/` (pytest), docs under `docs/`
  (MkDocs). Pretrained models under `models/` by default (overridable via `paths.models_root`).
