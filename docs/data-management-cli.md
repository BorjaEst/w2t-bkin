# Data Management CLI Guide

**Version:** 1.0  
**Date:** 2024-12-04

## Overview

The W2T-BKIN data management CLI provides safe, guided commands for setting up and organizing experimental data. These commands help you:

- Initialize new experiments with proper structure
- Add subjects and sessions with metadata
- Import existing raw data safely (using symbolic links)
- Validate folder structures and metadata

**Key Safety Features:**

- Never moves or deletes original data
- Uses symbolic links for imports (preserves originals)
- Dry-run mode by default for import operations
- Interactive prompts with confirmation
- Comprehensive validation

---

## Quick Start

### 1. Initialize a New Experiment

```bash
# Interactive mode (prompts for details)
python -m w2t_bkin.cli data init /data/my-experiment

# Non-interactive mode
python -m w2t_bkin.cli data init /data/my-experiment \
  --lab "Larkum Lab" \
  --institution "Humboldt University" \
  --experimenters "Alice,Bob" \
  --protocol "IACUC-2024-001" \
  --description "Whisker tracking study" \
  -y
```

**Creates:**

```txt
/data/my-experiment/
├── raw/
│   └── metadata.toml
├── interim/
├── processed/
├── models/
└── config.toml
```

### 2. Add a Subject

```bash
# Basic subject
python -m w2t_bkin.cli data add-subject /data/my-experiment subject-001

# With full metadata
python -m w2t_bkin.cli data add-subject /data/my-experiment subject-001 \
  --species "Mus musculus" \
  --sex M \
  --age P84D \
  --genotype "Thy1-GFP" \
  --strain "C57BL/6J" \
  -y
```

**Creates:**

```txt
/data/my-experiment/raw/
└── subject-001/
    └── subject.toml
```

### 3. Add a Session

```bash
# Basic session
python -m w2t_bkin.cli data add-session /data/my-experiment subject-001 session-001

# With metadata
python -m w2t_bkin.cli data add-session /data/my-experiment subject-001 session-001 \
  --date 2024-01-15 \
  --description "Baseline recording" \
  --experimenter "Alice" \
  --start-time "2024-01-15T14:30:00Z" \
  -y
```

**Creates:**

```txt
/data/my-experiment/raw/subject-001/
└── session-001/
    ├── session.toml
    ├── Video/
    ├── TTLs/
    └── Bpod/
```

### 4. Import Existing Data (SAFE)

```bash
# Step 1: Preview (dry-run, no changes)
python -m w2t_bkin.cli data import-raw /original-data/2024-01-15 \
  --experiment /data/my-experiment \
  --subject subject-001 \
  --session session-001

# Step 2: Execute (creates symbolic links)
python -m w2t_bkin.cli data import-raw /original-data/2024-01-15 \
  --experiment /data/my-experiment \
  --subject subject-001 \
  --session session-001 \
  --confirm
```

**Safety Guarantees:**

- ✅ Originals preserved in `/original-data/2024-01-15`
- ✅ Symbolic links created in session directory
- ✅ Auto-detects cameras, TTLs, and Bpod files
- ✅ Updates `session.toml` with detected configuration

### 5. Validate Structure

```bash
# Validate entire experiment
python -m w2t_bkin.cli data validate /data/my-experiment

# Validate specific subject
python -m w2t_bkin.cli data validate /data/my-experiment --subject subject-001

# Validate specific session (verbose)
python -m w2t_bkin.cli data validate /data/my-experiment \
  --subject subject-001 \
  --session session-001 \
  --verbose
```

---

## Command Reference

### `data init`

Initialize a new experiment folder structure.

**Usage:**

```bash
python -m w2t_bkin.cli data init EXPERIMENT_ROOT [OPTIONS]
```

**Arguments:**

- `EXPERIMENT_ROOT`: Path to experiment root directory

**Options:**

- `--lab TEXT`: Lab name (required if not interactive)
- `--institution TEXT`: Institution name (required if not interactive)
- `--experimenters TEXT`: Comma-separated experimenter names (required if not interactive)
- `--protocol TEXT`: Protocol ID (e.g., IACUC number)
- `--description TEXT`: Experiment description
- `--yes, -y`: Skip confirmation prompts

