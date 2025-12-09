# Data Management Commands

Commands for setting up and organizing experimental data structures.

## Overview

The data management commands help you:

- Initialize new experiments with proper folder structure
- Add subjects and sessions with metadata
- Import existing raw data safely (using symbolic links)
- Validate folder structures and metadata

**Key Safety Features:**

- Never moves or deletes original data
- Uses symbolic links for imports (preserves originals)
- Dry-run mode by default for import operations
- Comprehensive validation

---

## `data init` - Initialize Experiment

Create a new experiment folder structure with metadata and configuration files.

### Usage

```bash
w2t-bkin data init ROOT_PATH [OPTIONS]
```

### Arguments

- `ROOT_PATH` - Path to experiment root directory

### Options

- `--lab TEXT` - Lab name (prompted if not provided)
- `--institution TEXT` - Institution name (prompted if not provided)
- `--experimenters TEXT` - Comma-separated experimenter names (prompted if not provided)
- `--protocol TEXT` - Protocol ID (e.g., IACUC number)
- `--description TEXT` - Experiment description
- `--skip-docker-env` - Skip Docker .env generation
- `--yes, -y` - Skip confirmation prompts

### Created Structure

```
{ROOT_PATH}/
├── configuration.toml    # Pipeline configuration
├── data/
│   ├── raw/             # Raw data storage
│   │   └── metadata.toml # NWB metadata
│   ├── interim/         # Intermediate artifacts
│   ├── processed/       # Final outputs
│   └── external/        # External data
├── models/              # Trained models
└── docker/              # Auto-generated Docker config
    └── .env            # Environment variables
```

### Examples

```bash
# Interactive mode (prompts for values)
w2t-bkin data init /data/my-experiment

# Non-interactive mode
w2t-bkin data init /data/my-experiment \
  --lab "Larkum Lab" \
  --institution "HU Berlin" \
  --experimenters "Alice,Bob" \
  -y

# Skip Docker .env generation
w2t-bkin data init /data/my-experiment --skip-docker-env -y
```

### Docker Integration

By default, `data init` auto-generates a `.env` file for Docker Compose deployment. This includes:

- Absolute paths for volume mounts
- Prefect configuration
- Resource limits

To use containerized deployment after init:

```bash
cd /data/my-experiment
docker compose up -d server
docker compose up -d worker
```

---

## `data add-subject` - Add Subject

Add a new subject to the experiment with metadata.

### Usage

```bash
w2t-bkin data add-subject EXPERIMENT_ROOT SUBJECT_ID [OPTIONS]
```

### Arguments

- `EXPERIMENT_ROOT` - Path to experiment root directory
- `SUBJECT_ID` - Subject identifier (letters, numbers, hyphens, underscores only)

### Options

- `--species TEXT` - Species name (default: "Mus musculus")
- `--sex TEXT` - Sex: F|M|U|O (default: "U" - unknown)
- `--age TEXT` - Age in ISO 8601 duration (e.g., P84D for 84 days)
- `--genotype TEXT` - Genotype
- `--strain TEXT` - Strain
- `--date-of-birth TEXT` - Date of birth (ISO 8601)
- `--weight TEXT` - Weight
- `--description TEXT` - Subject description
- `--yes, -y` - Skip confirmation prompts

### Created Structure

```
{EXPERIMENT_ROOT}/data/raw/
└── {SUBJECT_ID}/
    └── subject.toml
```

### Examples

```bash
# Minimal
w2t-bkin data add-subject /data/my-experiment mouse-001 -y

# Full metadata
w2t-bkin data add-subject /data/my-experiment mouse-001 \
  --species "Mus musculus" \
  --sex F \
  --age P84D \
  --genotype "Thy1-GFP" \
  --strain "C57BL/6J" \
  --weight "25g" \
  -y
```

### ISO 8601 Duration Format

- `P84D` = 84 days
- `P12W` = 12 weeks
- `P3M` = 3 months
- `P2Y` = 2 years

---

## `data add-session` - Add Session

Add a new session for a subject with metadata and standard folders.

### Usage

```bash
w2t-bkin data add-session EXPERIMENT_ROOT SUBJECT_ID SESSION_ID [OPTIONS]
```

### Arguments

- `EXPERIMENT_ROOT` - Path to experiment root directory
- `SUBJECT_ID` - Subject identifier
- `SESSION_ID` - Session identifier (letters, numbers, hyphens, underscores only)

### Options

