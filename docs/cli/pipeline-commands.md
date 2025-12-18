# Pipeline Commands

Commands for running the w2t-bkin processing pipeline using Prefect orchestration.

## Overview

The w2t-bkin pipeline uses a **UI-first workflow** powered by Prefect. Instead of CLI commands to run individual sessions, you:

1. Start the Prefect server: `w2t-bkin server start`
2. Use the Prefect UI at `http://localhost:4200` to trigger workflows
3. Monitor execution in real-time

## `server` - Prefect Server Management

Manage the Prefect server for pipeline orchestration.

### Server Commands

```bash
w2t-bkin server start [OPTIONS]   # Start Prefect server and create deployments
w2t-bkin server stop               # Stop running server
w2t-bkin server status             # Check if server is running
w2t-bkin server restart [OPTIONS]  # Restart server
```

### Server Start Options

- `--config, -c PATH` - Default config file for deployments
- `--dev` - Development mode (serves flows locally with Runner, requires worker extras)
- `--port, -p INT` - Prefect UI port (default: 4200)
- `--browser/--no-browser` - Open browser automatically (default: true)
- `--workers INT` - Number of Docker workers to auto-start (default: 1 for production, 0 for dev)
- `--log-level TEXT` - Logging level (default: INFO)

### Examples

```bash
# Production mode (default) - uses Docker workers
w2t-bkin server start

# Start with 4 Docker workers for parallel processing
w2t-bkin server start --workers 4

# Start without auto-starting workers (manual setup)
w2t-bkin server start --workers 0

# Development mode - runs flows locally (requires worker extras)
w2t-bkin server start --dev

# Check server status
w2t-bkin server status

# Stop server (also stops all auto-started workers)
w2t-bkin server stop
```

### What `server start` Does

#### Production Mode (Default)

1. **Starts Prefect Server** - Launches at `http://localhost:4200`
2. **Creates Work Pool** - Creates `docker-pool` (type: docker) for Docker-based execution
3. **Creates Deployments** - Uses `.deploy()` to create:
   - `process-session` - Single session processing
   - `batch-process` - Batch processing
4. **Auto-starts Workers** - Starts the specified number of Docker workers (default: 1)
   - Workers pull image from `.workers/.env` (default: `ghcr.io/borjaest/w2t-bkin:latest`)
   - Each worker starts containers for flow runs
5. **Opens Browser** - Automatically opens Prefect UI (unless `--no-browser`)

#### Development Mode (--dev)

1. **Starts Prefect Server** - Launches at `http://localhost:4200`
2. **Validates Worker Extras** - Checks that worker dependencies are installed
3. **Serves Flows** - Uses Runner to serve flows in server process:
   - `process-session` - Single session processing
   - `batch-process` - Batch processing
4. **Opens Browser** - Automatically opens Prefect UI (unless `--no-browser`)

No work pool or workers needed - flows run directly in the server process!
Runtime config is injected via `W2T_RUNTIME_CONFIG_JSON` environment variable (same as production).

### Worker Management

**Production Mode (Docker Workers)**:

Auto-start (recommended):

```bash
# Automatically starts 1 Docker worker
w2t-bkin server start

# Start with 4 workers for parallel processing
w2t-bkin server start --workers 4
```

Manual setup (if you disabled auto-start with `--workers 0`):

```bash
# In a new terminal
w2t-bkin worker start
```

Alternatively, use the raw Prefect command:

```bash
source .workers/.env
prefect worker start --pool docker-pool --type docker
```

````

**Development Mode (No Workers)**:

```bash
# Development mode - flows run in server process
w2t-bkin server start --dev

# No worker needed - flows execute directly!
````

---

## Processing Workflows

### Single Session Processing

**Via Prefect UI (Production Mode):**

1. Start server: `w2t-bkin server start` (Docker workers auto-start by default)
2. Navigate to `http://localhost:4200`
3. Go to **Deployments** → **process-session**
4. Click **Run**
5. Set parameters:
   - `config_path`: Path to configuration TOML
   - `subject_id`: Subject identifier (e.g., "subject-001")
   - `session_id`: Session identifier (e.g., "session-001")
   - `skip_bpod`: Skip Bpod processing (optional)
   - `skip_pose`: Skip pose estimation (optional)
   - `skip_nwb_validation`: Skip NWB validation (optional)
6. Click **Submit**
7. Monitor in **Flow Runs** tab

**Via Prefect UI (Development Mode):**

Same as above, but start server with: `w2t-bkin server start --dev`

Flows run directly in the server process - faster iteration, no Docker builds needed!

**Via Python API:**

