# Caching and Reprocessing Guide

## Overview

The W2T-BKIN pipeline intelligently caches intermediate results to avoid redundant computation. This guide explains how caching works, when outputs are regenerated, and how to control this behavior.

## What Gets Cached?

The pipeline caches three types of outputs:

### 1. **Pose Estimation Results** (Intermediate)

**Location**: `data/interim/dlc-pose/{camera_id}/` or `data/interim/sleap-pose/{camera_id}/`

**Files**:

- DeepLabCut: `{video_stem}DLC_{model_name}_{...}.h5`
- SLEAP: `{video_stem}_sleap_{...}.h5`

**When cached**:

- If H5 file exists for a video, pose estimation is **skipped** by default
- GPU inference is expensive, so caching saves significant time

### 2. **Final NWB Files** (Output)

**Location**: `data/processed/{subject_id}/{session_id}/`

**Files**: `{session_id}.nwb` (or custom template from config)

**When cached**:

- NWB files are **always regenerated** during pipeline runs
- This ensures metadata updates are incorporated
- If you want to preserve old outputs, rename or move them first

### 3. **Session Artifacts** (Metadata)

**Location**: Various sidecar JSON files

**Files**:

- `alignment.json` - Synchronization statistics
- `provenance.json` - Processing history
- Validation reports

**When cached**:

- Regenerated with each pipeline run
- Used for QC and reproducibility tracking

---

## Default Caching Behavior

### Example: Processing a Session

```bash
# First run - generates everything
w2t-bkin run config.toml subject-001 session-001

# Output:
# ✓ Running DLC pose estimation (5 videos, ~10 min)
# ✓ Syncing TTLs
# ✓ Writing NWB file
```

```bash
# Second run - uses cached poses
w2t-bkin run config.toml subject-001 session-001

# Output:
# ✓ All DLC outputs cached (skipping inference)
# ✓ Syncing TTLs
# ✓ Writing NWB file
```

**Key point**: DLC/SLEAP inference is skipped, but NWB assembly runs again.

---

## Forcing Regeneration

### Method 1: Configuration File (Recommended)

Edit your `configuration.toml`:

```toml
[preprocessing]
force_rerun = true  # Regenerate all intermediate files
```

Then run normally:

```bash
w2t-bkin run config.toml subject-001 session-001
```

**What this does**:

- ✅ Regenerates DLC/SLEAP poses even if cached
- ✅ Reprocesses all intermediate artifacts
- ✅ Useful when you've updated models or fixed bugs

### Method 2: Delete Intermediate Folders

```bash
# Delete all cached poses for a session
rm -rf data/interim/dlc-pose/
rm -rf data/interim/sleap-pose/

# Or delete specific camera
rm -rf data/interim/dlc-pose/camera_0/
```

Then run normally - pipeline will regenerate missing files.

### Method 3: Via Python API

```python
from w2t_bkin.flows import process_session_flow, SessionFlowConfig

config = SessionFlowConfig(
    config_path="config.toml",
    subject_id="subject-001",
    session_id="session-001",
    # Currently force_rerun is controlled by config file only
    # Future: may add per-flow override
)

result = process_session_flow(config)
```

---

## Cache Invalidation

### When Is Cache Stale?

The pipeline currently uses **existence-based caching**:

- If H5 file exists → use it
- If H5 file missing → regenerate

**Limitations** (current implementation):

- ❌ Does not check if source video changed
- ❌ Does not check if DLC model updated
- ❌ Does not validate H5 file integrity

### Recommended Practice

**Always clear cache when**:

1. You update DLC/SLEAP models
2. You modify source videos
3. You upgrade pipeline version
4. You suspect corrupt intermediate files

```bash
# Safe cache reset
rm -rf data/interim/*
```

### Future Improvements

Planned for v1.0+:

- Timestamp-based validation (regenerate if video newer than H5)
- Model version tracking (regenerate if model changed)
- H5 integrity checks (detect corrupt files)
- Per-stage `--force-{stage}` CLI flags

---

## Batch Processing Considerations

### Caching During Batch Jobs