**Created Structure:**

```txt
{EXPERIMENT_ROOT}/
├── raw/              # Raw data storage
│   └── metadata.toml # NWB metadata
├── interim/          # Intermediate artifacts
├── processed/        # Final outputs
├── models/           # Trained models
└── config.toml       # Pipeline configuration
```

**Example:**

```bash
python -m w2t_bkin.cli data init /data/whisker-study \
  --lab "Larkum Lab" \
  --institution "Humboldt University" \
  --experimenters "Alice Smith,Bob Jones" \
  --protocol "IACUC-2024-001" \
  --description "Multi-session whisker tracking" \
  -y
```

---

### `data add-subject`

Add a new subject to the experiment.

**Usage:**

```bash
python -m w2t_bkin.cli data add-subject EXPERIMENT_ROOT SUBJECT_ID [OPTIONS]
```

**Arguments:**

- `EXPERIMENT_ROOT`: Path to experiment root directory
- `SUBJECT_ID`: Subject identifier (letters, numbers, hyphens, underscores only)

**Options:**

- `--species TEXT`: Species name (default: "Mus musculus")
- `--sex TEXT`: Sex (F|M|U|O) (default: "U" - unknown)
- `--age TEXT`: Age in ISO 8601 duration (e.g., P84D for 84 days)
- `--genotype TEXT`: Genotype
- `--strain TEXT`: Strain
- `--date-of-birth TEXT`: Date of birth (ISO 8601)
- `--weight TEXT`: Weight
- `--description TEXT`: Subject description
- `--yes, -y`: Skip confirmation prompts

**Created Structure:**

```txt
{EXPERIMENT_ROOT}/raw/
└── {SUBJECT_ID}/
    └── subject.toml
```

**Examples:**

```bash
# Minimal
python -m w2t_bkin.cli data add-subject /data/my-experiment mouse-001 -y

# Full metadata
python -m w2t_bkin.cli data add-subject /data/my-experiment mouse-001 \
  --species "Mus musculus" \
  --sex M \
  --age P90D \
  --genotype "Thy1-GFP" \
  --strain "C57BL/6J" \
  --date-of-birth "2024-01-01" \
  --weight "25g" \
  --description "Adult male, behavioral training completed" \
  -y
```

**ISO 8601 Duration Format:**

- `P84D` = 84 days
- `P12W` = 12 weeks
- `P3M` = 3 months
- `P2Y` = 2 years

---

### `data add-session`

Add a new session for a subject.

**Usage:**

```bash
python -m w2t_bkin.cli data add-session EXPERIMENT_ROOT SUBJECT_ID SESSION_ID [OPTIONS]
```

**Arguments:**

- `EXPERIMENT_ROOT`: Path to experiment root directory
- `SUBJECT_ID`: Subject identifier
- `SESSION_ID`: Session identifier (letters, numbers, hyphens, underscores only)

**Options:**

- `--date TEXT`: Session date (ISO 8601, e.g., 2024-01-15) (default: today)
- `--description TEXT`: Session description (prompted if not provided)
- `--experimenter TEXT`: Experimenter name (prompted if not provided)
- `--start-time TEXT`: Session start time (ISO 8601, e.g., 2024-01-15T14:30:00Z)
- `--no-subdirs`: Don't create Video/TTLs/Bpod folders
- `--yes, -y`: Skip confirmation prompts

**Created Structure:**

```txt
{EXPERIMENT_ROOT}/raw/{SUBJECT_ID}/
└── {SESSION_ID}/
    ├── session.toml
    ├── Video/       # Optional
    ├── TTLs/        # Optional
    └── Bpod/        # Optional
```

**Examples:**

```bash
# Minimal (prompts for description and experimenter)
python -m w2t_bkin.cli data add-session /data/my-experiment mouse-001 session-001

# Full metadata
python -m w2t_bkin.cli data add-session /data/my-experiment mouse-001 session-001 \
  --date 2024-01-15 \
  --description "Baseline whisker tracking" \
  --experimenter "Alice Smith" \
  --start-time "2024-01-15T14:30:00+01:00" \
  -y

# Without standard subfolders
python -m w2t_bkin.cli data add-session /data/my-experiment mouse-001 session-002 \
  --no-subdirs \
  -y
```

