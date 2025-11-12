---
post_title: "Tasks — W2T-BKIN implementation plan and dependency order"
author1: "Project Team"
post_slug: "tasks-w2t-bkin-impl-plan"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["engineering", "planning", "traceability"]
tags: ["tasks", "dependencies", "topological-order", "requirements-mapping"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Actionable implementation plan with module dependency graph, build phases, requirement mapping, and minimal contracts/tests."
post_date: "2025-11-11"
---

## Purpose

This document turns requirements and design into a concrete build plan. It shows cross-dependencies, the order of implementation, and the tests that gate each phase.

## Dependency graph (concise)

```mermaid
flowchart LR
  subgraph Foundation
    U[utils]:::f
    D[domain]:::f
    C[config]:::f
  end
  I[ingest]
  E[events (bpod)]
  S[sync (timebase)]
  T[transcode]
  P[pose]
  F[facemap]
  N[nwb]
  Q[qc]
  CLI[cli]

  U --> I
  U --> T
  U --> P
  U --> F
  U --> N
  D --> C
  D --> I
  D --> S
  D --> N
  C --> I
  C --> S
  I --> S
  I --> T
  S --> P
  S --> F
  P --> N
  F --> N
  I --> N
  N --> Q
  I --> Q
  E --> Q
  CLI --> C
  CLI --> I
  CLI --> T
  CLI --> P
  CLI --> F
  CLI --> N
  CLI --> Q

  classDef f fill:#eef,stroke:#88a;
```

Notes:

- P (pose) and F (facemap) are optional and depend on S (sync) for alignment.
- N (nwb) requires I (manifest), and consumes bundles from P/F when present.
- Q (qc) needs N (for nwbinspector) and verification outputs from I; E (events) augments QC when available.

## Topological build order (with phases)

1. Phase 0 — Foundation

   - utils, domain, config
   - Rationale: Shared primitives, data models, and strict schema validation are prerequisites for all stages.
   - Requirements: FR-10, NFR-10, NFR-11; supports A18.

2. Phase 1 — Ingest + Verify (fail-fast)

   - ingest (manifest + counts), verification_summary sidecar
   - Requirements: FR-1, FR-2, FR-3, FR-13, FR-15, FR-16; Acceptance A6, A7.
   - Outcome: manifest.json, verification_summary.json; abort if mismatch > tolerance.

3. Phase 2 — Timebase (sync)

   - Timebase providers (Nominal, TTL; Neuropixels stub if needed), mapping strategies (nearest, linear), jitter budget enforcement
   - Requirements: FR-TB-1..6; Acceptance A17, A20, A8, A9, A10, A11, A12.
   - Outcome: alignment indices and alignment_stats.json; provenance timebase fields resolved.

4. Phase 3 — Optional modalities

   - events (bpod) — parse Bpod .mat files into trials and behavioral events
   - transcode (if enabled) — idempotent mezzanine
   - pose import/harmonize (DLC/SLEAP) — aligned to reference timebase
   - facemap compute/import — aligned to reference timebase
   - Requirements: FR-4, FR-5, FR-6, FR-11, FR-14; contributes to A1, A3, A4.

5. Phase 4 — NWB Assembly

   - Assemble Devices, ImageSeries (rate-based, external_file), ndx-pose, BehavioralTimeSeries; embed provenance
   - Requirements: FR-7, NFR-6, NFR-1/2; Acceptance A1, A12.

6. Phase 5 — Validation + QC
   - Run nwbinspector, emit HTML report with verification, pose, facemap, and optional Bpod summaries
   - Requirements: FR-8, FR-9, FR-14; Acceptance A2, A3, A4.

## Minimal contracts per module (inputs/outputs)

- utils

  - Inputs: primitives
  - Outputs: hashing, safe paths, ffmpeg/ffprobe wrappers, bounded concurrency, JSON I/O, logging

- domain

  - Inputs: none
  - Outputs: Pydantic models (Config, Session, Camera, TTL, Manifest, VerificationSummary, Provenance, AlignmentStats, etc.)

- config

  - Inputs: config.toml, session.toml, env overrides
  - Outputs: validated Config and Session; deterministic hashes (config_hash, session_hash)

- ingest

  - Inputs: Config, Session
  - Outputs: Manifest, VerificationSummary sidecar; errors on missing files, mismatch > tolerance

- events (optional)

  - Inputs: list of Bpod .mat files
  - Outputs: Trials table + BehavioralEvents + QC summary (BpodSummary)
  - Requirements: FR-11, FR-14; Acceptance A4

- sync

  - Inputs: Config (timebase.\*), Manifest
  - Outputs: TimebaseProvider, alignment indices, AlignmentStats; enforce jitter budget before NWB

- transcode (optional)

  - Inputs: Manifest, TranscodeOptions
  - Outputs: Updated Manifest pointing to mezzanine files (idempotent)

- pose (optional)

  - Inputs: Manifest, model metadata
  - Outputs: PoseBundle aligned to reference timebase + alignment_stats contribution

- facemap (optional)

  - Inputs: Manifest, ROIs or precomputed signals
  - Outputs: FacemapBundle aligned to reference timebase + alignment_stats contribution

- nwb

  - Inputs: Manifest, Bundles (pose/facemap), Config, Provenance
  - Outputs: NWB file path (with external_file ImageSeries, rate-based timing)

- qc

  - Inputs: NWB path, VerificationSummary, alignment_stats, optional Bpod summary
  - Outputs: Validation report (nwbinspector), QC HTML

- cli
  - Inputs: user flags; file paths
  - Outputs: Orchestration and stage logging

## Requirements mapping (traceability)

- FR-1/2/3/13/15/16 → ingest (+verify)
- FR-4 → transcode
- FR-5/6 → pose, facemap (+sync)
- FR-7 → nwb (+sync for derived data only)
- FR-8/9/14 → qc (+nwb, +events)
- FR-10 → config
- FR-11/14 → events (bpod)
- FR-TB-1..6 → sync
- NFR-1/2 → nwb, utils, deterministic ordering across stages
- NFR-3 → all stages emit JSON sidecars/logs
- NFR-6 → nwb (rate-based ImageSeries)
- NFR-10/11 → config, provenance
- A1/A2/A3/A4/A5/A6/A7/A8/A9/A10/A11/A12/A17/A18/A19/A20 → covered across phases as indicated above

## Phase gates and test anchors

- Phase 0 gate:

  - tests/unit/test_config.py — strict schema; invalid enums; missing/extra keys
  - tests/unit/test_domain.py — model validation and immutability

- Phase 1 gate:

  - tests/unit/test_ingest.py — discovery, counts, abort on mismatch > tolerance; unverifiable cameras warning
  - tests/unit/test_utils.py — ffprobe wrapper probes (mocked)

- Phase 2 gate:

  - tests/unit/test_sync.py — nearest vs linear mapping; jitter budget check; offset application
  - tests/property/test_invariants.py — reproducibility of hashes and alignment

- Phase 3 gate:

  - tests/unit/test_events.py — Bpod .mat parsing; trial extraction with outcome inference; behavioral event extraction; NaN handling; summary generation
  - tests/unit/test_pose.py — import/harmonize; confidence preservation; alignment length checks
  - tests/unit/test_facemap.py — ROI handling; alignment; preview stats
  - tests/unit/test_transcode.py — idempotent outputs; content-addressed paths

- Phase 4 gate:

  - tests/integration/test_to_nwb.py — ImageSeries external links (rate-based); deterministic container order

- Phase 5 gate:
  - tests/integration/test_report_validate.py — nwbinspector has no critical issues; QC includes verification/pose/facemap

## Risks and mitigations

- Tooling variability (ffmpeg/nwbinspector versions) — pin minimums; record versions in provenance; mock in tests.
- TTL data quality (gaps/duplication) — debounce and gap thresholds; surface as warnings/errors via taxonomy.
- Large sessions — bound concurrency; stream where possible; avoid per-frame timestamps entirely.

## Next actions

- Stand up Phase 0 scaffolding (utils/logger, Pydantic models, config loader with strict schema and hashing)
- Implement Phase 1 ingest + verification, write sidecars, and wire logs
- Add Phase 2 timebase with nearest/linear and budget enforcement
- Proceed with optional modalities, then NWB and QC
