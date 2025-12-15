# Configuration Parameters Guide

This document describes configuration parameters for the w2t-bkin pipeline. Configuration controls **HOW** the pipeline processes data.

> **Note**: For data description parameters (cameras, TTLs, subjects), see [Metadata Parameters Guide](metadata-parameters.md).

## Configuration vs Metadata

- **Configuration (`config.toml`)**: Pipeline behavior and processing parameters

  - Examples: `force_rerun`, `gpu_index`, `check_sync_mismatch`, `verification` settings
  - Location: Project root or specified via `--config` flag
  - Scope: Project-wide processing behavior

- **Metadata** (`.toml` files in `data/raw/`): Data description and NWB metadata
  - Examples: Camera paths, TTL channels, Bpod sync mappings, subject info
  - Location: Hierarchical files in raw data directory
  - Scope: Experiment/subject/session specific
  - See: [Metadata Parameters Guide](metadata-parameters.md)

## Table of Contents

- [Project Settings](#project-settings)
- [Path Configuration](#path-configuration)
- [Synchronization Settings](#synchronization-settings)
- [Verification Settings](#verification-settings)
- [Preprocessing Settings](#preprocessing-settings)
- [Session-Level Logging](#session-level-logging)
- [Usage Examples](#usage-examples)

---

## Project Settings

### `[project]`

Basic project identification.

```toml
[project]
name = "w2t-bkin-pipeline"
```

**Parameters**:

- `name` (string): Project name for identification

---

## Path Configuration

### `[paths]`

File system paths for pipeline data organization.

```toml
[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"
root_metadata = "config/metadata.toml"  # Optional
```

**Parameters**:

- `raw_root` (path, required): Root directory containing raw experimental data
- `intermediate_root` (path, required): Directory for intermediate processing artifacts (DLC poses, etc.)
- `output_root` (path, required): Directory for final NWB files and results
- `models_root` (path, default: `"models"`): Directory containing pose estimation models
- `root_metadata` (path, optional): Global metadata file loaded before raw_root hierarchy

**Notes**:

- All paths can be absolute or relative to config file location
- Paths are resolved and validated on load
- `root_metadata` provides a base layer for metadata hierarchy (see [Metadata Guide](metadata-parameters.md))

### Environment Variable Overrides

Paths can be overridden using environment variables. This is particularly useful for containerized environments (e.g., Docker workers) where paths inside the container differ from the host.

**Supported Variables:**

- `W2T_RAW_ROOT`: Overrides `paths.raw_root`
- `W2T_INTERMEDIATE_ROOT`: Overrides `paths.intermediate_root`
- `W2T_OUTPUT_ROOT`: Overrides `paths.output_root`
- `W2T_MODELS_ROOT`: Overrides `paths.models_root`
- `W2T_ROOT_METADATA`: Overrides `paths.root_metadata`

**Precedence:** Environment variables > `config.toml` settings.

---

## Synchronization Settings

### `[synchronization]`

Controls time synchronization strategy across data streams.

```toml
[synchronization]
strategy = "hardware_pulse"
reference_channel = "ttl_camera"

[synchronization.alignment]
method = "nearest"
tolerance_s = 0.002
global_offset_s = 0.0
```

**Parameters**:

#### `synchronization.strategy`

- Type: string
- Default: `"hardware_pulse"`
- Options: `"hardware_pulse"`, `"rate_based"`, `"none"`
- Description: Synchronization method for aligning data streams

#### `synchronization.reference_channel`

- Type: string
- Default: `"ttl_camera"`
- Description: TTL channel ID used as timing reference (must match metadata `[[TTLs]].id`)

#### `synchronization.alignment.method`

- Type: string
- Default: `"nearest"`
- Options: `"nearest"`, `"linear"`, `"previous"`, `"next"`
- Description: Interpolation method for timestamp alignment

#### `synchronization.alignment.tolerance_s`

- Type: float
- Default: `0.002`
- Units: seconds
- Description: Maximum allowed time difference for alignment matches

#### `synchronization.alignment.global_offset_s`

- Type: float
- Default: `0.0`
- Units: seconds
- Description: Global time offset applied to all streams

---

## Verification Settings

### Verification Overview

The verification configuration controls various checks performed during pipeline execution, including frame counting, TTL synchronization verification, and error handling behavior.

### Verification Configuration

**Location:** Configuration files (`config.toml`)

```toml
[verification]
enabled = true                      # Master switch for all verification checks
check_frame_counts = true           # Count video frames (can be slow for large videos)
check_sync_mismatch = true          # Verify frame/TTL synchronization
skip_nwb_requirements = false       # Skip NWB-required frame counting
mismatch_tolerance_frames = 0       # Maximum allowed frame/TTL count mismatch
warn_on_mismatch = false            # Warn instead of fail on mismatch
```

### Parameters

#### `enabled` (boolean, default: `true`)

Master switch that disables all verification checks when set to `false`.

**Use case:** Disable for rapid prototyping or when verification is not needed.

#### `check_frame_counts` (boolean, default: `true`)

Count frames in video files using ffprobe (accurate but slow).

**Use cases:**

- Set to `false` for faster execution with large videos
- Recommended to keep `true` for production to ensure data integrity

#### `check_sync_mismatch` (boolean, default: `true`)

Verify that camera frame counts match TTL pulse counts.

**Behavior:**

- When `enabled=true`:
  - Fails if camera has no TTL files (unless camera is optional)
  - Fails if frame/pulse count mismatch exceeds tolerance
- When `enabled=false`:
  - Skips TTL synchronization verification entirely
  - No checks performed even if TTL files are available

**Use cases:**

- Set to `false` when processing sessions **without TTL data**
- Set to `false` for rate-based synchronization strategies
- Keep `true` for hardware_pulse synchronization to ensure data integrity

**Important Note:** If TTL files are missing for a required camera, you will see:

```text
⊘ Camera 'camera_name': No TTL files found for 'ttl_id'
  → Skipping verification (cannot verify without sync data).
  Set verification.check_sync_mismatch=false if this is expected.
```

#### `skip_nwb_requirements` (boolean, default: `false`)

Skip NWB-required frame counting for multi-file videos, using FPS-based estimation instead.

**Warning:** Not recommended for production use as it reduces accuracy.

#### `mismatch_tolerance_frames` (integer, default: `0`)

Maximum allowed difference between video frame count and TTL pulse count.

**Examples:**

- `0`: Exact match required
- `5`: Allow up to 5 frames difference
- `10`: Allow up to 10 frames difference

#### `warn_on_mismatch` (boolean, default: `false`)

When `true`, log warning instead of failing if mismatch is within tolerance.

**Use case:** Useful for datasets with known minor synchronization issues.

### Examples

#### Example 1: Strict Verification (Production)

```toml
[verification]
enabled = true
check_frame_counts = true
check_sync_mismatch = true
skip_nwb_requirements = false
mismatch_tolerance_frames = 0
warn_on_mismatch = false
```

#### Example 2: Fast Processing (Development)

```toml
[verification]
enabled = true
check_frame_counts = false  # Skip slow frame counting
check_sync_mismatch = false  # Skip TTL verification
skip_nwb_requirements = true
mismatch_tolerance_frames = 10
warn_on_mismatch = true
```

#### Example 3: Sessions Without TTL Data

```toml
[verification]
enabled = true
check_frame_counts = true  # Still count frames for NWB
check_sync_mismatch = false  # No TTL data available
skip_nwb_requirements = false
mismatch_tolerance_frames = 0
warn_on_mismatch = false
```

#### Example 4: Lenient Verification

```toml
[verification]
enabled = true
check_frame_counts = true
check_sync_mismatch = true
skip_nwb_requirements = false
mismatch_tolerance_frames = 5  # Allow small mismatch
warn_on_mismatch = true  # Only warn, don't fail
```

---

## Preprocessing Settings

### `[preprocessing]`

Controls artifact generation and pose estimation.

```toml
[preprocessing]
force_rerun = false

[preprocessing.dlc]
enabled = true
# gpu = 0  # Optional: specify GPU index

[preprocessing.sleap]
enabled = false
# gpu = 0  # Optional: specify GPU index
```

**Parameters**:

#### `preprocessing.force_rerun`

- Type: boolean
- Default: `false`
- Description: Regenerate all intermediate artifacts even if cached versions exist
- Use cases:
  - Changed pose estimation models
  - Updated processing parameters
  - Suspected cache corruption

#### `preprocessing.dlc.enabled`

- Type: boolean
- Default: `true`
- Description: Enable DeepLabCut pose estimation

#### `preprocessing.dlc.gpu`

- Type: integer
- Default: Auto-detect
- Range: 0-7
- Description: GPU device index for DLC inference

#### `preprocessing.sleap.enabled`

- Type: boolean
- Default: `false`
- Description: Enable SLEAP pose estimation

#### `preprocessing.sleap.gpu`

- Type: integer
- Default: Auto-detect
- Range: 0-7
- Description: GPU device index for SLEAP inference

**Notes**:

- Both DLC and SLEAP can be enabled simultaneously
- GPU selection is per-framework (can use different GPUs)
- If GPU not specified, pipeline auto-detects available devices
- `force_rerun` affects all preprocessing (DLC, SLEAP, video processing)

---

## Session-Level Logging

### Logging Overview

The pipeline automatically creates session-specific log files capturing all WARNING and ERROR messages for each processed session.

### Log File Locations

For each session, two identical log files are created:

```text
{output_root}/{subject_id}/{session_id}/pipeline.log
{intermediate_root}/{subject_id}/{session_id}/pipeline.log
```

### Logging Behavior

- **Automatic Creation:** Log files are created automatically after Phase 0 (initialization)
- **Content:** Only WARNING and ERROR level messages
- **Format:** Standard log format with timestamp, level, logger name, and message
- **Lifecycle:** Handlers are cleaned up after pipeline completion
- **Purpose:** Easy troubleshooting of specific session issues in batch processing

### Log Format

```text
YYYY-MM-DD HH:MM:SS - LEVEL - logger.name - message
```

### Example Log Content

```text
2025-12-04 14:03:19 - WARNING - w2t_bkin.core.pipeline.phases.discovery - ⊘ Camera 'face_right' is optional and no files found - skipping
2025-12-04 14:03:19 - WARNING - w2t_bkin.core.pipeline.phases.discovery - Camera 'face_left': No TTL data available for estimation
2025-12-04 14:03:20 - ERROR - w2t_bkin.sync.validation - Synchronization mismatch exceeds tolerance: expected 1000 frames, got 995 TTL pulses
```

### Log File Usage

**View session logs after processing:**

```bash
# View output directory log
cat /path/to/output_root/{subject}/{session}/pipeline.log

# View intermediate directory log
cat /path/to/intermediate_root/{subject}/{session}/pipeline.log

# Search for specific issues
grep "ERROR" /path/to/output_root/{subject}/{session}/pipeline.log
grep "Camera.*skipping" /path/to/output_root/{subject}/{session}/pipeline.log
```

### Benefits

1. **Session Isolation:** Each session has its own log file
2. **Batch Processing:** Easy to identify which sessions had issues
3. **Debugging:** Complete warning/error history per session
4. **Automation:** No manual configuration needed

### Notes

- Log files are **overwritten** on each pipeline run (mode='w')
- Only captures messages from `w2t_bkin.*` loggers
- Does not interfere with console output or other logging handlers
- Minimal overhead: Only writes WARNING and ERROR level messages

---

## Usage Examples

### Example 1: Processing Sessions Without TTL

**Problem:** Older sessions don't have TTL synchronization files

**Solution:**

```toml
# In config.toml
[verification]
enabled = true
check_frame_counts = true  # Still validate video integrity
check_sync_mismatch = false  # Skip TTL verification
```

**Result:**

- Frame counting still performed for NWB file
- TTL synchronization checks skipped
- No false failures due to missing TTL files

### Example 2: Development vs Production

**Development Configuration:**

```toml
# Fast processing for development
[verification]
enabled = true
check_frame_counts = false  # Skip slow checks
check_sync_mismatch = false
mismatch_tolerance_frames = 10
warn_on_mismatch = true
```

**Production Configuration:**

```toml
# Strict validation for production
[verification]
enabled = true
check_frame_counts = true  # Ensure data integrity
check_sync_mismatch = true
mismatch_tolerance_frames = 0  # No tolerance
warn_on_mismatch = false  # Fail on mismatch
```

---

## Complete Configuration Example

See [`templates/standard.toml`](../../templates/standard.toml) for a complete, annotated configuration file.

```toml
# =============================================================================
# Project Configuration
# =============================================================================

[project]
name = "w2t-bkin-pipeline"

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

# =============================================================================
# Synchronization Strategy
# =============================================================================

[synchronization]
strategy = "hardware_pulse"
reference_channel = "ttl_camera"

[synchronization.alignment]
method = "nearest"
tolerance_s = 0.002
global_offset_s = 0.0

# =============================================================================
# Verification & Validation
# =============================================================================

[verification]
enabled = true
check_frame_counts = true
check_sync_mismatch = true
skip_nwb_requirements = false
mismatch_tolerance_frames = 0
warn_on_mismatch = false

# =============================================================================
# Preprocessing Configuration
# =============================================================================

[preprocessing]
force_rerun = false

[preprocessing.dlc]
enabled = true
# gpu = 0  # Optional

[preprocessing.sleap]
enabled = false
# gpu = 0  # Optional

# =============================================================================
# Logging Configuration
# =============================================================================

[logging]
level = "INFO"
structured = false
```

---

## Troubleshooting

### Issue: TTL verification failing for sessions without TTL

**Solution:** Set `verification.check_sync_mismatch = false` in config.toml.

### Issue: Can't find session-level logs

**Solution:** Logs are created in:

- `{output_root}/{subject_id}/{session_id}/pipeline.log`
- `{intermediate_root}/{subject_id}/{session_id}/pipeline.log`

Ensure these directories exist and pipeline completed initialization phase.

### Issue: Figures not being generated

**Possible causes:**

1. Missing trial synchronization configuration in metadata (see [Metadata Guide](metadata-parameters.md#bpod-trial-synchronization))
2. No TTL or Bpod data available
3. matplotlib not installed (install with `pip install -e .[worker]`)

**Solution:** Check `pipeline.log` for messages like "Skipping trial alignment (no trial_type configs in metadata)"

### Issue: Force rerun not regenerating artifacts

**Solution:** Ensure `preprocessing.force_rerun = true` in config.toml, not in metadata files.

---

## See Also

- **[Metadata Parameters Guide](metadata-parameters.md)** - Camera, TTL, Bpod, and subject configuration
- **[Templates](../../templates/README.md)** - Example configuration and metadata files
- [Pipeline Commands](../cli/pipeline-commands.md) - Run and batch processing
- [Data Management](../cli/data-management.md) - Experiment organization
- [Caching and Reprocessing](../user-guide/caching-and-reprocessing.md) - Cache management
