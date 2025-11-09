---
post_title: "Domain Module — Data Contracts (W2T BKin)"
author1: "Project Team"
post_slug: "domain-module-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "domain"]
tags: ["domain", "contracts", "data-models"]
ai_note: "Generated from design and API specifications."
summary: "Domain data contracts and pure data structures for the W2T BKin pipeline, providing type-safe boundaries between stages."
post_date: "2025-11-09"
---

# Domain Module — Data Contracts

## Overview

The `w2t_bkin.domain` module provides pure data structures representing domain entities and contracts between pipeline stages. As a **Layer 0** foundation module, it **must not import any other project packages**, ensuring zero circular dependencies.

**Design Principle**: Immutable, validated data classes with no business logic beyond structural constraints.

## Purpose

According to the design (`design.md` §3, §21.1):

- Defines contracts between all pipeline stages
- Ensures type safety and data validation at boundaries
- Acts as a foundation layer (Layer 0) with no dependencies on other project packages
- Supports reproducibility (NFR-1), data integrity (NFR-8), and modularity (NFR-7)

## Public API

See full API documentation in `api.md` §3.1. All classes are frozen dataclasses with validation:

### Video & Manifest Contracts

- **`VideoMetadata`** — Single camera video metadata with validation (FR-1)
- **`Manifest`** — Session manifest with all inputs and provenance (FR-1, NFR-1)

### Synchronization Contracts

- **`TimestampSeries`** — Per-camera frame timestamps with monotonic validation (FR-2)
- **`SyncSummary`** — Synchronization quality statistics and warnings (FR-3)

### Pose Contracts

- **`PoseSample`** — Single pose keypoint observation with confidence (FR-5)
- **`PoseTable`** — Harmonized pose table with skeleton metadata (FR-5)

### Facemap Contracts

- **`FacemapMetrics`** — Facial metrics time series (FR-6)

### Events & Trials Contracts

- **`Event`** — Behavioral event with timestamp and payload (FR-11)
- **`Trial`** — Trial interval with QC metadata (FR-11)

### NWB & QC Contracts

- **`NWBAssemblyOptions`** — NWB file assembly configuration (FR-7, FR-10)
- **`QCReportSummary`** — QC report structure with optional sections (FR-8)

## Design Constraints

### No Internal Dependencies

As a Layer 0 foundation module, `domain` **must not import**:

- `w2t_bkin.config`
- `w2t_bkin.utils`
- Any processing stage (`ingest`, `sync`, `pose`, etc.)

Only external libraries and Python standard library are allowed.

### Immutability

All domain classes are **frozen dataclasses**:

- Ensures thread safety
- Supports reproducibility (NFR-1)
- Prevents accidental mutation
- Enables hashability for caching

### Validation

All classes include `__post_init__` validation:

- **Structural constraints** — Non-empty strings, positive numbers, valid ranges
- **Data integrity** — Monotonic timestamps, matching array lengths
- **Business rules** — Confidence in [0,1], non-negative times

### Error Handling

- Raise standard `ValueError` for validation failures
- Include descriptive error messages with actual values
- No custom exceptions (to avoid circular dependencies)

## Data Contract Examples

### VideoMetadata

```python
from pathlib import Path
from w2t_bkin.domain import VideoMetadata

video = VideoMetadata(
    camera_id=0,
    path=Path("/data/cam0.mp4"),
    codec="h264",
    fps=30.0,
    duration=60.0,
    resolution=(1920, 1080)
)

# Validation ensures:
# - camera_id >= 0
# - fps > 0
# - duration >= 0
# - resolution is (width>0, height>0)
```

### Manifest

```python
from w2t_bkin.domain import Manifest, VideoMetadata

manifest = Manifest(
    session_id="session_001",
    videos=[video0, video1, video2, video3, video4],
    sync=[{"path": "/data/sync_ttl.csv", "type": "ttl"}],
    pose=[{"path": "/data/pose_dlc.h5", "format": "dlc"}],  # Optional
    facemap=[{"path": "/data/facemap.npy"}],  # Optional
    events=[{"path": "/data/events.ndjson", "kind": "ndjson"}],  # Optional
    config_snapshot={"n_cameras": 5},
    provenance={"git_commit": "abc1234"}
)

# Validation ensures:
# - session_id is non-empty
# - videos list is non-empty
# - sync list is non-empty
```

### TimestampSeries

```python
from w2t_bkin.domain import TimestampSeries

timestamps = TimestampSeries(
    frame_index=[0, 1, 2, 3],
    timestamp_sec=[0.0, 0.0333, 0.0666, 0.1000]
)

# Validation ensures:
# - Equal length arrays
# - Non-empty
# - Strictly monotonic increasing timestamps

# Computed properties:
duration = timestamps.duration  # 0.1000 seconds
n_frames = timestamps.n_frames  # 4
```

### PoseSample & PoseTable

