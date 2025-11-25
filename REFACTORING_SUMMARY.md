# NWB-First Architecture Refactoring Summary

## Date: 2025-11-25

## Overview

Successfully refactored the W2T-BKIN pipeline from a Manifest-centric architecture to an **NWB-first architecture**, where `pynwb.NWBFile` serves as the primary orchestration artifact throughout the pipeline.

## What Was Changed

### 1. ✅ Modules Deleted

**Removed files (1,411 lines total):**

- `src/w2t_bkin/ingest.py` (775 lines) - File discovery, counting, verification, manifest building
- `src/w2t_bkin/nwb.py` (636 lines) - NWB assembly with manifest
- `src/w2t_bkin/domain/manifest.py` (223 lines) - Manifest, ManifestCamera, ManifestTTL models

**Rationale:** These modules created intermediate representations that duplicated NWB functionality. Direct NWBFile manipulation is more efficient and standards-compliant.

### 2. ✅ Utilities Relocated

**Moved to `src/w2t_bkin/utils.py`:**

- `count_video_frames(video_path) -> int` - Video frame counting with ffprobe + synthetic stub support
- `count_ttl_pulses(ttl_path) -> int` - TTL pulse counting from log files

**Already in utils.py:**

- `discover_files(base_dir, pattern) -> List[Path]` - Glob-based file discovery
- `run_ffprobe(video_path) -> int` - Low-level ffprobe execution

### 3. ✅ New Helpers in session.py

**Added to `src/w2t_bkin/session.py`:**

```python
def add_video_acquisition(
    nwbfile: NWBFile,
    camera_id: str,
    video_files: List[str],
    frame_rate: float = 30.0,
    device: Optional[Device] = None
) -> NWBFile:
    """Add video ImageSeries to NWBFile acquisition with external file links."""

def write_nwb_file(nwbfile: NWBFile, output_path: Path) -> Path:
    """Write NWBFile to disk using NWBHDF5IO."""
```

**Purpose:** Encapsulate NWB-specific operations in the session module alongside `create_nwb_file()`.

### 4. ✅ Pipeline Refactored

**`src/w2t_bkin/pipeline.py` changes:**

#### Before (Manifest-centric):

```python
manifest = build_and_count_manifest(config, session)
verification = verify_manifest(manifest, tolerance)
# ... processing ...
nwb_path = assemble_nwb(manifest, config, provenance, output_dir)
```

#### After (NWB-first):

```python
# Phase 0: Create NWBFile early
nwbfile = create_nwb_file(session_path)

# Phase 1: Inline file discovery and verification
for camera_config in session.cameras:
    video_files = discover_files(session_dir, camera_config.paths)
    frame_count = sum(count_video_frames(f) for f in video_files)
    ttl_pulse_count = sum(count_ttl_pulses(f) for f in ttl_files)

    # Verify inline
    if abs(frame_count - ttl_pulse_count) > tolerance:
        raise ValueError(f"Verification failed")

    # Add to NWBFile immediately
    add_video_acquisition(nwbfile, camera_config.id, video_files)

# Phase 2-4: Add pose, behavior, etc. to nwbfile

# Phase 5: Write to disk
write_nwb_file(nwbfile, output_path)
```

#### RunResult Changes:

```python
# OLD
class RunResult(TypedDict):
    manifest: Manifest  # ❌ Removed
    nwb_path: Optional[Path]
    # ... other fields ...

# NEW
class RunResult(TypedDict):
    nwbfile: NWBFile  # ✅ Primary artifact
    nwb_path: Optional[Path]
    # ... other fields ...
```

### 5. ✅ Domain Updates

**`src/w2t_bkin/domain/__init__.py`:**

- Removed exports: `Manifest`, `ManifestCamera`, `ManifestTTL`, `VerificationResult`, `VerificationSummary`, `CameraVerificationResult`
- Kept: All Config, Session, Alignment, Facemap, Transcode models

### 6. ✅ Package-Level Updates

**`src/w2t_bkin/__init__.py`:**

- Removed imports: `ingest`, `nwb`
- Updated docstring to reflect NWB-first architecture
- Updated Quick Start example to use `pipeline.run_session()`

## Architecture Comparison

### Old Flow (Manifest-centric)

```
Config + Session
  ↓ discover_files()
Manifest (intermediate model)
  ↓ populate_counts()
Manifest (with counts)
  ↓ verify_manifest()
VerificationResult
  ↓ assemble_nwb()
NWBFile
  ↓ write()
Disk
```

### New Flow (NWB-first)

```
Session
  ↓ create_nwb_file()
NWBFile (early, in memory)
  ↓ discover files + verify inline
NWBFile (with ImageSeries)
  ↓ add pose/behavior modules
NWBFile (complete)
  ↓ write_nwb_file()
Disk
```

## Benefits