```python
from w2t_bkin.flows import process_session_flow
from w2t_bkin.api import SessionFlowConfig

config = SessionFlowConfig(
    config_path="configs/standard.toml",
    subject_id="subject-001",
    session_id="session-001"
)

# Direct execution (no UI, no Prefect)
result = process_session_flow(config=config)
```

### Batch Processing

**Via Prefect UI:**

1. Start server: `w2t-bkin server start`
2. Navigate to `http://localhost:4200`
3. Go to **Deployments** → **batch-process**
4. Click **Run**
5. Set parameters:
   - `config_path`: Path to configuration TOML
   - `subject_filter`: Glob pattern for subjects (optional)
   - `session_filter`: Glob pattern for sessions (optional)
   - `max_parallel`: Maximum parallel sessions (1-16, default: 4)
   - `skip_bpod`: Skip Bpod processing (optional)
   - `skip_pose`: Skip pose estimation (optional)
   - `skip_nwb_validation`: Skip NWB validation (optional)
6. Click **Submit**
7. Monitor parallel execution in **Flow Runs** tab

**Via Python API:**

```python
from w2t_bkin.flows import batch_process_flow
from w2t_bkin.api import BatchFlowConfig

config = BatchFlowConfig(
    config_path="configs/standard.toml",
    subject_filter="subject-001",  # Optional
    max_parallel=4
)

# Direct execution (no UI)
result = batch_process_flow(config=config)
```

---

## Pipeline Phases

Both `process-session` and `batch-process` execute these phases:

1. **Initialization** - Load config and create NWBFile
2. **Discovery** - Find and verify raw data files
3. **Artifact Generation** - Generate pose estimation (optional)
4. **Ingestion** - Process Bpod, Pose, and TTL data
5. **Assembly** - Build NWB behavior tables
6. **Finalization** - Write and validate NWB file

---

## Worker Configuration

The pipeline can run with two types of workers:

### Docker Workers (Recommended)

- **Isolation**: Each task runs in isolated container
- **Dependencies**: All ML/video dependencies included
- **Setup**: Automatic via `server start --work-pool docker`

**Start Docker worker:**

```bash
# Pull pre-built worker image
docker pull ghcr.io/borjaest/w2t-bkin:latest

# Run worker
docker run -d \
  -v $(pwd)/data:/data \
  -v $(pwd)/models:/models \
  -v $(pwd)/configs:/configs \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  --name w2t-worker \
  ghcr.io/borjaest/w2t-bkin:latest
```

---

## Monitoring and Debugging

### Prefect UI Features

- **Flow Runs** - View all executions (running, completed, failed)
- **Logs** - Real-time logs for each flow run
- **Task Runs** - Detailed breakdown of each pipeline phase
- **Artifacts** - View outputs and intermediate results
- **Retries** - Automatic retry on transient failures

### Command-Line Monitoring

```bash
# Check server status
w2t-bkin server status

# View logs (if running in terminal)
# Press Ctrl+C to stop server

# Stop server
w2t-bkin server stop
```

---

## Migration from Old CLI

**Old CLI (Removed):**

```bash
# ❌ No longer available
w2t-bkin run config.toml subject-001 session-001
w2t-bkin batch config.toml --max-workers 4
w2t-bkin serve-session ...
w2t-bkin serve-batch ...
```

**New Workflow:**

```bash
# ✅ Start server once
w2t-bkin server start

# ✅ Use Prefect UI for all workflows
# Open http://localhost:4200
# Navigate to Deployments → process-session or batch-process
# Configure parameters via UI
# Submit and monitor
```

See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for complete migration instructions.

### With Prefect UI

For real-time monitoring and batch processing:

```bash
# Start Prefect server (opens browser at http://localhost:4200)
w2t-bkin server start

# In Prefect UI:
# Navigate to Deployments → batch-process
# Set parameters (config path, filters, max workers)
# Click Run
# Monitor real-time progress, logs, and statistics
```

---

## `discover` - List Available Sessions

Scan raw data directory and list all processable sessions.

### Discover Usage

```bash
w2t-bkin discover CONFIG_PATH [OPTIONS]
```

### Discover Arguments

- `CONFIG_PATH` - Path to configuration TOML file

### Discover Options

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

```text
subject-001     session-001
subject-002     session-002
```

#### Plain

Human-readable table with Rich formatting

### Discover Examples

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

### Version Usage

```bash
w2t-bkin version
```

### Example Output

```text
w2t-bkin version 0.0.11

W2T Body Kinematics Pipeline
Prefect-native NWB processing for behavioral neuroscience

https://github.com/BorjaEst/w2t-bkin
```

---

## See Also

- [Data Management](data-management.md) - Experiment setup commands
- [Validation Commands](validation.md) - NWB validation
- [Configuration Guide](../configuration-parameters.md) - Pipeline configuration
