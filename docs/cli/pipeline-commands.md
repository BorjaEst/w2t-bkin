# Pipeline Commands

Commands for processing behavioral and kinematic data through the w2t-bkin pipeline.

## `run` - Process Single Session

Execute the complete pipeline for a single subject/session.

### Usage

```bash
w2t-bkin run CONFIG_PATH SUBJECT_ID SESSION_ID [OPTIONS]
```

### Arguments

- `CONFIG_PATH` - Path to configuration TOML file
- `SUBJECT_ID` - Subject identifier (e.g., "subject-001")
- `SESSION_ID` - Session identifier (e.g., "session-001")

### Options

- `--skip-bpod` - Skip Bpod processing
- `--skip-pose` - Skip pose estimation
- `--skip-ttl` - Skip TTL processing
- `--skip-validation` - Skip NWB validation
- `--log-level TEXT` - Logging level (DEBUG|INFO|WARNING|ERROR|CRITICAL)

### Examples

```bash
# Basic usage
w2t-bkin run config.toml subject-001 session-001

# Skip pose estimation (faster)
w2t-bkin run config.toml subject-001 session-001 --skip-pose

# Debug mode
w2t-bkin run config.toml subject-001 session-001 --log-level DEBUG
```

### Pipeline Phases

The `run` command executes these phases via Prefect:

1. **Initialization** - Load config and create NWBFile
2. **Discovery** - Find and verify files
3. **Artifact Generation** - Generate pose estimation (optional)
4. **Ingestion** - Process Bpod, Pose, and TTL data
5. **Assembly** - Build NWB behavior tables
6. **Finalization** - Write and validate NWB file

---

## `batch` - Process Multiple Sessions

Process multiple sessions in parallel using Prefect orchestration.

### Usage

```bash
w2t-bkin batch CONFIG_PATH [OPTIONS]
```

### Arguments

- `CONFIG_PATH` - Path to configuration TOML file

### Options

- `--subject, -s TEXT` - Filter by specific subject ID
- `--session, -x TEXT` - Filter by specific session ID
- `--max-workers, -j INT` - Maximum concurrent sessions (default: 4)
- `--skip-bpod` - Skip Bpod processing for all sessions
- `--skip-pose` - Skip pose estimation for all sessions
- `--skip-validation` - Skip NWB validation for all sessions
- `--log-level TEXT` - Logging level

### Examples

```bash
# Process all sessions with 4 parallel workers
w2t-bkin batch config.toml --max-workers 4

# Process specific subject
w2t-bkin batch config.toml --subject subject-001 --max-workers 2

# Process specific session across all subjects
w2t-bkin batch config.toml --session session-001

# Fast processing (skip pose and validation)
w2t-bkin batch config.toml --skip-pose --skip-validation --max-workers 8
```

### Features

- **Automatic Retries** - 2 retry attempts with 60-second delays
- **Parallel Execution** - Configurable worker count
- **Graceful Errors** - Partial failures don't stop batch
- **Aggregated Results** - Summary statistics at end

### With Prefect UI

For real-time monitoring:

```bash
# Terminal 1: Start Prefect server
docker compose up -d server

# Terminal 2: Run batch processing
w2t-bkin batch config.toml --max-workers 4

# Open browser to http://localhost:4200
# View real-time progress, logs, and statistics
```

---

## `discover` - List Available Sessions

Scan raw data directory and list all processable sessions.

### Usage

```bash
w2t-bkin discover CONFIG_PATH [OPTIONS]
```

### Arguments

- `CONFIG_PATH` - Path to configuration TOML file

### Options

- `--subject, -s TEXT` - Filter by specific subject ID
- `--session, -x TEXT` - Filter by specific session ID
- `--format, -f TEXT` - Output format: json|tsv|plain (default: json)

### Output Formats

#### JSON (Default)

Detailed output with metadata information:

```json
[
  {
    "subject": "subject-001",
    "session": "session-001",
    "has_subject_metadata": true,
    "metadata_file": "session.toml"
  }
]
```

#### TSV

Tab-separated for piping to tools:

```
subject-001     session-001
subject-002     session-002
```

#### Plain

Human-readable table with Rich formatting

### Examples

```bash
# List all sessions (JSON)
w2t-bkin discover config.toml

# Human-readable table
w2t-bkin discover config.toml --format plain

# Filter by subject
w2t-bkin discover config.toml --subject subject-001

# Pipe to GNU Parallel
w2t-bkin discover config.toml --format tsv | \
  parallel --col-sep '\t' w2t-bkin run config.toml {1} {2}
```

---

## `version` - Show Version

Display version information.

### Usage

```bash
w2t-bkin version
```

### Example Output

```
w2t-bkin version 0.0.10

W2T Body Kinematics Pipeline
Prefect-native NWB processing for behavioral neuroscience

https://github.com/BorjaEst/w2t-bkin
```

---

## See Also

- [Data Management](data-management.md) - Experiment setup commands
- [Validation Commands](validation.md) - NWB validation
- [Configuration Guide](../configuration-parameters.md) - Pipeline configuration
