---
post_title: "Utils Module — Foundation Utilities (W2T BKin)"
author1: "Project Team"
post_slug: "utils-module-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline", "utils"]
tags: ["utils", "foundation", "helpers"]
ai_note: "Generated from design and API specifications."
summary: "Foundation utilities providing JSON/CSV I/O, file hashing, git provenance, timing, and logging for the W2T BKin pipeline."
post_date: "2025-11-09"
---

# Utils Module — Foundation Utilities

## Overview

The `w2t_bkin.utils` module provides foundational utility functions used across all pipeline stages. As a **Layer 0** foundation module, it **must not import any other project packages**, ensuring zero circular dependencies.

**Design Principle**: Pure, stateless helper functions with no side effects beyond I/O operations.

## Purpose

According to the design (`design.md` §2, §21.1):

- Provides reusable primitives for file I/O, hashing, provenance capture, timing, and logging
- Acts as a foundation layer (Layer 0) with no dependencies on other project packages
- Supports reproducibility (NFR-1), observability (NFR-3), and provenance (NFR-11)

## Public API

See full API documentation in `api.md` §3.2. Key functions:

- **JSON I/O**: `read_json()`, `write_json()` — NFR-3, Design §8
- **CSV I/O**: `write_csv()` — Design §3.2, §3.5
- **File Hashing**: `file_hash()` — NFR-1, NFR-8, NFR-11
- **Git Provenance**: `get_commit()` — NFR-11, Design §11
- **Timing**: `time_block()` — NFR-3, NFR-4, Design §7
- **Logging**: `configure_logging()` — NFR-3, Design §7

## Design Constraints

### No Internal Dependencies

As a Layer 0 foundation module, `utils` **must not import**:

- `w2t_bkin.config`
- `w2t_bkin.domain`
- Any processing stage (`ingest`, `sync`, `pose`, etc.)

Only external libraries and Python standard library are allowed.

### Stateless Functions

All functions should be:

- **Pure** where possible (deterministic outputs for given inputs)
- **Stateless** (no module-level mutable state)
- **Thread-safe** (safe for concurrent use)

### Error Handling

- Raise standard Python exceptions (`FileNotFoundError`, `ValueError`, `OSError`)
- Do not use custom pipeline exceptions from `domain` (to avoid circular dependency)
- Include descriptive error messages with file paths when applicable

## Testing Strategy

Unit tests for `utils` (see `tests/unit/test_utils.py`):

1. **JSON I/O**: Round-trip serialization, error handling for malformed JSON
2. **CSV I/O**: Field ordering, empty input handling, special characters
3. **File Hashing**: Consistency across runs, algorithm validation, large file handling
4. **Git Provenance**: Repository detection, fallback to "unknown"
5. **Timing**: Accuracy of elapsed time measurement, logger integration
6. **Logging**: Configuration validation, structured format toggle

## Usage Examples

### Manifest Persistence (Ingest Stage)

```python
from w2t_bkin.utils import write_json, file_hash

manifest_data = {...}  # Manifest dict
write_json(output_dir / "manifest.json", manifest_data)

# Optional: compute hash for caching
manifest_hash = file_hash(output_dir / "manifest.json")
```

### Timestamp CSV Export (Sync Stage)

```python
from w2t_bkin.utils import write_csv

timestamps = [
    {"frame_index": 0, "timestamp": 0.0000},
    {"frame_index": 1, "timestamp": 0.0333},
]
write_csv(output_dir / "timestamps_cam0.csv", timestamps, fieldnames=["frame_index", "timestamp"])
```

### Performance Profiling (Any Stage)

```python
from w2t_bkin.utils import time_block
import logging

logger = logging.getLogger(__name__)

with time_block("TTL parsing", logger=logger):
    parse_ttl_logs(sync_files)
```

### Provenance Capture (NWB Stage)

```python
from w2t_bkin.utils import get_commit

provenance = {
    "git_commit": get_commit(),
    "pipeline_version": "0.1.0",
    "timestamp": datetime.now().isoformat()
}
```

## Dependencies

**Standard Library Only**:

- `json` — JSON serialization
- `csv` — CSV I/O
- `hashlib` — File hashing
- `pathlib` — Path handling
- `subprocess` — Git command execution
- `time`, `contextlib` — Timing utilities
- `logging` — Logging configuration

**No External Dependencies** — `utils` must remain lightweight.

## Maintenance Notes

- Keep functions focused and single-purpose
- Avoid feature creep (complex transformations belong in stage modules)
- Document all public functions with Requirements/Design traceability
- Maintain 100% unit test coverage

## Related Documentation

- **Design**: `/design.md` §8 (Performance), §7 (Logging), §11 (Provenance)
- **API**: `/api.md` §3.2 (Utils Module API)
- **Tests**: `/tests/unit/test_utils.py`

---

**Last Updated**: 2025-11-09  
**Status**: Foundation module (Layer 0)
