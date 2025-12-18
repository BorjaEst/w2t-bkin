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

### Using Pre-built Images (Recommended)

This is the **primary deployment method** for w2t-bkin. Production mode uses Docker workers exclusively:

```bash
# Pull latest worker image
docker pull ghcr.io/borjaest/w2t-bkin:latest

# Start Prefect server in production mode (from experiment directory)
cd /path/to/experiment
w2t-bkin server start --config configs/standard.toml

# Start Docker worker (in a separate terminal)
w2t-bkin worker start
```

The worker will automatically:

- Connect to the Prefect server via the API URL
- Poll the `docker-pool` for flow runs
- Start containers for each flow run with the specified image
- Mount data directories from `.workers/.env`

**Configuration** (`.workers/.env`):

```bash
W2T_DOCKER_IMAGE=ghcr.io/borjaest/w2t-bkin:latest
# Add data paths as needed
```

### Development Mode (Optional)

For rapid iteration without Docker builds, use dev mode:

```bash
# Requires worker extras: pip install -e .[worker]
w2t-bkin server start --config configs/standard.toml --dev
```

This uses Prefect Runner to serve flows in the server process - no Docker worker needed!

### Manual Build (For Customization)

Build custom worker images from repository root:

```bash
# Build from repository root with explicit Dockerfile path
docker build -f docker/Dockerfile -t w2t-bkin:local-dev .

# Tag for testing
docker tag w2t-bkin:local-dev ghcr.io/borjaest/w2t-bkin:custom

# Update .workers/.env to use your custom image
W2T_DOCKER_IMAGE=ghcr.io/borjaest/w2t-bkin:custom
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
- `WORK_POOL`: Work pool name (default: `docker-pool`)
- `WORKER_NAME`: Worker identifier (default: `docker-worker`)
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

The production deployment uses **Prefect Docker Work Pool**:

1. **Prefect Server**: Orchestration server with web UI (port 4200)
2. **Docker Work Pool** (`docker-pool`): Infrastructure configuration for Docker-based execution
3. **Docker Workers**: Poll the work pool and execute flows in fresh containers per run

**Why Docker Workers?**

- ✅ **Isolation**: Each flow run executes in a fresh container
- ✅ **Reproducibility**: Same image guarantees consistent environment
- ✅ **Flexibility**: Different flows can use different images
- ✅ **Resource management**: Container limits prevent runaway processes
- ✅ **Simple scaling**: Start more workers to handle more concurrent runs

**Development Alternative**: Use `--dev` mode for rapid iteration without Docker overhead (flows run via Prefect Runner in server process)

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

### Production (Recommended: Use CLI)

```bash
# Start Prefect server
w2t-bkin server start

# In another terminal, start workers
w2t-bkin worker start

# Or with multiple workers
w2t-bkin worker start --count 4
```

### Development (No Workers Needed)

For development, use `--dev` mode which serves flows without workers:

```bash
# Install worker dependencies
pip install -e .[worker]

# Start in dev mode (flows run in server process)
w2t-bkin server start --dev
```

### Advanced: Manual Docker Worker (Alternative)

If you need to run workers manually:

```bash
# Start Prefect server first
w2t-bkin server start

# In another terminal, run worker container manually
docker run -d \
  --name w2t-worker \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  -e WORK_POOL=docker-pool \
  -e WORKER_NAME=manual-worker \
  ghcr.io/borjaest/w2t-bkin:latest \
  prefect worker start --pool docker-pool --name manual-worker
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
