---
post_title: "W2T Body Kinematics Pipeline (Design Phase)"
author1: "Project Team"
post_slug: "readme-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pipeline", "docs"]
tags: ["overview", "design", "nwb"]
ai_note: "Draft produced with AI assistance and reviewed by maintainers."
summary: "Overview, goals, architecture, development workflow, and roadmap for the modular W2T body kinematics pipeline."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Overview

Modular, reproducible Python pipeline turning multi-camera rodent behavior recordings plus sync and
optional pose/facial/event logs into a validated NWB dataset with QC and provenance.

**Status**: Phase 4 Complete (NWB Assembly with pynwb) ✅  
**Test Coverage**: 255 tests passing (13 skipped)  
**Latest**: Real NWB file assembly with external video links, rate-based timing, and provenance embedding

## Key Features

- Explicit per-frame timestamps from hardware sync (TTL or counters)
- Optional mezzanine transcoding (idempotent)
- Pose harmonization (DLC/SLEAP) with skeleton mapping and confidence retention
- Facemap facial metric integration
- Bpod behavioral data parsing with multi-file session support (glob patterns, ordering, merging)
- Trials & events import from NDJSON (not used for sync)
- Single NWB output with external video links (no embedded heavy binaries)
- QC HTML: drift, drops, pose confidence, facial previews
- Deterministic, config-driven (TOML + Pydantic)

## High-Level Flow

```text
ingest → sync → (transcode) → pose / facemap / events → nwb → validate → qc
```

## Package Modules (Planned)

| Module    | Purpose                               | Status      |
| --------- | ------------------------------------- | ----------- |
| config    | Load & validate settings              | ✅ Complete |
| ingest    | Discover assets, produce manifest     | ✅ Complete |
| sync      | Generate timestamps, drift/drop stats | ✅ Complete |
| transcode | Optional stable mezzanine videos      | ✅ Complete |
| pose      | Import/harmonize pose outputs         | ✅ Complete |
| facemap   | Import/compute facial metrics         | ✅ Complete |
| events    | Normalize NDJSON → trials/events      | ✅ Complete |
| nwb       | Assemble NWB file & provenance        | ✅ Complete |
| qc        | Build HTML report from summaries      | 🔲 Planned  |
| validate  | Run nwbinspector validation           | 🔲 Planned  |
| cli       | Typer CLI entry points                | 🔲 Planned  |
| utils     | Shared primitives                     | ✅ Complete |
| domain    | Shared typed domain models            | ✅ Complete |

## Configuration Snippet (Example)

```toml
[project]
name = "w2t-bkin"
n_cameras = 5

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

[video]
pattern = "cam{index}.mp4"

[sync]
primary_clock = "cam0"
tolerance_ms = 2.0

[nwb]
link_external_video = true
```

## CLI (Planned Subcommands)

- `ingest` — build manifest
- `sync` — compute timestamps & stats
- `transcode` — optional mezzanine outputs
- `pose` — import/harmonize pose outputs
- `infer` — run pose inference when configured
- `facemap` — facial metric stage
- `events` — normalize NDJSON logs
- `to-nwb` — assemble NWB
- `validate` — run nwbinspector
- `report` — generate QC HTML

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pre-commit install
pytest -q
```

## Testing Strategy (Summary)

- Unit: timestamp math, skeleton mapping, event derivation
- Integration: synthetic mini-session end-to-end
- CLI: artifact presence & exit codes
- Type: mypy on core modules; style: ruff

## Artifact Locations

| Path                             | Description             |
| -------------------------------- | ----------------------- |
| `data/raw/<session>`             | Source videos + logs    |
| `data/interim/<session>/sync`    | Timestamps + summaries  |
| `data/interim/<session>/pose`    | Harmonized pose         |
| `data/interim/<session>/facemap` | Facial metrics          |
| `data/interim/<session>/events`  | Trials/events tables    |
| `data/interim/<session>/video`   | Mezzanine videos        |
| `data/processed/<session>`       | NWB + validation report |
| `data/qc/<session>`              | QC HTML                 |

## Quality Gates

- Timestamps monotonic per camera
- Drift within configured threshold
- No critical nwbinspector issues
- Pose confidence distributions reasonable
- Trials table non-overlapping

## Roadmap

### ✅ Completed (Phases 0-4)

- [x] Configuration loading and validation (Phase 0)
- [x] File discovery and manifest building (Phase 1)
- [x] Timebase synchronization and alignment (Phase 2)
- [x] Behavioral events from Bpod .mat files (Phase 3)
- [x] Video transcoding to mezzanine format (Phase 3)
- [x] Pose import and harmonization (DLC/SLEAP) (Phase 3)
- [x] Facemap facial metrics computation (Phase 3)
- [x] **NWB file assembly with pynwb** (Phase 4)
  - Real pynwb Device and ImageSeries objects
  - External video file links
  - Rate-based timing (no per-frame timestamps)
  - Provenance metadata embedding
  - Security validations and deterministic output

### 🔲 Planned (Phase 5+)

- [ ] NWB validation with nwbinspector
- [ ] QC HTML report generation
- [ ] CLI interface with Typer
- [ ] Optional modalities integration in NWB (pose, facemap, Bpod events)
- [ ] Full end-to-end pipeline orchestration

## Out of Scope

- Camera calibration & 3D reconstruction
- Embedding raw video in NWB by default

## Contributing (Early Phase)

Open an issue describing proposed functionality. Keep PRs small and focused (single stage or feature).
Add/adjust tests and update documentation sections touched.

## License

Apache-2.0 (see `LICENSE`).

## Summary Sentence

Design-phase repository for a modular, timestamp-faithful, NWB-centric behavioral pipeline with
explicit synchronization, optional analytics stages, and transparent QC.
