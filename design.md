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

## Scope

In scope: ingest → verify → (optional: transcode | pose | facemap | bpod) → align (timebase) → assemble NWB → validate → QC. Out of scope: calibration, triangulation, embedding raw videos internally.

## Architecture (simplified)

```mermaid
flowchart LR
  subgraph Core
    CFG[config] --> ING[ingest]
    CFG --> SYN(sync)
    ING --> SYN
    SYN --> NWB[nwb]
  end
  ING --> VER[verify counts]
  VER -->|abort on mismatch>tol| X((abort))
  VER -->|within tol| OPT[optionals]
  OPT --> TRN[transcode]
  OPT --> POS[pose]
  OPT --> FAC[facemap]
  OPT --> EVT[events/bpod]
  TRN --> SYN
  POS --> SYN
  FAC --> SYN
  EVT --> SYN
  SYN --> NWB
  NWB --> VAL[validate]
  VAL --> QC[qc report]
```

Principles:

1. No cross-imports between sibling service packages.
2. Composition through files + domain models only.
3. Fail fast before heavy processing.
4. Sidecars for observability (verification, alignment, provenance, validation).
5. All outputs deterministic when inputs unchanged.

## Module Responsibilities (minimal contracts)

| Module          | Key Input                              | Output / Contract                                           | FR/NFR Coverage                  |
| --------------- | -------------------------------------- | ----------------------------------------------------------- | -------------------------------- |
| config          | config.toml, session.toml              | validated Config, Session, hashes                           | FR-10, FR-15, FR-TB-\* NFR-10/11 |
| domain          | none                                   | Pydantic models (immutable)                                 | FR-12 NFR-7                      |
| utils           | primitives                             | hashing, path safety, subprocess wrappers, logging          | NFR-1/2/3                        |
| ingest+verify   | Config, Session                        | manifest.json, verification_summary.json (abort/warn logic) | FR-1/2/3/13/15/16                |
| sync            | Config(Timebase), Manifest             | alignment indices + alignment_stats.json (budget enforced)  | FR-TB-1..6, FR-17, A17           |
| transcode (opt) | Manifest                               | updated Manifest (mezzanine paths)                          | FR-4, NFR-2                      |
| pose (opt)      | Manifest, timebase                     | PoseBundle (aligned)                                        | FR-5                             |
| facemap (opt)   | Manifest, timebase                     | FacemapBundle (aligned)                                     | FR-6                             |
| events (opt)    | Bpod .mat files, BpodSession, timebase | Trials/Events (aligned), TrialSummary, multi-file merging   | FR-11/14                         |
| nwb             | Manifest + bundles + provenance        | NWB file (rate-based ImageSeries)                           | FR-7 NFR-6                       |
| validate        | NWB                                    | nwbinspector report                                         | FR-9                             |
| qc              | NWB + sidecars                         | QC HTML                                                     | FR-8/14 NFR-3                    |

## Sidecar Schemas (summary)

**verification_summary.json:**

```json
{
  "session_id": "string",
  "cameras": [
    {
      "camera_id": "string",
      "ttl_id": "string | null",
      "frame_count": "int",
      "ttl_pulse_count": "int",
      "mismatch": "int",
      "verifiable": "bool",
      "status": "string"
    }
  ],
  "generated_at": "ISO8601 timestamp"
}
```

**alignment_stats.json:**

```json
{
  "timebase_source": "nominal_rate | ttl | neuropixels",
  "mapping": "nearest | linear",
  "offset_s": "float",
  "max_jitter_s": "float",
  "p95_jitter_s": "float",
  "aligned_samples": "int"
}
```

**provenance.json:**

```json
{
  "config_hash": "SHA256 hash",
  "session_hash": "SHA256 hash",
  "software": {
    "name": "w2t_bkin",
    "version": "string",
    "python_version": "string",
    "dependencies": {
      "pynwb": "version",
      "opencv": "version",
      "ffmpeg": "version"
    }
  },
  "git": {
    "commit": "SHA hash",
    "branch": "string",
    "dirty": "bool",
    "remote": "URL"
  },
  "timebase": {
    "source": "nominal_rate | ttl | neuropixels",
    "mapping": "nearest | linear",
    "offset_s": "float",
    "ttl_id": "string (if source=ttl)",
    "neuropixels_stream": "string (if source=neuropixels)"
  },
  "created_at": "ISO8601 timestamp"
}
```

**validation_report.json:**

```json
{
  "nwbinspector_version": "string",
  "nwb_file": "path",
  "timestamp": "ISO8601",
  "messages": [
    {
      "severity": "critical | error | warning | info",
      "message": "string",
      "location": "string"
    }
  ],
  "summary": {
    "critical": "int",
    "errors": "int",
    "warnings": "int"
  }
}
```