- `--date TEXT` - Session date in ISO 8601 (e.g., 2024-01-15) (default: today)
- `--description TEXT` - Session description (prompted if not provided)
- `--experimenter TEXT` - Experimenter name (prompted if not provided)
- `--start-time TEXT` - Session start time in ISO 8601 (e.g., 2024-01-15T14:30:00Z)
- `--no-subdirs` - Don't create Video/TTLs/Bpod folders
- `--yes, -y` - Skip confirmation prompts

### Created Structure

```
{EXPERIMENT_ROOT}/data/raw/{SUBJECT_ID}/
└── {SESSION_ID}/
    ├── session.toml     # Session metadata
    ├── Video/          # Video recordings (optional)
    ├── TTLs/           # TTL synchronization files (optional)
    └── Bpod/           # Bpod behavioral data (optional)
```

### Examples

```bash
# Interactive (prompts for description and experimenter)
w2t-bkin data add-session /data/my-experiment mouse-001 session-001

# Non-interactive
w2t-bkin data add-session /data/my-experiment mouse-001 session-001 \
  --date 2024-01-15 \
  --description "Behavioral training session" \
  --experimenter Alice \
  -y

# Without standard subfolders
w2t-bkin data add-session /data/my-experiment mouse-001 session-002 \
  --no-subdirs \
  -y
```

---

## `data import-raw` - Import Raw Data

Import existing raw data using symbolic links (SAFE - preserves originals).

### Usage

```bash
w2t-bkin data import-raw SOURCE [OPTIONS]
```

### Arguments

- `SOURCE` - Source directory containing raw data

### Required Options

- `--experiment, -e PATH` - Experiment root directory
- `--subject, -s TEXT` - Target subject ID
- `--session TEXT` - Target session ID

### Options

- `--no-detect` - Skip automatic file pattern detection
- `--confirm` - Execute import (required for actual operation)

### Safety Features

✅ **Symbolic links only** (never moves/copies/deletes)  
✅ **Originals preserved** in source directory  
✅ **Dry-run by default** (requires `--confirm` to execute)  
✅ **Auto-updates metadata** (session.toml with detected cameras/TTLs)

### File Detection

| Category | Patterns                                 | Target               |
| -------- | ---------------------------------------- | -------------------- |
| Video    | `*.avi`, `*.mp4`, `*.mkv`, `*.mov`       | `Video/{camera_id}/` |
| TTL      | `*ttl*.txt`, `*pulse*.txt`, `*sync*.txt` | `TTLs/`              |
| Bpod     | `*.mat`                                  | `Bpod/`              |
| Other    | Everything else                          | `Other/`             |

### Workflow

```bash
# Step 1: Preview (dry-run, safe - no changes)
w2t-bkin data import-raw /raw-storage/2024-01-15 \
  -e /data/my-experiment \
  -s mouse-001 \
  --session session-001

# Output shows detected files and target locations

# Step 2: Execute (creates symbolic links)
w2t-bkin data import-raw /raw-storage/2024-01-15 \
  -e /data/my-experiment \
  -s mouse-001 \
  --session session-001 \
  --confirm
```

### Post-Import

After import, **review and update** `session.toml`:

- Camera FPS values (defaults to 30.0)
- Camera-TTL mappings
- TTL channel descriptions

---

## `data validate` - Validate Structure

Validate experiment folder structure and metadata.

### Usage

```bash
w2t-bkin data validate EXPERIMENT_ROOT [OPTIONS]
```

### Arguments

- `EXPERIMENT_ROOT` - Path to experiment root directory

### Options

- `--subject TEXT` - Filter by specific subject ID
- `--session TEXT` - Filter by specific session ID
- `--verbose, -v` - Show detailed validation info

### Checks

- ✓ Required folders exist (raw/, interim/, processed/)
- ✓ Root metadata.toml exists and is valid
- ✓ Subject folders have subject.toml
- ✓ Session folders have session.toml
- ✓ Referenced files in metadata exist
- ✓ Camera/TTL configurations are complete

### Examples

```bash
# Validate entire experiment
w2t-bkin data validate /data/my-experiment

# Validate specific subject
w2t-bkin data validate /data/my-experiment --subject mouse-001

# Validate specific session (verbose)
w2t-bkin data validate /data/my-experiment \
  --subject mouse-001 \
  --session session-001 \
  --verbose
```

### Output

```
Errors:
  ✗ Missing required folder: data/processed/
  ✗ Missing session-002/session.toml

Warnings:
  ⚠ Missing root metadata: data/raw/metadata.toml

✗ Validation failed
  2 error(s), 1 warning(s)
```

---

## See Also

- [Pipeline Commands](pipeline-commands.md) - Process sessions
- [Validation Commands](validation.md) - NWB validation
- [Configuration Guide](../configuration-parameters.md) - Pipeline configuration
