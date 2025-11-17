# W2T-BKIN Examples - Status and Test Results

## Summary

This document tracks the status of all examples in the `examples/` directory after API alignment fixes.

**Last Updated**: 2025-01-17

## Working Examples

### ✅ 01_happy_path_end_to_end.py

**Status**: WORKING

**Description**: Complete end-to-end pipeline from synthetic data generation through alignment stats

**Test Result**: All phases complete successfully

- Phase 0: Setup - synthetic session with 200 frames ✓
- Phase 1: Ingest - manifest building ✓
- Phase 2: Verify - frame/TTL alignment check ✓
- Phase 3: Sync - alignment stats creation ✓
- Phase 4: Summary - artifact generation ✓

**Outputs**:

- `temp/examples/01_happy_path/output/verification_summary.json`
- `temp/examples/01_happy_path/output/alignment_stats.json`

**Notes**:

- NWB assembly and validation not yet implemented (marked with note in example)
- Uses mock alignment values for demonstration

**Run Command**:

```bash
python examples/01_happy_path_end_to_end.py
```

---

### ✅ 02_multi_camera_session.py

**Status**: WORKING

**Description**: Multi-camera session with separate TTL channels per camera

**Test Result**: All phases complete successfully

- Phase 0: Generate 2-camera synthetic data ✓
- Phase 1: Load config and session ✓
- Phase 2: Fast discovery (no counting) ✓
- Phase 3: Slow counting ✓
- Phase 4: Cross-reference validation ✓
- Phase 5: Per-camera verification ✓
- Phase 6: Write verification summary ✓

**Outputs**:

- `temp/examples/02_multi_camera/output/verification_summary.json`
- `temp/examples/02_multi_camera/output/manifest.json`

**Configuration**:

- Environment variable `N_CAMERAS=4` to test with more cameras
- Environment variable `N_FRAMES=300` to test with more frames

**Run Command**:

```bash
python examples/02_multi_camera_session.py
# Or with custom settings:
N_CAMERAS=4 N_FRAMES=300 python examples/02_multi_camera_session.py
```

---

## Examples Requiring Fixes

### ⚠️ 03_jitter_budget_comparison.py

**Status**: NEEDS FIXES

**Required Changes**:

1. SyntheticSession attributes: `videos` → `camera_video_paths`, `ttls` → `ttl_paths`
2. Session model: `ttls` → `TTLs`, `camera.camera_id` → `camera.id`, `ttl.ttl_id` → `ttl.id`
3. VerificationResult: `cameras` → `camera_results`
4. Status values: `"OK"/"WARN"/"FAIL"` → `"pass"/"warn"/"fail"`

**Estimated Effort**: ~15 minutes (apply same fixes as examples 01 and 02)

---

### ⚠️ 11_ingest_and_verify.py

**Status**: NEEDS FIXES

**Required Changes**:
Same as 03_jitter_budget_comparison.py

**Estimated Effort**: ~10 minutes

---

### ❓ 21_verification_plots.py

**Status**: UNTESTED

**Description**: Visualization using `figures.ingest_verify` module

**Required Changes**:

- May need API alignment depending on figures package interface
- Test after fixing other examples

**Estimated Effort**: TBD after testing

---

### ❓ 22_alignment_plots.py

**Status**: UNTESTED

**Description**: Visualization using `figures.sync` module

**Required Changes**:

- May need API alignment depending on figures package interface
- Test after fixing other examples

**Estimated Effort**: TBD after testing

---

## Key API Fixes Applied

### SyntheticSession Structure

```python
# OLD (incorrect)
session.videos  # List[Path]
session.ttls    # List[Path]

# NEW (correct)
session.camera_video_paths  # Dict[str, Union[Path, List[Path]]]
session.ttl_paths          # Dict[str, Path]
```

### Session Model Attributes

```python
# OLD (incorrect)
session_data.ttls  # AttributeError

# NEW (correct)
session_data.TTLs  # Capitalized

# Camera attributes
camera.camera_id  # OLD
camera.id        # NEW

# TTL attributes
ttl.ttl_id  # OLD
ttl.id      # NEW
```

### ManifestTTL vs ManifestCamera

```python
# TTL pulse counts stored in ManifestCamera, not ManifestTTL
# ManifestTTL only has: ttl_id, files
# ManifestCamera has: camera_id, ttl_id, frame_count, ttl_pulse_count, ...
```

### VerificationResult Structure

```python
# OLD (incorrect)
verification.cameras  # AttributeError

# NEW (correct)
verification.camera_results  # List[CameraVerificationResult]
```

### Status Values

```python
# OLD (incorrect)
if result.status == "OK":    # Wrong
if result.status == "WARN":  # Wrong
if result.status == "FAIL":  # Wrong

# NEW (correct)
if result.status == "pass":  # Correct
if result.status == "warn":  # Correct
if result.status == "fail":  # Correct
```

### VerificationSummary Creation

```python
# verify_manifest returns VerificationResult
# write_verification_summary expects VerificationSummary

from w2t_bkin.domain.manifest import VerificationSummary
from datetime import datetime, timezone

verification = ingest.verify_manifest(manifest, tolerance=5)

# Must convert VerificationResult → VerificationSummary
summary = VerificationSummary(
    session_id=manifest.session_id,
    cameras=verification.camera_results,
    generated_at=datetime.now(timezone.utc).isoformat(),  # String, not datetime
)

ingest.write_verification_summary(summary, path)
```

### Sync API Usage

```python
# compute_alignment is a stub returning dict
# Use create_alignment_stats directly with explicit values

from w2t_bkin.sync import create_timebase_provider, create_alignment_stats

provider = create_timebase_provider(config, manifest)

# Mock alignment for happy path
alignment_stats = create_alignment_stats(
    timebase_source="ttl",
    mapping="nearest",
    offset_s=0.0,
    max_jitter_s=0.0001,
    p95_jitter_s=0.00005,
    aligned_samples=n_frames,
)
```

---

## Testing Checklist

- [x] Example 01: Happy path end-to-end
- [x] Example 02: Multi-camera session
- [ ] Example 03: Jitter budget comparison
- [ ] Example 11: Ingest and verify
- [ ] Example 21: Verification plots
- [ ] Example 22: Alignment plots

---

## Next Steps

1. **Apply fixes to examples 03 and 11** using the patterns from 01 and 02
2. **Test visualization examples 21 and 22** to verify figures package integration
3. **Document any additional API changes** discovered during testing
4. **Update examples/README.md** if necessary
5. **Consider adding integration tests** for all examples

---

## Notes

- All examples use pydantic-settings for configuration via environment variables
- Examples follow direct `if __name__ == "__main__"` pattern (no main() function)
- Root-level `figures` package used for visualization (not `w2t_bkin.figures`)
- NWB assembly and validation phases not yet implemented in w2t_bkin API