## Error Taxonomy

Codes: CONFIG_MISSING_KEY, CONFIG_EXTRA_KEY, SESSION_MISSING_KEY, SESSION_EXTRA_KEY, CAMERA_UNVERIFIABLE, MISMATCH_EXCEEDS_TOLERANCE, JITTER_EXCEEDS_BUDGET, PROVIDER_RESOURCE_MISSING, DERIVED_COUNT_MISMATCH, EXTERNAL_TOOL_ERROR.
Shape: { error_code, message, context:{...}, hint, stage }.

### Exception Hierarchy

```python
W2TError(Exception)
├── ConfigError
│   ├── ConfigMissingKeyError
│   ├── ConfigExtraKeyError
│   └── ConfigValidationError
├── SessionError
│   ├── SessionMissingKeyError
│   ├── SessionExtraKeyError
│   └── SessionValidationError
├── IngestError
│   ├── FileNotFoundError
│   └── VerificationError
│       └── MismatchExceedsToleranceError
├── SyncError
│   ├── TimebaseProviderError
│   ├── JitterExceedsBudgetError
│   └── AlignmentError
├── EventsError
│   └── BpodParseError
├── TranscodeError
├── PoseError
├── FacemapError
├── NWBError
│   └── ExternalToolError
├── ValidationError (nwbinspector)
└── QCError
```

Base `W2TError` includes structured fields: `error_code`, `message`, `context` (dict), `hint` (str), `stage` (str).
Module-specific errors (IngestError, SyncError, etc.) inherit from W2TError and add domain-specific context.

## Timebase Strategy (Reference Only)

Provider (nominal|ttl|neuropixels) chosen via config; mapping strategy (nearest|linear) aligns derived samples; jitter metrics (max, p95) computed and compared to budget. Abort prior to NWB if budget exceeded (A17). ImageSeries timing untouched (rate-based invariant).

## Build Order & Dependencies

1. Foundation: utils, domain, config
2. Ingest+Verify
3. Sync (timebase + alignment)
4. Optional modalities (transcode, pose, facemap, events)
5. NWB assembly
6. Validation + QC

## Requirement Coverage (condensed matrix)

| Requirement Group | Implemented By                                |
| ----------------- | --------------------------------------------- |
| FR-1/2/3/13/15/16 | ingest+verify                                 |
| FR-4              | transcode                                     |
| FR-5              | pose                                          |
| FR-6              | facemap                                       |
| FR-7              | nwb (plus sync for derived alignment)         |
| FR-8/9/14         | qc + validate + events                        |
| FR-10             | config                                        |
| FR-11             | events                                        |
| FR-12             | modular package layout                        |
| FR-17 + FR-TB-\*  | sync + provenance                             |
| NFR-1/2           | deterministic ordering + hashing (utils, nwb) |
| NFR-3             | sidecars + JSON logging                       |
| NFR-4             | concurrency model + O(n) verification         |
| NFR-5             | cross-platform Python tooling                 |
| NFR-6             | rate-based ImageSeries in nwb                 |
| NFR-7             | plugin-compatible optional modules            |
| NFR-8             | ingest existence + optional checksums         |
| NFR-9             | anonymization policy (utils)                  |
| NFR-10/11         | config + provenance                           |
| NFR-12            | pytest + CI gating                            |
| NFR-13            | sync abstraction                              |

## Testing & Quality Gates

Unit: config/session validation, mismatch logic, timebase jitter computation, hashing reproducibility.
Property: reproducible config/session hashes, linear vs nearest jitter comparison (A20).
Integration: ingest → nwb → validate → qc on synthetic fixtures (A1/A2/A3/A4/A5).
Edge: unverifiable camera, tolerance boundary, jitter budget exceeded, missing ttl_id, duplicate Bpod order.
CI: pre-commit (ruff, black, mypy), unit matrix, integration job storing NWB + QC artifacts.

## Security & Privacy

Path sanitization, restricted subprocess arguments, optional checksums, deterministic anonymized subject IDs (salted hash), no PII in logs.

## Extensibility

Entry points: `w2t_bkin.pose_plugins`, `w2t_bkin.facemap_plugins`. Failures isolated; warnings logged; core unaffected.

## Sequence & State (Minimal)

