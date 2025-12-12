# Migration Guide: New UI-First Workflow

This guide explains the new simplified workflow for w2t-bkin.

## Summary of Changes

| Aspect            | New Workflow                                 |
| ----------------- | -------------------------------------------- |
| **Installation**  | `pip install w2t-bkin` or `w2t-bkin[worker]` |
| **Running flows** | Prefect UI at http://localhost:4200          |
| **Starting**      | `w2t-bkin server start` (one command)        |
| **Workers**       | Docker (default) or local (optional)         |
| **CLI commands**  | Removed: `run`, `batch`, `serve-*`           |

## New Workflow

### 1. Installation

```bash
# Base installation (sufficient for most users)
pip install w2t-bkin

# Only install [worker] if you want LOCAL workers instead of Docker
pip install w2t-bkin[worker]
```

**Important**: You don't need `[worker]` extras unless you want to run workers locally. The base installation includes everything needed for the CLI and server.

### 2. Start Server

```bash
# Start Prefect server with automatic deployments
cd /your/workspace
w2t-bkin server start --config configs/standard.toml

# This automatically:
# 1. Starts Prefect server at http://localhost:4200
# 2. Creates deployments (process-session, batch-process)
# 3. Opens your browser to the Prefect UI
# 4. Detects if you have [worker] extras and configures work pool accordingly
```

### 3. Start Workers

**Option A: Docker Worker (Recommended)**

```bash
# Pull pre-built worker image from GitHub Container Registry
docker pull ghcr.io/borjaest/w2t-bkin:latest

# Run worker container
docker run -d \
  -v $(pwd)/data:/data \
  -v $(pwd)/models:/models \
  -v $(pwd)/configs:/configs \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  -e WORK_POOL=docker-pool \
  --name w2t-worker \
  ghcr.io/borjaest/w2t-bkin:latest
```

**Option B: Local Worker (Only if w2t-bkin[worker] installed)**

```bash
# Start local worker
prefect worker start --pool local-pool --type process
```

### 4. Run Workflows in UI

1. Open **http://localhost:4200** (automatically opened by `server start`)
2. Navigate to **Deployments**
3. Click **process-session** or **batch-process**
4. Click **Run** button
5. Fill in parameters:
   - Config path: `/configs/standard.toml`
   - Subject ID: `mouse-001`
   - Session ID: `session-001`
6. Click **Run** to start
7. Monitor progress in **Flow Runs** tab

## Removed Commands

These CLI commands have been **removed**:

- ❌ `w2t-bkin run` - Use Prefect UI instead
- ❌ `w2t-bkin batch` - Use Prefect UI instead
- ❌ `w2t-bkin serve-session` - Use `server start` + UI
- ❌ `w2t-bkin serve-batch` - Use `server start` + UI

## Retained Commands

- ✅ `w2t-bkin server start` - **NEW**: Start everything
- ✅ `w2t-bkin discover` - List available sessions
- ✅ `w2t-bkin validate` - Validate NWB files
- ✅ `w2t-bkin inspect` - Inspect NWB files
- ✅ `w2t-bkin data *` - All data management commands

## Complete Example

```bash
# 1. Install
pip install w2t-bkin

# 2. Setup workspace
w2t-bkin data init /data/experiment
w2t-bkin data add-subject /data/experiment mouse-001 --species "Mus musculus" -y
w2t-bkin data add-session /data/experiment mouse-001 session-001 -y

# 3. Start server
cd /data/experiment
w2t-bkin server start --config configs/standard.toml

# 4. Start Docker worker (in another terminal)
docker pull ghcr.io/borjaest/w2t-bkin:latest
docker run -d \
  -v $(pwd)/data:/data \
  -v $(pwd)/models:/models \
  -v $(pwd)/configs:/configs \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  --name w2t-worker \
  ghcr.io/borjaest/w2t-bkin:latest

# 5. Use UI at http://localhost:4200 to run workflows
```

## Advanced: Python API

For advanced users who need programmatic control:

```python
from w2t_bkin.api import SessionFlowConfig
from w2t_bkin.flows import process_session_flow

# Create configuration
config = SessionFlowConfig(
    config_path="configs/standard.toml",
    subject_id="mouse-001",
    session_id="session-001",
    skip_pose=True  # Optional
)

# Direct execution (bypasses Prefect)
result = process_session_flow(config=config)

if result.success:
    print(f"✓ NWB written to: {result.nwb_path}")
```

## Work Pool Selection

The `server start` command automatically detects the appropriate work pool:

- **Has `[worker]` extras**: Creates `local-pool` (process-based)
- **No `[worker]` extras**: Creates `docker-pool` (container-based)

Override with `--work-pool`:

```bash
# Force Docker pool
w2t-bkin server start --work-pool docker

# Force local pool (requires [worker] extras)
w2t-bkin server start --work-pool local
```

## Benefits

✅ **Simpler**: One command starts everything  
✅ **UI-First**: Professional workflow monitoring  
✅ **Flexible**: Docker or local workers  
✅ **No heavy deps**: Base installation is lightweight  
✅ **Better UX**: Visual parameter forms in UI

## Troubleshooting

### "Worker not picking up work"

Make sure:

1. Worker is running (`docker ps` or check Prefect UI → Work Pools)
2. Work pool name matches (`docker-pool` or `local-pool`)
3. `PREFECT_API_URL` points to server correctly

### "Deployment parameters empty"

The UI auto-generates forms from Pydantic models. Fill in all required fields:

- `config_path`: Full path to config file (e.g., `/configs/standard.toml`)
- `subject_id`: Subject identifier
- `session_id`: Session identifier

### "Cannot import worker dependencies"

If using local workers, install worker extras:

```bash
pip install w2t-bkin[worker]
```

For Docker workers, dependencies are included in the image.

## Getting Help

- **Documentation**: [docs/README.md](README.md)
- **Cheat Sheet**: [CHEATSHEET.md](../CHEATSHEET.md)
- **Issues**: https://github.com/BorjaEst/w2t-bkin/issues