```bash
# Process all sessions - reuses any existing pose estimates
w2t-bkin batch config.toml --max-workers 4
```

**Behavior**:

- Each session checks cache independently
- Sessions with cached poses skip inference
- Sessions without cached poses run inference
- Useful for processing new sessions without redoing old work

### Mixed Cache States

```text
Example scenario:
- subject-001/session-001: Poses cached ✓
- subject-001/session-002: Poses missing ✗
- subject-002/session-001: Poses cached ✓

Batch job:
- session-001: Uses cache (fast)
- session-002: Runs DLC (slow)
- subject-002/session-001: Uses cache (fast)
```

---

## Troubleshooting

### Issue: "Pipeline runs but pose quality is poor"

**Possible cause**: Cached poses from old model

**Solution**:

```bash
# 1. Check when poses were generated
ls -lh data/interim/dlc-pose/camera_0/

# 2. Clear cache and regenerate
rm -rf data/interim/dlc-pose/
w2t-bkin run config.toml subject-001 session-001
```

### Issue: "Cache takes too much disk space"

**Solution**: Clean up old intermediate files

```bash
# Check disk usage
du -sh data/interim/

# Safe cleanup (keeps only processed NWB)
rm -rf data/interim/dlc-pose/
rm -rf data/interim/sleap-pose/

# Nuclear option (delete all intermediate)
rm -rf data/interim/*
```

### Issue: "Want to reprocess specific camera only"

**Solution**: Delete specific camera cache

```bash
# Regenerate only camera_0 poses
rm -rf data/interim/dlc-pose/camera_0/

# Regenerate only camera_1 SLEAP poses
rm -rf data/interim/sleap-pose/camera_1/

# Then run normally
w2t-bkin run config.toml subject-001 session-001
```

### Issue: "Batch job is too slow despite caching"

**Check**:

1. Are poses actually cached?

   ```bash
   find data/interim/dlc-pose/ -name "*.h5" | wc -l
   ```

2. Is `force_rerun = true` in config?

   ```bash
   grep force_rerun configuration.toml
   ```

3. Are you processing new sessions (no cache yet)?
   ```bash
   w2t-bkin discover config.toml --format plain
   ```

---

## Best Practices

### ✅ Do This

1. **Keep interim folder organized**

   ```bash
   data/interim/
   ├── dlc-pose/           # Pose estimates
   └── sleap-pose/         # SLEAP poses
   ```

2. **Clear cache when upgrading**

   ```bash
   # Before upgrading pipeline
   rm -rf data/interim/*

   # Then upgrade
   pip install --upgrade w2t-bkin
   ```

3. **Use `force_rerun` for troubleshooting**

   - Suspected bug → force regeneration
   - Confirmed bug fix → clear cache once

4. **Backup processed outputs**
   ```bash
   # Before reprocessing with changes
   cp -r data/processed/ data/processed.backup/
   ```

### ❌ Don't Do This

1. **Don't manually edit H5 files** - Pipeline won't detect changes
2. **Don't mix force_rerun=true in production** - Wastes compute
3. **Don't assume cache is always valid** - Validate after model updates
4. **Don't delete `data/processed/`** - This is your final output!

---

## Configuration Reference

### force_rerun Parameter

**Location**: `configuration.toml` → `[preprocessing]`

```toml
[preprocessing]
# Force regeneration of intermediate files (DLC/SLEAP poses)
# Default: false (use cache when available)
# Set to true when:
# - Models have been updated
# - Debugging pose estimation issues
# - Verifying reproducibility
force_rerun = false  # or true
```

**Scope**: Affects all preprocessing stages (DLC, SLEAP, etc.)

**Does NOT affect**:

- NWB file assembly (always regenerated)
- TTL synchronization (recomputed each run)
- Metadata loading (always re-read)

---

## See Also

- [Pipeline Commands](../cli/pipeline-commands.md) - Running sessions and batch jobs
- [Configuration Reference](../reference/configuration-parameters.md) - All config options
- [Troubleshooting Guide](../TROUBLESHOOTING.md) - Common issues
- [FAQ](../FAQ.md) - Frequently asked questions