```mermaid
stateDiagram-v2
  [*] --> LoadConfig
  LoadConfig --> Ingest: Config + Session validated
  Ingest --> Verify

  Verify --> Abort: mismatch > tolerance
  Verify --> CheckOptionals: mismatch <= tolerance

  state CheckOptionals {
    [*] --> CheckTranscode
    CheckTranscode --> Transcode: enabled
    CheckTranscode --> CheckEvents: disabled
    Transcode --> CheckEvents

    CheckEvents --> ParseBpod: bpod.parse=true
    CheckEvents --> Sync: bpod.parse=false
    ParseBpod --> Sync
  }

  state CheckOptionals {
    [*] --> CheckTranscode
    CheckTranscode --> Transcode: enabled
    CheckTranscode --> CheckEvents: disabled
    Transcode --> CheckEvents

    CheckEvents --> ParseBpod: bpod.parse=true
    CheckEvents --> CheckPose: bpod.parse=false
    ParseBpod --> CheckPose
  }

  CheckOptionals --> CheckPose: video transcoded (if enabled)

  state CheckPose {
    [*] --> ImportPose: pose files exist
    [*] --> CheckFacemap: no pose files
    ImportPose --> CheckFacemap
  }

  CheckPose --> CheckFacemap: pose imported (if available)

  state CheckFacemap {
    [*] --> ComputeFacemap: enabled
    [*] --> Sync: disabled
    ComputeFacemap --> Sync
  }

  CheckFacemap --> Sync: optional data ready for alignment

  Sync --> NWB: all data aligned to timebase

  NWB --> Validate
  Validate --> QC
  QC --> [*]: pipeline complete

  Abort --> [*]: validation failed
```

```mermaid
sequenceDiagram
  participant CLI
  participant config
  participant ingest
  participant verify
  participant events
  participant sync
  participant pose
  participant facemap
  participant nwb
  participant validate
  participant qc

  Note over CLI: Pipeline orchestration
  CLI->>config: load_config(config.toml)
  config-->>CLI: Config
  CLI->>config: load_session(session.toml)
  config-->>CLI: Session

  Note over CLI,ingest: Phase 1: Ingest + Verify
  CLI->>ingest: build_manifest(Config, Session)
  ingest-->>CLI: Manifest
  CLI->>verify: verify_manifest(Manifest, Config)
  verify-->>CLI: VerificationResult

  alt mismatch > tolerance
    verify-->>CLI: VerificationError
    CLI->>CLI: abort with diagnostic
  else mismatch <= tolerance
    verify-->>CLI: VerificationSummary (success)

    Note over CLI,events: Phase 2a: Optional Modalities (Pre-Sync)
    opt bpod.parse == true
      CLI->>events: parse_bpod_files(Session)
      events-->>CLI: Trials/Events (raw)
    end

    opt pose files available
      CLI->>pose: import_pose(Manifest)
      pose-->>CLI: PoseData (raw)
    end

    opt facemap enabled
      CLI->>facemap: compute_facemap(Manifest)
      facemap-->>CLI: FacemapData (raw)
    end

    Note over CLI,sync: Phase 2b: Timebase + Alignment
    CLI->>sync: make_timebase(Config)
    sync-->>CLI: TimebaseProvider
    CLI->>sync: align_manifest(Manifest, Timebase)
    sync-->>CLI: AlignmentStats

    alt jitter > budget
      sync-->>CLI: JitterExceedsBudgetError
      CLI->>CLI: abort
    end

    opt events data available
      CLI->>sync: align_trials_events(Trials, Events, Timebase)
      sync-->>CLI: Trials/Events (aligned)
    end

    opt pose data available
      CLI->>sync: align_pose(PoseData, Timebase)
      sync-->>CLI: PoseBundle (aligned)
    end

    opt facemap data available
      CLI->>sync: align_facemap(FacemapData, Timebase)
      sync-->>CLI: FacemapBundle (aligned)
    end

    Note over CLI,nwb: Phase 3: NWB Assembly
    CLI->>nwb: assemble_nwb(Manifest, Bundles, Provenance)
    nwb-->>CLI: NWB file path

    Note over CLI,qc: Phase 4: Validation + QC
    CLI->>validate: run_nwbinspector(NWB)
    validate-->>CLI: ValidationReport

    CLI->>qc: render_qc(NWB, Summaries)
    qc-->>CLI: QC HTML path
  end

  Note over CLI: Pipeline complete
```

## Provenance (Determinism)

Canonicalization: strip comments → sort keys → compact JSON → SHA256. Record timebase selection and jitter metrics. Ensures reproducibility (NFR-1) and traceability (FR-17, A18).

## Summary

Design reduced to essential contracts and flow while maintaining full requirements coverage, reproducibility, modularity, and observability. For extended rationale or detailed schemas, see `spec/spec-design-w2t-bkin-simplified.md` and `spec/*` schema specs.
