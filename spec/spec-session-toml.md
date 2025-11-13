---
title: Session TOML Specification (W2T BKin)
version: 1.0
date_created: 2025-11-10
last_updated: 2025-11-10
owner: pipeline-team
tags: [schema, session, design]
---

# Introduction

This specification defines the structure and constraints of the per-session `session.toml` file
that captures session-specific metadata and file patterns. It enables flexible processing for
sessions with differing camera sets, TTL logs, and auxiliary data while maintaining consistent
validation rules.

## 1. Purpose & Scope

Purpose: Provide a clear, unambiguous schema for `session.toml` used during ingestion and
verification. Scope: Single session metadata and file discovery patterns.

## 2. Definitions

- Session: A single recording instance with one or more cameras and TTL logs.
- TTL: Pulse log used to count frames; one `ttl_id` SHOULD exist per camera.
- Pattern: Glob pattern resolved relative to repository `paths.raw_root`.

## 3. Requirements, Constraints & Guidelines

- REQ-001: The session file MUST contain exactly the following sections and keys:
  - `[session]`: `id`, `subject_id`, `date`, `experimenter`, `description`, `sex`, `age`, `genotype`
  - `[bpod]`: `path`, `order`
  - `[[bpod.trial_types]]`: `description`, `trial_type`, `sync_signal`, `sync_ttl`
  - `[[TTLs]]`: `id`, `description`, `paths`
  - `[[cameras]]`: `id`, `description`, `paths`, `order`, `ttl_id`
- REQ-002: No additional or missing keys are allowed in any section.
- REQ-003: All path patterns MUST be relative to the session root under `paths.raw_root`.
- REQ-004: Each camera MUST reference a `ttl_id` that exists in `[[TTLs]]`.
- REQ-005: bpod MUST identify trial types with `[[bpod.trial_types]]` and the sync TTL.
- CON-001: No absolute subject PII allowed; `session.subject_id` SHOULD be anonymized.
- GUD-001: `order` SHOULD be one of `name_asc`, `name_desc`, `mtime_asc`, `mtime_desc`.
- PAT-001: Name TTL ids clearly (e.g., `ttl_camera`, `ttl_hitmiss`).

## 4. Interfaces & Data Contracts

Schema outline (strict):

session: { id: str, subject_id: str, date: str, experimenter: str, description: str, sex: str, age: str, genotype: str }
bpod: { path: str, order: str }
TTLs: [ { id: str, description: str, paths: str } ]
cameras: [ { id: str, description: str, paths: str, order: str, ttl_id: str } ]

## 5. Acceptance Criteria

- AC-001: Given a session file with two cameras and TTL mappings, ingestion discovers at least one
  video file per camera and at least one TTL file per `ttl_id`.
- AC-002: When a camera lacks a matching `ttl_id`, the system logs a warning and flags the camera as
  unverifiable.
- AC-003: When no videos match a camera's `paths`, ingestion fails with `MissingInputError`.
- AC-004: When `bpod.path` is set but no files match, ingestion warns and continues without Bpod tables.

## 6. Test Automation Strategy

- Unit tests: schema validation for cameras/TTLs; cross-reference `ttl_id` resolution.
- Integration tests: synthetic data tree with cameras and TTLs; verify globbing and mapping.
- Property tests: randomized camera ids and TTL ids; ensure uniqueness and resolution.

## 7. Rationale & Context

Per-session TOML enables flexible discovery and mapping from videos to TTL logs without central
configuration churn. TTL per camera provides robust verification while using FPS-derived timing for
NWB.

## 8. Dependencies & External Integrations

### External Systems

- EXT-001: Filesystem for glob expansion under `paths.raw_root`.

### Third-Party Services

- SVC-001: None.

### Infrastructure Dependencies

- INF-001: Directory structure consistent with lab conventions.

### Data Dependencies

- DAT-001: Presence of actual video files and TTL logs matching declared patterns.

### Technology Platform Dependencies

- PLT-001: Python runtime for ingestion utilities.

### Compliance Dependencies

- COM-001: Anonymized subject identifiers where applicable.

## 9. Examples & Edge Cases

```code
[session]
id = "SNA-145518"
subject_id = "mouse_123"
date = "2025-01-01"

[bpod]
path = "Bpod/*.mat"
order = "name_asc"

[[bpod.trial_types]]
description = "Active wisker touch trials"
trial_type = 1
sync_signal = "W2L_Audio"
sync_ttl = "ttl_cue"

[[bpod.trial_types]]
description = "Passive wisker touch trials"
trial_type = 2
sync_signal = "A2L_Audio"
sync_ttl = "ttl_cue"


[[TTLs]]
id = "cam0_sync"
role = "camera_sync"
paths = "TTLs/cam0_*_sync.txt"

[[cameras]]
id = "cam0"
paths = "Video/top/*.avi"
expected_fps = 25.0
ttl_id = "cam0_sync"

# Edge case: camera without ttl_id (verification warns)
[[cameras]]
id = "cam2"
paths = "Video/side/*.avi"
expected_fps = 30.0
```

## 10. Validation Criteria

- Unique camera ids; unique TTL ids.
- All referenced `ttl_id` exist in `[[TTLs]]`.
- No extra or missing keys in any section.
- Globs do not escape session directory.

## 11. Related Specifications / Further Reading

- `spec-config-toml.md`
- Requirements document (`requirements.md`)
- Design document (`design.md`)
