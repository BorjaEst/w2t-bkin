# W2T-BKIN Docker Configuration

This directory contains the Docker configuration for running w2t-bkin workers in containerized environments.

**Note**: For users on Windows, we recommend [Rancher Desktop](https://rancherdesktop.io/) as it provides Docker runtime automatically without requiring Docker knowledge.

## Prerequisites

- **Rancher Desktop** (recommended for Windows)
  - Download from [rancherdesktop.io](https://rancherdesktop.io/)
  - Provides Docker automatically
  - No Docker knowledge required
- **OR Docker Desktop** (alternative)

## Quick Start

### Using Pre-built Images (Recommended for Users)

Pull and run the official pre-built worker image from GitHub Container Registry:

```bash
# Pull latest worker image
docker pull ghcr.io/borjaest/w2t-bkin:latest

# Run worker (connects to Prefect server on host)
docker run -d \
  --name w2t-worker \
  -v /path/to/data:/data:ro \
  -v /path/to/models:/models:ro \
  -v /path/to/configs:/configs:ro \
  -v /path/to/output:/data/processed:rw \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  -e WORK_POOL=process-pool \
  ghcr.io/borjaest/w2t-bkin:latest

# Check logs
docker logs -f w2t-worker

# Stop worker
docker stop w2t-worker
docker rm w2t-worker
```

### Manual Build (For Development)

Build the worker image from repository root:

```bash
# CORRECT: Build from repository root with explicit Dockerfile path
docker build -f docker/Dockerfile -t ghcr.io/borjaest/w2t-bkin:dev .

# WRONG: This will fail because context is docker/ directory
docker build -t ghcr.io/borjaest/w2t-bkin:dev docker
```

## Files

- **Dockerfile**: Multi-stage worker image with optimized layer caching
- **start-worker.sh**: Entrypoint script for Prefect worker containers
- **README.md**: This file

## Build Context

**Critical**: The Dockerfile must be built from the **repository root** (`.`) as the build context because it needs access to:

- `src/` - Python package source code
- `nwb-extensions/` - Git submodules with NWB extensions
- `pyproject.toml` - Package dependencies
- `README.md` - Package metadata

**Correct build command:**

```bash
docker build -f docker/Dockerfile -t w2t-bkin:worker .
#            ^^^ Specify Dockerfile      Tag       ^^^ Context = repo root
```

## Environment Variables

Configure worker behavior via environment variables (in `.env` file or `docker run -e` flags):

### Prefect Connection

- `PREFECT_API_URL`: Prefect server URL (default: `http://host.docker.internal:4200/api`)
- `WORK_POOL`: Work pool name (default: `process-pool`)
- `WORKER_NAME`: Worker identifier (default: `worker`)
- `PREFECT_LOGGING_LEVEL`: Log verbosity (default: `INFO`)

### Data Paths

- `DATA_ROOT`: Mount point for data directory (default: `/data`)
- `MODELS_ROOT`: Mount point for models (default: `/models`)
- `CONFIG_ROOT`: Mount point for configs (default: `/configs`)
- `OUTPUT_ROOT`: Mount point for outputs (default: `/output`)

### Resource Limits

- `WORKER_REPLICAS`: Number of worker containers (default: `1`)
- `WORKER_CPU_LIMIT`: Max CPU cores per worker (default: `4`)
- `WORKER_MEMORY_LIMIT`: Max memory per worker (default: `8G`)
- `WORKER_CPU_RESERVATION`: Reserved CPU cores (default: `1`)
- `WORKER_MEMORY_RESERVATION`: Reserved memory (default: `2G`)

## Architecture

The Docker deployment uses **Prefect Process Work Pools**:

1. **PostgreSQL**: Prefect backend database
2. **Prefect Server**: Orchestration server with web UI (port 4200)
3. **Workers**: Execute pipeline flows as subprocesses

**Why Process Pools?**

- ✅ No Docker socket access required (better security)
- ✅ No container-in-container overhead
- ✅ Predictable resource usage
- ✅ Simpler debugging with unified logs
- ✅ Fast startup times

## Image Tags

Production images are published to GitHub Container Registry (GHCR):

- `ghcr.io/borjaest/w2t-bkin:latest` - Latest stable release
- `ghcr.io/borjaest/w2t-bkin:v0.0.10` - Specific version
- `ghcr.io/borjaest/w2t-bkin:dev` - Development branch builds

## Layer Caching Strategy

The Dockerfile uses an optimized layer ordering to maximize Docker cache reuse:

1. **NWB extensions** (rarely change) → Cached
2. **pyproject.toml** (occasionally changes) → Triggers dependency rebuild
3. **Dummy package + pip install** (10+ min) → Only when deps change
4. **Source code** (frequently changes) → Fast rebuild (30 sec)

**Result**: Editing Python code triggers only step 4, keeping rebuilds fast.

## Troubleshooting

### Build Fails: "/src: not found"

**Problem**: Build context is set incorrectly.

**Solution**: Always build from repository root:

```bash
# Correct - build from repository root
docker build -f docker/Dockerfile -t w2t-bkin:worker .

# Wrong - context is docker/ directory (can't see src/, nwb-extensions/, etc.)
docker build -t w2t-bkin:worker docker
```

## Running Workers

### Production (Manual Docker Run)

```bash
# Start Prefect server on host first
prefect server start

# In another terminal, run worker
docker run -d \
  --name w2t-worker \
  -v $(pwd)/data:/data \
  -v $(pwd)/models:/models \
  -v $(pwd)/configs:/configs \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  -e WORK_POOL=process-pool \
  w2t-bkin:worker
```

### Development (Local Python)

For development, run workers locally without Docker:

```bash
# Install worker dependencies
pip install -e .[worker]

# Start worker
prefect worker start --pool process-pool
```

### Worker Cannot Connect to Server

**Problem**: `PREFECT_API_URL` points to wrong host.

**Solution**: Use the correct URL for your setup:

- **Docker worker → Host server**: `PREFECT_API_URL=http://host.docker.internal:4200/api`
- **Local worker → Local server**: `PREFECT_API_URL=http://localhost:4200/api`

### Submodule Errors

**Problem**: NWB extension submodules not initialized.

**Solution**:

```bash
git submodule update --init --recursive
```

### Permission Errors on Mounted Volumes

**Problem**: Worker runs as uid 1000, host files owned by different user.

**Solution**:

```bash
# Fix ownership to match container user (uid 1000)
sudo chown -R 1000:1000 data/ models/ configs/ output/
```

## See Also

- [Migration Guide](../docs/MIGRATION_GUIDE.md) - Migrating from Docker-first workflow
- [Prefect UI Configuration](../docs/reference/prefect-ui-configuration.md) - Using the Prefect web interface
- [Architecture Design](../docs/development/design.md) - Technical architecture overview
