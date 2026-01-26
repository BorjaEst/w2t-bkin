# Design

## Problem Summary

Session processing can fail during `TaskRecording` construction with an HDMF `docval` error:

`incorrect type for 'events' (got 'EventsTable', expected 'EventsTable')`

This happens when two different Python classes share the same display name `EventsTable`, commonly:

- TTL events table: `ndx-events.EventsTable`
- Behavioral events table: `ndx-structured-behavior.EventsTable`

In addition, repeated namespace loading (e.g., editable installs or worker isolation) can create multiple distinct Python class objects for the _same_ NWB neurodata type, leading to class identity mismatches.

## Architecture / Approach

### Key Idea

Use PyNWB’s runtime type map as the source of truth for ndx-structured-behavior classes, and validate inputs against the exact types expected by the runtime-generated `TaskRecording` constructor.

### Implementation Elements

- A small resolver helper:
  - `_sb_get_class(neurodata_type)` → `pynwb.get_class(neurodata_type, "ndx-structured-behavior")`

- Input validation in `build_task_recording`:
  - Extract expected types from `TaskRecording.__init__.__docval__`
  - Check `isinstance(...)` for `states`, `events`, and `actions`
  - Raise `TypeError` with a detailed, actionable message when mismatched

- Construct key ndx-structured-behavior objects via the type map:
  - `StatesTable`, `EventsTable`, `ActionsTable`, `TrialsTable`, `TaskArgumentsTable`, `Task`

## Sequence (Behavior Assembly)

1. Extract Bpod types (`StateTypesTable`, `EventTypesTable`, `ActionTypesTable`)
2. Extract occurrences (`StatesTable`, `EventsTable`, `ActionsTable`)
3. Build `TaskRecording` (validated types)
4. Build `TrialsTable` referencing the tables inside `TaskRecording`
5. Build `Task` referencing type tables + optional arguments

## Error Handling

- For mismatched `events` type:
  - Raise `TypeError` including fully qualified types
  - If `ndx_events` is detected in the provided type, include a hint about TTL vs behavioral mix-up and the `TTLEvents` container

## Testing Strategy

- Unit regression test ensures `build_task_recording` rejects an `ndx-events.EventsTable` with a clear message.

### Decision - 2026-01-20

**Decision**: Fail fast with explicit `TypeError` and actionable message; do not attempt auto-conversion between `ndx-events` and `ndx-structured-behavior` tables.
**Rationale**: These tables represent different schemas and semantics; auto-conversion would be lossy/incorrect and could hide wiring bugs.
**Impact**: Faster debugging, clearer operator experience; pipeline fails earlier with an informative message.
**Review**: Revisit if a future workflow legitimately requires mapping TTL tables into behavioral events.

# Design

## Overview

`build_pose_estimation` accepts pose frames + metadata and returns an ndx-pose `PoseEstimation`.

Although ndx-pose technically allows `PoseEstimation(skeleton=None)`, ndx-pose properties like `PoseEstimation.nodes` and `PoseEstimation.edges` dereference `PoseEstimation.skeleton` directly. Returning an object without a skeleton is therefore incorrect for typical usage.

The design is:

- Make `skeleton` optional in `build_pose_estimation`.
- If omitted, auto-create a valid skeleton from detected bodyparts.

## Auto-Created Skeleton

If `skeleton is None`:

- `nodes`: detected `bodyparts` (stable ordering as produced by bodypart derivation)
- `edges`: empty
- `name`: deterministic uuid5-derived name

## Deterministic Naming

Random UUIDs prevent collisions but break reproducibility and prevent downstream deduplication-by-name.

Use `uuid.uuid5(uuid.NAMESPACE_URL, key_string)` where:

`key_string = "w2t_bkin|pose|{source_software}|{source_software_version}|{scorer}|{','.join(bodyparts)}"`

Resulting name:

`subject_{uuid_hex[:8]}`

This is stable across runs for identical inputs.

## Compatibility

- Callers that already pass a skeleton are unchanged.
- Validation for missing bodyparts in a provided skeleton is preserved.

## Bpod Ingestion Robustness

### Problem

SciPy's `loadmat(..., struct_as_record=False, squeeze_me=True)` commonly returns MATLAB structs as `mat_struct` objects. These behave like attribute objects (no `dict.get`), so any code treating `SessionData` as a mapping can crash.

### Approach

- Normalize Bpod `SessionData` for both single-file and multi-file ingestion so downstream code sees a consistent structure.
- In the data model, treat `SessionData` as "MATLAB struct or dict" and convert via `convert_matlab_struct` at access boundaries.

### Key Outcome

`BpodData.n_trials` must be safe regardless of whether `SessionData` is a dict or MATLAB struct object.