```python
from w2t_bkin.domain import PoseSample, PoseTable

# Single pose observation
sample = PoseSample(
    time=1.0,
    keypoint="nose",
    x_px=320.5,
    y_px=240.2,
    confidence=0.95  # Must be in [0, 1]
)

# Collection with metadata
table = PoseTable(
    records=[sample1, sample2, sample3],
    skeleton_meta={"model": "dlc", "skeleton": "mouse_topdown"}
)

# Computed properties:
n_samples = table.n_samples
keypoints = table.keypoints  # Set of unique keypoint names
```

### FacemapMetrics

```python
from w2t_bkin.domain import FacemapMetrics

metrics = FacemapMetrics(
    time=[0.0, 0.033, 0.066],
    metric_columns={
        "pupil_area": [100.0, 105.0, 102.0],
        "motion_energy": [0.5, 0.6, 0.55]
    }
)

# Validation ensures:
# - time is non-empty
# - All metric columns have same length as time

# Computed properties:
n_samples = metrics.n_samples  # 3
metric_names = metrics.metrics  # ["pupil_area", "motion_energy"]
```

### Event & Trial

```python
from w2t_bkin.domain import Event, Trial

# Behavioral event
event = Event(
    time=5.0,
    kind="reward",
    payload={"amount": 1, "valve": "left"}
)

# Trial interval with QC
trial = Trial(
    trial_id=1,
    start_time=10.0,
    stop_time=15.0,
    phase_first="baseline",
    phase_last="stimulus",
    declared_duration=5.0,
    observed_span=5.02,
    duration_delta=0.02,
    qc_flags=["slight_duration_mismatch"]
)

# Computed properties:
duration = trial.duration  # 5.0 seconds
```

## Testing Strategy

Unit tests for `domain` (see `tests/unit/test_domain.py`):

1. **Creation tests** — Valid construction with all required fields
2. **Validation tests** — Constraint enforcement (ranges, lengths, types)
3. **Immutability tests** — Frozen dataclass behavior
4. **Computed properties** — Property calculations and edge cases
5. **Edge cases** — Empty data, boundary values, optional fields
6. **Integration** — Complex manifests with all optional components

**All 41 tests pass** ✅

## Usage Patterns

### Stage Input Contracts

Stages consume domain contracts as inputs:

```python
# ingest stage produces
from w2t_bkin.domain import Manifest, VideoMetadata

def build_manifest(...) -> Manifest:
    videos = [VideoMetadata(...) for cam in cameras]
    return Manifest(session_id=..., videos=videos, sync=...)
```

### Stage Output Contracts

Stages produce domain contracts as outputs:

```python
# sync stage produces
from w2t_bkin.domain import TimestampSeries, SyncSummary

def compute_timestamps(...) -> tuple[list[TimestampSeries], SyncSummary]:
    ts = [TimestampSeries(...) for cam in cameras]
    summary = SyncSummary(...)
    return ts, summary
```

### NWB Assembly

NWB stage consumes multiple contracts:

```python
from w2t_bkin.domain import (
    Manifest,
    TimestampSeries,
    PoseTable,
    FacemapMetrics,
    NWBAssemblyOptions
)

def assemble_nwb(
    manifest: Manifest,
    timestamps: list[TimestampSeries],
    pose: PoseTable | None = None,
    facemap: FacemapMetrics | None = None,
    options: NWBAssemblyOptions = NWBAssemblyOptions()
) -> Path:
    ...
```

## Dependencies

**Standard Library Only**:

- `dataclasses` — Frozen dataclass decorator
- `pathlib` — Path type for file references
- `typing` — Type hints (Any, field)

**No External Dependencies** — `domain` must remain lightweight.

## Maintenance Notes

- Keep classes focused on data structure and validation
- No business logic or transformations (those belong in stage modules)
- Document all validation rules in docstrings
- Link requirements (FR-X) and design sections (§X) in docstrings
- Maintain 100% unit test coverage

## Validation Rules Reference

| Class | Field | Validation Rule |
|-------|-------|-----------------|
| `VideoMetadata` | `camera_id` | >= 0 |
| | `fps` | > 0 |
| | `duration` | >= 0 |
| | `resolution` | Both dimensions > 0 |
| `Manifest` | `session_id` | Non-empty string |
| | `videos` | Non-empty list |
| | `sync` | Non-empty list |
| `TimestampSeries` | Arrays | Equal length, non-empty |
| | `timestamp_sec` | Strictly monotonic increasing |
| `SyncSummary` | `per_camera_stats` | Non-empty dict |
| `PoseSample` | `confidence` | In range [0, 1] |
| | `keypoint` | Non-empty string |
| `PoseTable` | `records` | Non-empty list |
| `FacemapMetrics` | `time` | Non-empty list |
| | `metric_columns` | All same length as `time` |
| `Event` | `kind` | Non-empty string |
| | `time` | >= 0 |
| `Trial` | `start_time` | >= 0 |
| | `stop_time` | > `start_time` |

## Related Documentation

- **Design**: `/design.md` §3 (Data Contracts), §21.1 (Dependency Tree)
- **API**: `/api.md` §3.1 (Domain Module API)
- **Requirements**: `/requirements.md` (FR-1 through FR-11)
- **Tests**: `/tests/unit/test_domain.py`

---

**Last Updated**: 2025-11-09  
**Status**: Foundation module (Layer 0) — Fully implemented and tested
