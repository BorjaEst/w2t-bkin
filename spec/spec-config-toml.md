---
title: Config TOML Specification (W2T BKin)
version: 1.0
date_created: 2025-11-10
last_updated: 2025-11-10
owner: pipeline-team
tags: [schema, config, design]
---

# Introduction

This specification defines the structure, required and optional keys, constraints, and validation
rules for the pipeline-level configuration file `config.toml` used by the W2T BKin system. It
supports hardware-based frame synchronization (no software timestamp generation) and governs
ingestion, verification, processing stages, NWB assembly, and quality reporting.

## 1. Purpose & Scope

Purpose: Provide a precise schema for `config.toml` enabling deterministic parsing and validation by
Pydantic models. Scope: Repository-wide pipeline configuration (NOT per-session overrides).
Assumptions: Hardware delivers aligned frame timing and TTL pulse counts per camera.

## 2. Definitions

- TTL: Transistor-Transistor Logic pulse, used for hardware synchronization and frame counting.
- Mezzanine: Transcoded intermediate video optimized for processing and seeking.
- Verification: Counting and comparing video frames and TTL pulses per camera.
- Rate-based timing: NWB ImageSeries uses `starting_time` + `rate` instead of per-frame timestamps.

## 3. Requirements, Constraints & Guidelines

- REQ-001: The config file MUST conform to a strict schema with exactly the sections and keys listed below; no additional or missing keys are allowed.
- REQ-002: The config MUST include `project.name`.
- REQ-003: The config MUST include `paths.raw_root`, `paths.intermediate_root`, `paths.output_root`, `paths.metadata_file`, and `paths.models_root`.
- REQ-004: Verification settings MUST define `mismatch_tolerance_frames` (integer ≥ 0) and `warn_on_mismatch` (boolean).
- REQ-005: If `video.transcode.enabled` is true, all transcode subkeys (`codec`, `crf`, `preset`, `keyint`) MUST be present.
- REQ-006: NWB settings MUST include `link_external_video`, `lab`, `institution`, `file_name_template`, and `session_description_template`.
- REQ-007: Logging MUST define `level` ∈ {`DEBUG`,`INFO`,`WARNING`,`ERROR`,`CRITICAL`} and `structured` (boolean).
- REQ-008: Pose model configs (`labels.dlc`, `labels.sleap`) MUST include `run_inference` (boolean) and `model` (string).
- REQ-009: Facemap config MUST include `run_inference` (boolean) and `ROIs` (string list).
- REQ-010: QC MUST include `generate_report` (boolean), `out_template` (string), and `include_verification` (boolean).
- CON-001: No secret or credential keys allowed inside `config.toml`.
- CON-002: Paths MUST be relative to repository root or absolute paths; no environment interpolation.
- GUD-001: Prefer keeping mismatch tolerance at 0 when hardware sync is robust.
- GUD-002: Use `structured=true` for machine-parsed logs when scaling operations.
- PAT-001: Templates use Python format style referencing `session.*` keys.

## 4. Interfaces & Data Contracts

Schema outline (strict):

project: { name: str }
paths: { raw_root: str, intermediate_root: str, output_root: str, metadata_file: str, models_root: str }
acquisition: { concat_strategy: str }
verification: { mismatch_tolerance_frames: int, warn_on_mismatch: bool }
video: { transcode: { enabled: bool, codec: str, crf: int, preset: str, keyint: int } }
labels: { dlc: { run_inference: bool, model: str }, sleap: { run_inference: bool, model: str } }
facemap: { run_inference: bool, ROIs: string[] }
bpod: { parse: bool }
nwb: { link_external_video: bool, lab: str, institution: str, file_name_template: str, session_description_template: str }
qc: { generate_report: bool, out_template: str, include_verification: bool }
logging: { level: 'DEBUG'|'INFO'|'WARNING'|'ERROR'|'CRITICAL', structured: bool }

## 5. Acceptance Criteria

- AC-001: Given a minimal valid `config.toml`, the settings loader returns a Settings object without errors.
- AC-002: When `mismatch_tolerance_frames` < 0, validation fails with a descriptive error.
- AC-003: When `video.transcode.enabled=true` and any of `codec`, `crf`, `preset`, or `keyint` are missing, validation fails.
- AC-004: Logging level outside allowed set causes validation failure.
- AC-005: Unknown sections or keys cause validation failure citing the offending key path.
- AC-006: When `bpod.parse=true` but a session lacks Bpod files, ingestion emits a warning and continues.

## 6. Test Automation Strategy

- Unit tests: parse valid and invalid config variants; assert failures where expected.
- Property tests: random generation of gap policies and transcode settings within constraints.
- Integration tests: load config + session → ingest pipeline dry-run verifying templates expansion.
- Coverage: ≥ 95% of validation logic.

## 7. Rationale & Context

Hardware synchronization obviates per-frame timestamp generation, simplifying configuration (no sync section). Verification ensures integrity without constructing large timestamp arrays, reducing memory and CPU usage.

## 8. Dependencies & External Integrations

### External Systems

- EXT-001: Filesystem access for paths.

### Third-Party Services

- SVC-001: None directly; downstream may use ffmpeg referenced implicitly.

### Infrastructure Dependencies

- INF-001: Local disk with sufficient throughput for video IO.

### Data Dependencies

- DAT-001: Presence of per-session `session.toml` for template expansion.
- DAT-002: Optional presence of Bpod .mat file when `bpod.parse=true`.

### Technology Platform Dependencies

- PLT-001: Python runtime supporting Pydantic (≥ v2 expected).

### Compliance Dependencies

- COM-001: No PII; config should not store subject names beyond anonymized IDs.

## 9. Examples & Edge Cases

```code
# Edge case: enable transcode but omit codec (invalid)
[video.transcode]
enabled = true
crf = 20

# Valid minimal config (strict)
[project]
name = "w2t-bkin-pipeline"

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
metadata_file = "session.toml"
models_root = "models"

[verification]
mismatch_tolerance_frames = 0
warn_on_mismatch = false

[bpod]
parse = true

[acquisition]
concat_strategy = "ffconcat"

[video.transcode]
enabled = true
codec = "h264"
crf = 20
preset = "fast"
keyint = 15

[nwb]
link_external_video = true
lab = "Lab Name"
institution = "Institution Name"
file_name_template = "{session.id}.nwb"
session_description_template = "Session {session.id} on {session.date}"

[qc]
generate_report = true
out_template = "qc/{session.id}"
include_verification = true

[logging]
level = "INFO"
structured = false

[labels.dlc]
run_inference = false
model = "model.pb"

[labels.sleap]
run_inference = false
model = "sleap.h5"

[facemap]
run_inference = false
ROIs = ["face", "left_eye", "right_eye"]
```

## 10. Validation Criteria

- All required sections present.
- Types match schema (e.g., integers where required).
- Templates compile with example session metadata.
- No disallowed keys (e.g., secrets).

## 11. Related Specifications / Further Reading

- `spec-session-toml.md`
- Requirements document (`requirements.md`)
- Design document (`design.md`)