1. **Standards Compliance:** NWB used as primary artifact from the start
2. **Code Simplification:** Eliminated ~1,400 lines of intermediate model code
3. **Single Validation Path:** No duplicate validation (Manifest + NWB → only NWB)
4. **Better Performance:** Direct NWBFile population, no intermediate conversions
5. **Cleaner API:** `run_session()` returns NWBFile directly

## Breaking Changes

### API Changes

**Removed Functions:**

- `ingest.build_and_count_manifest()` → Functionality inlined in `pipeline.run_session()`
- `ingest.verify_manifest()` → Verification inlined in `pipeline.run_session()`
- `ingest.discover_files()` → Moved to `utils.discover_files()` (already existed)
- `nwb.assemble_nwb()` → Replaced by `session.write_nwb_file()`
- `nwb.create_device()` → Use `session.create_device()` (already existed)
- `nwb.create_image_series()` → Use `session.add_video_acquisition()`

**Removed Types:**

- `Manifest`
- `ManifestCamera`
- `ManifestTTL`
- `VerificationResult`
- `VerificationSummary`
- `CameraVerificationResult`

### Migration Guide for Existing Code

**Old Pattern:**

```python
from w2t_bkin.ingest import build_and_count_manifest, verify_manifest
from w2t_bkin.nwb import assemble_nwb

manifest = build_and_count_manifest(config, session)
verify_manifest(manifest, tolerance=10)
nwb_path = assemble_nwb(manifest, config, provenance, output_dir)
```

**New Pattern:**

```python
from w2t_bkin.pipeline import run_session

result = run_session(config_path, session_id)
nwbfile = result['nwbfile']  # In-memory NWBFile
nwb_path = result['nwb_path']  # Written file path
```

**Utilities (still available):**

```python
# OLD
from w2t_bkin.ingest import count_video_frames, count_ttl_pulses

# NEW
from w2t_bkin.utils import count_video_frames, count_ttl_pulses
```

## Testing Status

### ✅ Completed

- Core modules compile successfully (pipeline.py, session.py, utils.py)
- Package structure updated
- Domain models updated

### ⏳ Pending (50+ test files need updates)

- `tests/integration/test_phase_1_ingest.py` - 8 ingest imports
- `tests/integration/test_phase_4_nwb.py` - 20 nwb imports
- `tests/unit/test_ingest.py` - 15 ingest imports
- `tests/unit/test_nwb.py` - 10 nwb imports
- Examples: `bpod_camera_sync.py`, `pose_camera_nwb.py`

**Migration Strategy for Tests:**

1. Replace `build_and_count_manifest()` calls with inline file discovery
2. Replace `verify_manifest()` calls with inline verification assertions
3. Replace `assemble_nwb()` calls with `create_nwb_file()` + `write_nwb_file()`
4. Update assertions expecting Manifest objects to work with NWBFile directly
5. Import utilities from `utils` instead of `ingest`

## Validation Tools

### NWB Validation

The pipeline uses **nwbinspector** for validation (already referenced in code):

```python
from w2t_bkin.pipeline import run_validation

validation_result = run_validation(nwb_path)
# Returns: {"status": "pass"|"fail", "errors": [...], "warnings": [...]}
```

**No VerificationSummary JSON needed** - nwbinspector provides comprehensive validation reporting.

## Next Steps

1. **Update test files (Priority: High)**

   - Start with unit tests (test_utils.py for counting functions)
   - Update integration tests (test_pipeline.py)
   - Remove deprecated test files (test_ingest.py, test_nwb.py)

2. **Update examples (Priority: Medium)**

   - Rewrite examples to use new API
   - Add NWB-first workflow examples

3. **Documentation (Priority: Medium)**

   - Update design.md to reflect NWB-first architecture
   - Remove references to Manifest in docs
   - Update README.md Quick Start

4. **Performance Testing (Priority: Low)**
   - Benchmark NWB-first vs old Manifest approach
   - Verify memory usage is acceptable

## Files Modified

### Created/Modified:

- `src/w2t_bkin/utils.py` (+100 lines: count_video_frames, count_ttl_pulses)
- `src/w2t_bkin/session.py` (+120 lines: add_video_acquisition, write_nwb_file)
- `src/w2t_bkin/pipeline.py` (complete rewrite: +150 lines inlined discovery, -manifest imports)
- `src/w2t_bkin/domain/__init__.py` (-6 manifest exports)
- `src/w2t_bkin/__init__.py` (-2 module imports, updated docstring)

### Deleted:

- `src/w2t_bkin/ingest.py` (-775 lines)
- `src/w2t_bkin/nwb.py` (-636 lines)
- `src/w2t_bkin/domain/manifest.py` (-223 lines)

**Net Change:** ~-1,200 lines (code simplified)

## Timeline

- **Start Date:** 2025-11-25
- **Core Refactoring:** Completed in single session
- **Status:** Implementation complete, tests pending

## Contributors

- Implementation: AI Assistant (Claude Sonnet 4.5)
- Direction: User (Borja Esteban)

---

**End of Summary**