---

### `data import-raw`

Import existing raw data using symbolic links (SAFE - preserves originals).

**Usage:**

```bash
python -m w2t_bkin.cli data import-raw SOURCE [OPTIONS]
```

**Arguments:**

- `SOURCE`: Source directory containing raw data

**Required Options:**

- `--experiment, -e PATH`: Experiment root directory
- `--subject, -s TEXT`: Target subject ID
- `--session TEXT`: Target session ID

**Options:**

- `--no-detect`: Skip automatic file pattern detection
- `--confirm`: Execute import (required for actual operation)

**Default Behavior:**

- **Dry-run mode**: Shows preview without creating links
- **Auto-detection**: Scans for videos, TTLs, Bpod files
- **Pattern recognition**: Detects camera IDs and TTL channels

**Safety Features:**

- ✅ **Symbolic links only** (never moves/copies/deletes)
- ✅ **Originals preserved** in source directory
- ✅ **Dry-run by default** (requires `--confirm` to execute)
- ✅ **Auto-updates metadata** (session.toml with detected cameras/TTLs)

**File Detection:**

| Category | Patterns                                 | Target               |
| -------- | ---------------------------------------- | -------------------- |
| Video    | `*.avi`, `*.mp4`, `*.mkv`, `*.mov`       | `Video/{camera_id}/` |
| TTL      | `*ttl*.txt`, `*pulse*.txt`, `*sync*.txt` | `TTLs/`              |
| Bpod     | `*.mat`                                  | `Bpod/`              |
| Other    | Everything else                          | `Other/`             |

**Camera ID Detection:**

- `camera_0.avi` → `camera_0`
- `cam1_recording.mp4` → `camera_1`
- `view-front.avi` → `camera_front`

**TTL ID Detection:**

- `ttl_camera.txt` → `ttl_camera`
- `pulse_sync.txt` → `ttl_sync`
- `trigger.txt` → `ttl_sync`

**Workflow:**

```bash
# Step 1: Preview import (safe, no changes)
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-15-recording \
  --experiment /data/my-experiment \
  --subject mouse-001 \
  --session session-001

# Output shows:
# ┏━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ Category ┃ Files ┃ Target Pattern       ┃
# ┣━━━━━━━━╋━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━┫
# ┃ VIDEO    ┃    3 ┃ Video/camera_0/*.avi ┃
# ┃ TTL      ┃    2 ┃ TTLs/ttl_camera_*.txt┃
# ┃ BPOD     ┃    1 ┃ Bpod/*.mat           ┃
# ┗━━━━━━━━┻━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━┛

# Step 2: Execute import (creates symlinks)
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-15-recording \
  --experiment /data/my-experiment \
  --subject mouse-001 \
  --session session-001 \
  --confirm

# Result:
# ✓ Created 6 symbolic links
# ✓ Updated: raw/mouse-001/session-001/session.toml
```

**Post-Import Actions:**

After import, **review and update** `session.toml`:

- Camera FPS values (defaults to 30.0)
- TTL channel descriptions
- Camera-TTL mappings (`ttl_id` for each camera)
- Optional camera flags

**Example session.toml after import:**

```toml
# ... existing fields ...

[[cameras]]
id = "camera_0"
paths = "Video/camera_0/*.avi"
order = "name_asc"
fps = 30.0  # ← UPDATE THIS
ttl_id = "ttl_camera"
optional = false

[[TTLs]]
id = "ttl_camera"
paths = "TTLs/ttl_camera_*.txt"
description = "ttl_camera synchronization"  # ← UPDATE THIS
```

---

### `data validate`

Validate experiment folder structure and metadata.

**Usage:**

```bash
python -m w2t_bkin.cli data validate EXPERIMENT_ROOT [OPTIONS]
```

**Arguments:**

- `EXPERIMENT_ROOT`: Path to experiment root directory

**Options:**

- `--subject, -s TEXT`: Filter by subject ID
- `--session TEXT`: Filter by session ID
- `--verbose, -v`: Show detailed validation info

**Checks:**

