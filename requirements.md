---
post_title: "Requirements — W2T Body Kinematics Pipeline (Design Phase)"
author1: "Project Team"
post_slug: "requirements-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "validation", "testing"]
tags: ["requirements", "EARS", "design-phase"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Functional and non-functional requirements in EARS notation for a modular multi-camera behavioral pipeline producing NWB."
post_date: "2025-11-08"
---

## Overview

The pipeline transforms multi-camera behavioral recordings plus timing and event logs into a
validated NWB dataset. The following requirements reflect a clean-slate design-phase view with a
modular architecture and a CLI-first user experience.

## Functional requirements (EARS)

- FR-1 — Ubiquitous: THE SYSTEM SHALL ingest five camera video files per session and discover
  associated synchronization files.
- FR-2 — Event-driven: WHEN hardware sync inputs (TTL edges or frame counters) are provided,
  THE SYSTEM SHALL compute per-frame timestamps for each camera in a common session timebase.
- FR-3 — Event-driven: WHEN timestamp computation completes, THE SYSTEM SHALL detect and report
  dropped frames, duplicates, and inter-camera drift with summary statistics.
- FR-4 — Optional: WHERE transcoding is enabled in configuration, THE SYSTEM SHALL transcode videos
  to a mezzanine format; OTHERWISE THE SYSTEM SHALL operate directly on raw videos.
- FR-5 — Optional: WHERE pose results from DeepLabCut and/or SLEAP are supplied, THE SYSTEM SHALL
  import and harmonize them to a canonical skeleton and the session timebase, preserving confidence
  scores.
- FR-6 — Optional: WHERE Facemap inputs are supplied or enabled, THE SYSTEM SHALL import or compute
  facial metrics and align them to the session timebase.
- FR-7 — Ubiquitous: THE SYSTEM SHALL export one NWB file per session containing:
  Devices for five cameras; one ImageSeries per camera with external_file links and per-frame
  timestamps; synchronization TimeSeries; ndx-pose containers for pose (if present); and
  BehavioralTimeSeries for Facemap metrics (if present).
- FR-8 — Ubiquitous: THE SYSTEM SHALL generate a QC HTML report summarizing synchronization
  integrity, pose confidence distributions, and Facemap signal previews.
- FR-9 — Ubiquitous: THE SYSTEM SHALL validate the NWB output with nwbinspector and persist its
  report alongside the NWB file.
- FR-10 — Ubiquitous: THE SYSTEM SHALL be configuration-driven via TOML validated by Pydantic
  models with environment overrides.
- FR-11 — Optional: WHERE event NDJSON logs are present, THE SYSTEM SHALL import them as a Trials
  TimeIntervals table and BehavioralEvents without using them for video synchronization.
- FR-12 — Ubiquitous (modularity): THE SYSTEM SHALL organize implementation into modular Python
  subpackages per stage (ingest, sync, transcode, pose, facemap, events, nwb, qc, config, cli,
  utils) with clear contracts and minimal coupling.

## Non-functional requirements (NFR)

- NFR-1 — Reproducibility: Given identical inputs/configuration, artifacts SHALL be identical where
  feasible (external tool nondeterminism excepted).
- NFR-2 — Idempotence: Re-running a stage without input changes SHALL be a no-op unless forced.
- NFR-3 — Observability: Each stage SHALL emit structured logs and a JSON summary (e.g.,
  sync_summary.json) to support QC and debugging.
- NFR-4 — Performance: A typical one-hour, five-camera session SHOULD complete within practical lab
  time budgets; compute-heavy steps SHOULD support parallelization.
- NFR-5 — Portability: The pipeline SHALL run on Linux and macOS; Windows is best-effort.
- NFR-6 — Compatibility: Outputs SHALL be readable by pynwb and pass nwbinspector without critical
  issues.
- NFR-7 — Modularity: Optional stages (pose, facemap, events) SHALL be pluggable and import
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

## Configuration keys (reference skeleton)

- project: { name, n_cameras }
- paths: { raw_root, intermediate_root, output_root, models_root }
- session: { id, subject_id, date, experimenter, description, sex, age, genotype }
- video: { pattern, fps, transcode: { enabled, codec, crf, preset, keyint } }
- sync: { ttl_channels: [ { path, name, polarity } ], tolerance_ms, drop_frame_max_gap_ms,
  primary_clock }
- labels: { dlc: { model, run_inference }, sleap: { model, run_inference } }
- facemap: { run, roi }
- nwb: { link_external_video, file_name, session_description, lab, institution }
- qc: { generate_report, out }
- logging: { level }
- events: { patterns: ["**/*_training.ndjson", "**/*_trial_stats.ndjson"], format: "ndjson" }

## CLI contract (subcommands)

- ingest: Build a manifest from config; fail if expected files are missing; write manifest.json with
  absolute paths and metadata.
- sync: Produce per-camera timestamps and drift/drop summaries; non-zero exit on severe mismatch.
- transcode: Transcode videos when enabled; otherwise no-op with clear logging.
- pose: Import and harmonize pose outputs (DLC/SLEAP) to canonical schema and timebase.
- infer: Run pose inference or prepare datasets when configured.
- facemap: Run or import facial metrics.
- to-nwb: Assemble NWB with all available data; warn when optional data are missing.
- validate: Run nwbinspector and save report.
- report: Generate QC HTML summary.
- Note: If events are configured, ingest discovers them and to-nwb integrates Trials/Events.

## Acceptance criteria

- A1: For a sample session, ingest → sync → to-nwb → validate → report completes without errors and
  produces an NWB with external video links, valid timestamps, and optional pose/facemap when
  provided.
- A2: The nwbinspector report contains no critical issues.
- A3: The QC report includes a drift plot and pose confidence histograms when pose is present.

## Repository conventions

- Code under `src/` (package `w2t_bkin`), tests under `tests/` (pytest), docs under `docs/`
  (MkDocs). Pretrained models under `models/` by default (overridable via `paths.models_root`).
