# W2T-BKIN Docker Configuration

This directory contains the Docker configuration for running w2t-bkin in containerized environments.

**Note**: For users on Windows, we recommend [Rancher Desktop](https://rancherdesktop.io/) as it provides Docker runtime automatically without requiring Docker knowledge.

## Image Architecture

W2T-BKIN uses a **two-image architecture** for clean separation of concerns:

1. **Runner Image** (`Dockerfile`) - Flow execution environment

   - Contains w2t-bkin + all dependencies
   - Used by Prefect deployments (`image=...` parameter)
   - Containers are short-lived (one per flow run)
   - **This is what `W2T_DOCKER_IMAGE` should point to**

2. **Worker Image** (`Dockerfile.worker`) - Long-lived worker process
   - Wraps the runner image
   - Runs `prefect worker start` to poll for work
   - Creates runner containers for each flow run
   - Optional convenience image (you can also run workers via CLI)

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
# Pull latest runner image (for flow execution)
docker pull ghcr.io/borjaest/w2t-bkin:latest

# Start Prefect server in production mode (from experiment directory)
cd /path/to/experiment
w2t-bkin server start --config configs/standard.toml

# Start Docker worker (in a separate terminal)
# Option 1: Using CLI (recommended - runs on host)
w2t-bkin worker start --pool docker-pool --type docker

# Option 2: Using worker image (runs worker in container)
docker run --rm --name w2t-worker --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e PREFECT_API_URL=http://127.0.0.1:4200/api \
  ghcr.io/borjaest/w2t-bkin:latest-worker
```

The worker will automatically:

- Connect to the Prefect server via the API URL
- Poll the `docker-pool` for flow runs
- Start **runner containers** for each flow run with the image specified in `W2T_DOCKER_IMAGE`
- Mount data directories from `.workers/.env`

**Configuration** (`.workers/.env`):

```bash
# CRITICAL: This must be the RUNNER image, not the worker image
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

Build custom images from repository root:

```bash
# Step 1: Build runner image (slow - contains all dependencies)
docker build -f docker/Dockerfile -t w2t-bkin:local .

# Step 2: Build worker image (fast - wraps runner image)
docker build -f docker/Dockerfile.worker -t w2t-bkin-worker:local .

# Update .workers/.env to use your custom runner image
W2T_DOCKER_IMAGE=w2t-bkin:local
```

**Important**: The worker image is optional. You can run workers via CLI (`w2t-bkin worker start`) instead of using a worker container.

## Files

- **Dockerfile**: Builds the runner image (for flow execution)
- **Dockerfile.worker**: Builds the worker image (wraps runner, starts prefect worker)
- **start-worker.sh**: Entrypoint script for Prefect worker containers
- **README.md**: This file

## Build Context

**Critical**: Both Dockerfiles must be built from the **repository root** (`.`) as the build context because they need access to:

- `src/` - Python package source code
- `nwb-extensions/` - Git submodules with NWB extensions
- `pyproject.toml` - Package dependencies
- `README.md` - Package metadata

**Correct build commands:**

```bash
# Runner image (base)
docker build -f docker/Dockerfile -t w2t-bkin:local .
#            ^^^ Dockerfile path        Tag      ^^^ Context = repo root

# Worker image (wraps runner)
docker build -f docker/Dockerfile.worker -t w2t-bkin-worker:local .
```

## Environment Variables

Configure worker behavior via environment variables (in `.env` file or `docker run -e` flags):

### Prefect Connection

- `PREFECT_API_URL`: Prefect server URL (default: `http://host.docker.internal:4200/api`)
- `WORK_POOL`: Work pool name (default: `docker-pool`)
- `WORKER_NAME`: Worker identifier (default: `docker-worker`)
- `PREFECT_LOGGING_LEVEL`: Log verbosity (default: `INFO`)

### Data Volume Mounts

**Automatic Volume Configuration**: When you run `w2t-bkin server start` in production mode, the `docker-pool` work pool is automatically configured with volume mounts based on your project directory structure:

```text
Host Path (project_root)              → Container Path
--------------------------------------   ---------------
{project_root}/data                   → /data
{project_root}/models                 → /models
{project_root}/output                 → /output
{project_root}/configuration.toml     → /configs/configuration.toml
```

These mounts are set in the work pool's **base job template** when the pool is created. The runtime configuration (`W2T_RUNTIME_CONFIG_JSON`) uses container-native paths (`/data/raw`, `/models`, etc.), which are then accessible via the automatically mounted volumes.

**No manual volume configuration required** - the Docker worker inherits these mounts from the work pool job template and applies them to every flow-run container it creates.

### Path Override Environment Variables (Advanced)

These variables can override container paths if you have custom requirements, but normally you should configure paths in `configuration.toml` instead:

- `W2T_RAW_ROOT`: Override raw data location (default: `/data/raw`)
- `W2T_INTERMEDIATE_ROOT`: Override intermediate data location (default: `/data/interim`)
- `W2T_OUTPUT_ROOT`: Override output location (default: `/output`)
- `W2T_MODELS_ROOT`: Override models location (default: `/models`)
- `W2T_ROOT_METADATA`: Override global metadata file (default: `/configs/metadata.toml`)

**Note**: These overrides currently only work when NOT using `W2T_RUNTIME_CONFIG_JSON` (i.e., in legacy/local dev mode). In production deployments, paths are baked into the config JSON.

### Resource Limits (For Container-based Workers)

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

### Production (Docker Workers)

You can start workers either via the w2t-bkin CLI wrapper (recommended for consistency) or by calling Prefect directly.

#### Method 1: Docker workers via `w2t-bkin`

```bash
# Start Prefect server
w2t-bkin server start

# In another terminal, use the worker environment
w2t-bkin worker start --pool docker-pool --type docker
```

#### Method 2: Local process workers (requires `pip install w2t-bkin[worker]`)

```bash
# Start Prefect server
w2t-bkin server start

# In another terminal, start process workers
w2t-bkin worker start --pool default-pool --type process --limit 4
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