| Check            | Level   | Description                                               |
| ---------------- | ------- | --------------------------------------------------------- |
| Required folders | Error   | `raw/`, `interim/`, `processed/` exist                    |
| Root metadata    | Warning | `raw/metadata.toml` exists and valid                      |
| Config file      | Warning | `config.toml` exists and valid                            |
| Subject metadata | Warning | `subject.toml` exists per subject                         |
| Session metadata | Error   | `session.toml` exists per session                         |
| Required fields  | Error   | `session_description`, `identifier`, `session_start_time` |
| Camera files     | Warning | Files match `cameras[].paths` patterns                    |
| TTL files        | Warning | Files match `TTLs[].paths` patterns                       |
| TOML syntax      | Error   | All TOML files parse correctly                            |

**Examples:**

```bash
# Validate entire experiment
python -m w2t_bkin.cli data validate /data/my-experiment

# Output:
# Validation Results
# Experiment: /data/my-experiment
#
# ✓ Validation passed!
#   (2 warning(s) - review recommended)

# Validate specific subject
python -m w2t_bkin.cli data validate /data/my-experiment \
  --subject mouse-001

# Validate specific session (verbose)
python -m w2t_bkin.cli data validate /data/my-experiment \
  --subject mouse-001 \
  --session session-001 \
  --verbose

# Output (verbose):
# Validation Results
# Experiment: /data/my-experiment
#
# ⚠ 2 Warning(s):
#   • mouse-001/session-001: No files found for camera 'camera_1' (pattern: Video/camera_1/*.avi)
#   • Missing root metadata: raw/metadata.toml
#
# ℹ Info:
#   ✓ Found: raw/
#   ✓ Found: interim/
#   ✓ Found: processed/
#   ✓ Found config.toml
#   Found 1 subject(s)
```

---

## Complete Workflow Example

### Scenario: Setting up a new multi-subject whisker tracking experiment

```bash
# 1. Initialize experiment
python -m w2t_bkin.cli data init /data/whisker-2024 \
  --lab "Larkum Lab" \
  --institution "Humboldt University" \
  --experimenters "Alice Smith,Bob Jones" \
  --protocol "IACUC-2024-001" \
  --description "Multi-session whisker tracking study" \
  -y

# 2. Add first subject
python -m w2t_bkin.cli data add-subject /data/whisker-2024 mouse-001 \
  --species "Mus musculus" \
  --sex M \
  --age P90D \
  --genotype "Thy1-GFP" \
  --strain "C57BL/6J" \
  -y

# 3. Add first session
python -m w2t_bkin.cli data add-session /data/whisker-2024 mouse-001 baseline \
  --date 2024-01-15 \
  --description "Baseline whisker tracking" \
  --experimenter "Alice Smith" \
  -y

# 4. Import existing raw data (preview first)
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-15-mouse001-baseline \
  --experiment /data/whisker-2024 \
  --subject mouse-001 \
  --session baseline

# 5. Review preview, then confirm
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-15-mouse001-baseline \
  --experiment /data/whisker-2024 \
  --subject mouse-001 \
  --session baseline \
  --confirm

# 6. Update session metadata (manually edit)
nano /data/whisker-2024/raw/mouse-001/baseline/session.toml
# Update camera FPS, TTL descriptions, etc.

# 7. Validate
python -m w2t_bkin.cli data validate /data/whisker-2024 \
  --subject mouse-001 \
  --session baseline \
  --verbose

# 8. Process session
python -m w2t_bkin.cli run /data/whisker-2024/config.toml mouse-001 baseline
```

### Adding More Sessions

```bash
# Add second session for same subject
python -m w2t_bkin.cli data add-session /data/whisker-2024 mouse-001 training-day1 \
  --date 2024-01-16 \
  --description "First training session" \
  --experimenter "Bob Jones" \
  -y

# Import and process
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-16-mouse001-training \
  --experiment /data/whisker-2024 \
  --subject mouse-001 \
  --session training-day1 \
  --confirm

python -m w2t_bkin.cli run /data/whisker-2024/config.toml mouse-001 training-day1
```

### Adding More Subjects

```bash
# Add second subject
python -m w2t_bkin.cli data add-subject /data/whisker-2024 mouse-002 \
  --species "Mus musculus" \
  --sex F \
  --age P85D \
  --genotype "Thy1-GFP" \
  --strain "C57BL/6J" \
  -y

# Add sessions and process
python -m w2t_bkin.cli data add-session /data/whisker-2024 mouse-002 baseline \
  --date 2024-01-17 \
  --description "Baseline whisker tracking" \
  --experimenter "Alice Smith" \
  -y

# ... import and process ...
```

