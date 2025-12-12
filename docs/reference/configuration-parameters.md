# Configuration Parameters Guide

This document describes the new configuration parameters added to the w2t-bkin pipeline.

## Table of Contents

- [Optional Camera Support](#optional-camera-support)
- [Verification Settings](#verification-settings)
- [Session-Level Logging](#session-level-logging)
- [Configuration File Hierarchy](#configuration-file-hierarchy)
- [Usage Examples](#usage-examples)

---

## Optional Camera Support

### Overview

The pipeline now supports marking cameras as optional, allowing graceful handling of incomplete experimental data where some camera recordings may be missing.

### Configuration

**Location:** Session metadata files (`metadata.toml`, `session.toml`)

**Parameter:** `optional` (boolean, default: `false`)

```toml
[[cameras]]
id = "camera_name"
paths = "Video/camera_name/*.avi"
order = "name_asc"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # Set to true to skip camera if files are missing
```

### Behavior

#### When `optional = false` (default)

- Pipeline **fails** if no files match the pattern
- Error message includes helpful hint to set `optional = true`
- This is the recommended setting for critical cameras

#### When `optional = true`

- Pipeline **continues** if no files match the pattern
- Warning logged: `⊘ Camera 'camera_name' is optional and no files found - skipping`
- Camera is skipped in all subsequent phases:
  - **Discovery**: Empty file list created, no error raised
  - **Verification**: TTL synchronization check skipped
  - **Ingestion**: Pose data loading skipped
  - **Assembly**: Only available cameras processed

### Use Cases

- Cameras that may not be present in all sessions
- Equipment failures or missing recordings
- Incomplete data sets where some cameras are unavailable
- Batch processing of mixed complete/incomplete sessions

### Visual Indicators

The pipeline uses the `⊘` symbol to indicate skipped optional cameras in logs.

### Example

```toml
# Example: Required overhead camera, optional side cameras
[[cameras]]
id = "overhead"
paths = "Video/overhead/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = false  # Critical camera - must be present

[[cameras]]
id = "side_left"
paths = "Video/side_left/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # Nice to have, but not required

[[cameras]]
id = "side_right"
paths = "Video/side_right/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # Nice to have, but not required
```

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

## Configuration File Hierarchy

Configuration and metadata are loaded in layers, with later layers overriding earlier ones:

### Loading Order

1. **Root metadata:** `{raw_root}/metadata.toml` (if exists)
2. **Root metadata from config:** `config.paths.root_metadata` (if specified in config)
3. **Subject metadata:** `{raw_root}/{subject}/subject.toml` (if exists)
4. **Session metadata:** `{raw_root}/{subject}/{session}/session.toml` (if exists)

### Metadata Best Practices

- **Root metadata:** Define common cameras, TTLs, and devices used across all sessions
- **Subject metadata:** Define subject-specific settings (age, weight, genotype, etc.)
- **Session metadata:** Define session-specific overrides or additions

### Example Structure

```text
data/raw/
├── metadata.toml              # Common cameras, TTLs, devices for all sessions
├── subject-001/
│   ├── subject.toml          # Subject-specific info (age, weight, etc.)
│   ├── session-001/
│   │   ├── session.toml      # Session-specific overrides
│   │   └── Video/            # Session data
│   └── session-002/
│       ├── session.toml      # Different camera settings
│       └── Video/
└── subject-002/
    └── ...
```

---

## Usage Examples

### Example 1: Handling Incomplete Session

**Problem:** Session has missing camera recordings

**Solution:**

```toml
# In session.toml or metadata.toml
[[cameras]]
id = "side_camera"
paths = "Video/side/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # Skip if missing

[[cameras]]
id = "overhead_camera"
paths = "Video/overhead/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = false  # Required
```

**Result:**

- Pipeline processes overhead camera normally
- Side camera skipped with warning in `pipeline.log`
- Session completes successfully

### Example 2: Processing Sessions Without TTL

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

### Example 3: Batch Processing Mixed Sessions

**Problem:** Processing multiple sessions, some complete and some incomplete

**Setup:**

```toml
# Root metadata.toml (applies to all sessions)
[[cameras]]
id = "cam0"
paths = "Video/cam0/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = false  # Required for all sessions

[[cameras]]
id = "cam1"
paths = "Video/cam1/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # Optional - may be missing in some sessions
```

**Command:**

```bash
python -m w2t_bkin.cli batch config.toml --max-workers 4
```

**Result:**

- All sessions processed
- Sessions with cam1: Both cameras processed
- Sessions without cam1: Only cam0 processed, warning logged
- Check individual `pipeline.log` files for session-specific issues

### Example 4: Development vs Production

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

## CLI Override Options

The CLI provides options to override verification settings:

```bash
# Disable all verification
python -m w2t_bkin.cli run config.toml subject-001 session-001 --no-verification

# Skip frame counting
python -m w2t_bkin.cli run config.toml subject-001 session-001 --no-frame-count

# Skip TTL synchronization check
python -m w2t_bkin.cli run config.toml subject-001 session-001 --no-sync-check

# Set tolerance
python -m w2t_bkin.cli run config.toml subject-001 session-001 --tolerance 5

# Warn on mismatch
python -m w2t_bkin.cli run config.toml subject-001 session-001 --warn-on-mismatch
```

---

## Migration Guide

### Updating Existing Configurations

#### Step 1: Add verification section to config.toml

```toml
[verification]
enabled = true
check_frame_counts = true
check_sync_mismatch = true
skip_nwb_requirements = false
mismatch_tolerance_frames = 0
warn_on_mismatch = false
```

#### Step 2: Add optional field to cameras (if needed)

```toml
[[cameras]]
id = "camera_name"
# ... other fields ...
optional = false  # Add this field (default behavior)
```

#### Step 3: Test with single session

```bash
python -m w2t_bkin.cli run config.toml subject-001 session-001
```

#### Step 4: Check session logs

```bash
cat output_root/subject-001/session-001/pipeline.log
```

### Backward Compatibility

- **Default values:** All new parameters have sensible defaults
- **Optional fields:** Can be omitted (defaults to `false`)
- **Existing configs:** Continue to work without modification
- **Verification settings:** Old style verification settings are automatically migrated

---

## Troubleshooting

### Issue: Camera marked optional but still causing failure

**Solution:** Check that `optional = true` is set in the correct metadata file (session or root metadata).

### Issue: TTL verification failing for sessions without TTL

**Solution:** Set `verification.check_sync_mismatch = false` in config.toml.

### Issue: Can't find session-level logs

**Solution:** Logs are created in:

- `{output_root}/{subject_id}/{session_id}/pipeline.log`
- `{intermediate_root}/{subject_id}/{session_id}/pipeline.log`

Ensure these directories exist and pipeline completed initialization phase.

### Issue: Too many warnings in session logs

**Solution:** This is expected behavior. Session logs only capture WARNING and ERROR messages for troubleshooting. Use `grep "ERROR"` to filter for critical issues only.

---

## See Also

- [Pipeline Commands](../cli/pipeline-commands.md) - Run and batch processing
- [Data Management](../cli/data-management.md) - Experiment organization
- [Caching and Reprocessing](../user-guide/caching-and-reprocessing.md) - Cache management