---

## Safety Best Practices

### 1. Always Preview Imports First

```bash
# ✅ Good: Preview first (dry-run)
python -m w2t_bkin.cli data import-raw /raw-data --experiment /data/exp --subject s1 --session sess1

# Review output, then:
python -m w2t_bkin.cli data import-raw /raw-data --experiment /data/exp --subject s1 --session sess1 --confirm

# ❌ Bad: Skipping preview
python -m w2t_bkin.cli data import-raw /raw-data --experiment /data/exp --subject s1 --session sess1 --confirm
```

### 2. Validate Frequently

```bash
# After adding subjects
python -m w2t_bkin.cli data validate /data/my-experiment --subject new-subject --verbose

# After adding sessions
python -m w2t_bkin.cli data validate /data/my-experiment --subject s1 --session new-session --verbose

# Before batch processing
python -m w2t_bkin.cli data validate /data/my-experiment
```

### 3. Keep Originals Safe

```bash
# ✅ Good: Import from read-only archive
python -m w2t_bkin.cli data import-raw /archive/readonly/2024-01-15 \
  --experiment /data/working \
  --subject s1 \
  --session sess1 \
  --confirm

# ✅ Good: Import from backup location
python -m w2t_bkin.cli data import-raw /backup/raw-data/session001 \
  --experiment /data/my-experiment \
  --subject mouse-001 \
  --session session-001 \
  --confirm
```

### 4. Review Auto-Generated Metadata

After import, **always review**:

```bash
# Edit session.toml
nano /data/my-experiment/raw/subject-001/session-001/session.toml

# Check:
# 1. Camera FPS values (update from default 30.0)
# 2. TTL descriptions (replace auto-generated)
# 3. Camera-TTL mappings (verify ttl_id)
# 4. Optional camera flags (set if camera may be missing)
```

### 5. Use Version Control for Metadata

```bash
cd /data/my-experiment
git init
git add config.toml raw/metadata.toml
git add raw/*/subject.toml
git add raw/*/*/session.toml
git commit -m "Initial experiment setup"
```

---

## Troubleshooting

### Import: No Files Detected

**Problem:**

```txt
⚠ No recognizable files found in /raw-data
```

**Solutions:**

1. **Check file extensions:**

   ```bash
   ls -R /raw-data
   # Look for: .avi, .mp4, .mkv, .txt, .mat
   ```

2. **Use `--no-detect` and manual metadata:**

   ```bash
   # Import without auto-detection
   python -m w2t_bkin.cli data import-raw /raw-data \
     --experiment /data/exp \
     --subject s1 \
     --session sess1 \
     --no-detect \
     --confirm

   # Manually edit session.toml
   nano /data/exp/raw/s1/sess1/session.toml
   ```

### Validation: Missing Required Fields

**Problem:**

```txt
✗ mouse-001/session-001: Missing required field 'session_start_time'
```

**Solution:**

```bash
# Edit session.toml
nano /data/my-experiment/raw/mouse-001/session-001/session.toml

# Add missing field:
session_start_time = "2024-01-15T14:30:00Z"

# Re-validate
python -m w2t_bkin.cli data validate /data/my-experiment --subject mouse-001 --session session-001
```

### Validation: Camera Files Not Found

**Problem:**

```txt
⚠ mouse-001/session-001: No files found for camera 'camera_0' (pattern: Video/camera_0/*.avi)
```

**Solutions:**

1. **Check symbolic links:**

   ```bash
   ls -la /data/my-experiment/raw/mouse-001/session-001/Video/camera_0/
   # Verify symlinks point to existing files
   ```

2. **Fix broken symlinks:**

   ```bash
   # Remove broken links
   find /data/my-experiment/raw/mouse-001/session-001/Video/camera_0/ -xtype l -delete

   # Re-import
   python -m w2t_bkin.cli data import-raw /correct-source-path \
     --experiment /data/my-experiment \
     --subject mouse-001 \
     --session session-001 \
     --confirm
   ```

3. **Mark camera as optional:**

   ```bash
   # Edit session.toml
   nano /data/my-experiment/raw/mouse-001/session-001/session.toml

   # Update camera:
   [[cameras]]
   id = "camera_0"
   optional = true  # ← Add this
   ```

### Invalid Subject/Session ID

**Problem:**

```txt
✗ Invalid subject ID: subject 001
  Use only letters, numbers, hyphens, and underscores
```

**Solution:**

```bash
# ❌ Invalid: Contains space
python -m w2t_bkin.cli data add-subject /data/exp "subject 001"

# ✅ Valid: Use hyphen or underscore
python -m w2t_bkin.cli data add-subject /data/exp subject-001
python -m w2t_bkin.cli data add-subject /data/exp subject_001
```

---

## Integration with Pipeline

### After Data Setup

Once data is organized and validated:

```bash
# 1. Validate structure
python -m w2t_bkin.cli data validate /data/my-experiment

# 2. Discover all sessions
python -m w2t_bkin.cli discover /data/my-experiment/config.toml --format tsv

# 3. Process single session
python -m w2t_bkin.cli run /data/my-experiment/config.toml mouse-001 session-001

# 4. Batch process all sessions
python -m w2t_bkin.cli batch /data/my-experiment/config.toml --max-workers 4
```

### Automated Setup Script

```bash
#!/bin/bash
# setup_experiment.sh

EXPERIMENT_ROOT="/data/whisker-2024"
RAW_DATA_ROOT="/raw-storage"

# Initialize
python -m w2t_bkin.cli data init "$EXPERIMENT_ROOT" \
  --lab "Larkum Lab" \
  --institution "Humboldt University" \
  --experimenters "Alice,Bob" \
  -y

# Add subjects
for subject in mouse-001 mouse-002 mouse-003; do
  python -m w2t_bkin.cli data add-subject "$EXPERIMENT_ROOT" "$subject" -y
done

# Add sessions and import
for session_dir in "$RAW_DATA_ROOT"/*; do
  subject=$(basename "$session_dir" | cut -d'-' -f1)
  session=$(basename "$session_dir" | cut -d'-' -f2)

  python -m w2t_bkin.cli data add-session "$EXPERIMENT_ROOT" "$subject" "$session" \
    --date "$(date -I)" \
    --description "Auto-imported session" \
    --experimenter "Alice" \
    -y

  python -m w2t_bkin.cli data import-raw "$session_dir" \
    --experiment "$EXPERIMENT_ROOT" \
    --subject "$subject" \
    --session "$session" \
    --confirm
done

# Validate
python -m w2t_bkin.cli data validate "$EXPERIMENT_ROOT" --verbose
```

---

## Reference

### File Pattern Glob Syntax

Session metadata files use glob patterns for file matching:

| Pattern                | Matches            | Example                        |
| ---------------------- | ------------------ | ------------------------------ |
| `*.avi`                | All .avi files     | `camera_0_001.avi`             |
| `Video/camera_0/*.avi` | .avi in subfolder  | `Video/camera_0/frame_001.avi` |
| `TTLs/ttl_*.txt`       | Pattern match      | `TTLs/ttl_camera.txt`          |
| `Bpod/*.mat`           | All .mat in folder | `Bpod/session_data.mat`        |

### ISO 8601 Date/Time Format

**Dates:**

- `2024-01-15` (YYYY-MM-DD)

**Date-times:**

- `2024-01-15T14:30:00Z` (UTC)
- `2024-01-15T14:30:00+01:00` (with timezone)

**Durations:**

- `P84D` (84 days)
- `P12W` (12 weeks)
- `P3M` (3 months)
- `P2Y` (2 years)

### Subject Sex Codes

| Code | Meaning           |
| ---- | ----------------- |
| `F`  | Female            |
| `M`  | Male              |
| `U`  | Unknown (default) |
| `O`  | Other             |

---

## See Also

- **[Configuration Parameters Guide](./configuration-parameters.md)** - Detailed parameter documentation
- **[Batch Processing Guide](./batch-processing.md)** - Multi-session processing
- **[Quick Start Guide](./quick-start-batch.md)** - Pipeline quick start
- **[Architecture Diagram](./architecture_diagram.mmd)** - System architecture
