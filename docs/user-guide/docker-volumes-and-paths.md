# Docker Volumes and Path Configuration

This guide explains how data paths are configured and mounted when running w2t-bkin pipelines in Docker containers via Prefect workers.

## Overview

When you run flows in production mode (Docker workers), the system needs to:

1. **Mount host directories** into flow-run containers (e.g., `/home/user/experiment/data` → `/data`)
2. **Configure runtime paths** in the container to use the mounted locations

W2T-BKIN follows **Prefect's standard Docker worker pattern**:

- **Work Pool Job Template**: Defines volume mounts for all flow runs
- **Container-Native Config**: Runtime config uses fixed container paths (`/data`, `/models`, etc.)
- **Automatic Mounting**: Docker worker applies volume mounts when creating each flow-run container

## Architecture

### Two-Level Configuration System

1. **Infrastructure Config** (`.workers/.env`)

   - Docker image selection (`W2T_DOCKER_IMAGE`)
   - Volume mount configuration (managed via work pool)
   - Worker-level settings

2. **Pipeline Config** (`configuration.toml`)
   - Data processing settings
   - Relative paths (automatically converted for containers)
   - Algorithm parameters

### Path Resolution Flow

```
User Configuration (configuration.toml)
  ↓
  paths.raw_root = "data/raw"         # Relative to project root
  paths.models_root = "models"
  ↓
Server Start (w2t-bkin server start)
  ↓
  [Production Mode]
  ├─ Create docker-pool work pool
  │  └─ Set job template with volumes:
  │     - {project_root}/data:/data
  │     - {project_root}/models:/models
  │     - {project_root}/output:/output
  │
  └─ Deploy flows with container-native config:
     - raw_root = "/data/raw"          # Container path
     - models_root = "/models"
     - output_root = "/output"
     ↓
Worker Starts (w2t-bkin worker start)
  ↓
  Polls docker-pool for work
  ↓
Flow Run Triggered
  ↓
  Worker creates container with:
  - Image: W2T_DOCKER_IMAGE
  - Volumes: (from work pool job template)
    * /home/user/project/data:/data
    * /home/user/project/models:/models
    * /home/user/project/output:/output
  - Env: W2T_RUNTIME_CONFIG_JSON={"paths": {"raw_root": "/data/raw", ...}}
  ↓
Flow Executes in Container
  ↓
  Reads from /data/raw (mounted to host)
  Writes to /output (mounted to host)
```

## Volume Mount Configuration

### Automatic Setup (Recommended)

When you run `w2t-bkin server start` in production mode, the system automatically:

1. **Creates `docker-pool` work pool** (if it doesn't exist)
2. **Configures base job template** with volume mounts derived from project root:

```python
# Automatically configured mounts:
{project_root}/data          → /data          (read-write)
{project_root}/models        → /models        (read-only)
{project_root}/output        → /output        (read-write)
{project_root}/configuration.toml → /configs/configuration.toml (read-only)
```

3. **Generates container-native config** with paths matching container mount points

### Manual Verification

You can verify the work pool configuration:

```bash
# Inspect work pool
prefect work-pool inspect docker-pool

# Look for "job_configuration" → "volumes" in the output
```

### Updating Mounts

To change volume mounts:

**Option 1: Delete and recreate the pool**

```bash
# Delete existing pool
prefect work-pool delete docker-pool

# Restart server (recreates pool with current project paths)
w2t-bkin server start
```

**Option 2: Manually update via Prefect UI**

1. Navigate to `Work Pools` → `docker-pool`
2. Edit the base job template
3. Update the `volumes` field

## Path Precedence

### Configuration Hierarchy

1. **Work Pool Job Template** (highest priority - infrastructure)

   - Volume mounts (`/host/path:/container/path`)
   - Defines what host directories are accessible

2. **W2T_RUNTIME_CONFIG_JSON** (deployment config)

   - Container-native paths (`/data/raw`, `/models`, etc.)
   - Baked at deployment time from `configuration.toml`

3. **Environment Variable Overrides** (lowest priority - not currently supported in production)
   - `W2T_RAW_ROOT`, `W2T_MODELS_ROOT`, etc.
   - Only work in legacy/local dev mode (without `W2T_RUNTIME_CONFIG_JSON`)

### Important Notes

- **`.workers/.env` does NOT override `configuration.toml` paths** - it only configures the Docker image
- **Volume mounts are set at the work pool level**, not per-deployment
- **Container paths are fixed** (`/data`, `/models`, `/output`) to ensure consistency

## Common Scenarios

### Scenario 1: Standard Project Structure

```
/home/user/my-experiment/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── models/
├── output/
├── configuration.toml
└── .workers/
    └── .env
```

**Configuration** (`configuration.toml`):

```toml
[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "output"
models_root = "models"
```

**Result**: Automatic mounting works out-of-the-box. Run `w2t-bkin server start` from `/home/user/my-experiment/`.

### Scenario 2: Custom Data Location

If your data is in a different location (e.g., `/mnt/storage/data`), you have two options:

**Option A: Symlink (recommended)**

```bash
cd /home/user/my-experiment/
ln -s /mnt/storage/data data
```

**Option B: Update work pool job template manually**

Via Prefect UI or CLI, add custom volume mount:

```json
{
  "volumes": [
    "/mnt/storage/data:/data:rw",
    "/home/user/my-experiment/models:/models:ro",
    "/home/user/my-experiment/output:/output:rw"
  ]
}
```

### Scenario 3: Multiple Experiments Sharing Models

If you have shared models across experiments:

**Host Structure**:

```
/data/
├── experiment-1/
│   ├── data/
│   └── output/
├── experiment-2/
│   ├── data/
│   └── output/
└── shared-models/
```

**Setup for experiment-1**:

```bash
cd /data/experiment-1
ln -s /data/shared-models models
w2t-bkin server start
```

The symlink is resolved on the host, so the container mount will correctly point to `/data/shared-models`.

## Troubleshooting

### Error: `FileNotFoundError: [Errno 2] No such file or directory: '/home/user/...`

**Cause**: Container is trying to access host-absolute paths that don't exist inside the container.

**Solution**: Ensure you're running in production mode (not dev mode) so container-native paths are used:

```bash
# NOT: w2t-bkin server start --dev
w2t-bkin server start  # Production mode (uses Docker)
```

### Error: `Permission denied` when writing to `/output`

**Cause**: Container user (UID 1000) doesn't have write access to host directory.

**Solution**: Fix host directory permissions:

```bash
# On host
sudo chown -R 1000:1000 /path/to/experiment/output
# or
chmod -R 777 /path/to/experiment/output  # Less secure but works
```

### Worker can't find data after server restart

**Cause**: Work pool was deleted/recreated without volume mounts.

**Solution**: Verify work pool configuration:

```bash
prefect work-pool inspect docker-pool | grep -A 10 volumes
```

If mounts are missing, delete the pool and restart the server:

```bash
prefect work-pool delete docker-pool
w2t-bkin server start
```

### Containers use old paths after changing project location

**Cause**: Work pool job template still references old project root.

**Solution**: Recreate the work pool as shown above.

## Advanced: Custom Volume Configuration

If you need non-standard volume mounts, you can manually configure them in two ways:

### Method 1: Edit Work Pool Job Template (Recommended)

Via Prefect UI:

1. Navigate to **Work Pools** → **docker-pool**
2. Click **Edit**
3. Find the **Base Job Template** section
4. Add/modify the `volumes` array:

```json
{
  "job_configuration": {
    "volumes": [
      "/custom/host/path:/container/path:rw",
      "/another/path:/other:ro"
    ]
  }
}
```

### Method 2: Per-Deployment Job Variables (Not Recommended)

You can override volumes per deployment, but this requires modifying `src/w2t_bkin/cli/server.py`:

```python
# In _deploy_flows()
common_params = {
    "work_pool_name": "docker-pool",
    "image": docker_image,
    "job_variables": {
        "env": {
            "W2T_RUNTIME_CONFIG_JSON": config_json,
        },
        "volumes": [  # Per-deployment override
            "/custom/path:/data:rw",
        ]
    },
}
```

**Note**: Work pool base template is preferred because it applies to all deployments consistently.

## Best Practices

1. **Use relative paths in `configuration.toml`** - they're automatically converted to container paths
2. **Keep data under project root** - simplifies volume mounting
3. **Use symlinks for shared resources** - cleaner than complex volume configs
4. **Don't hardcode absolute paths** - breaks portability across environments
5. **Test with `w2t-bkin server start` (production)** - not just dev mode
6. **Verify mounts before running flows** - use `prefect work-pool inspect`

## See Also

- [Prefect Docker Workers Documentation](https://docs.prefect.io/latest/concepts/work-pools/#docker-work-pools)
- [Docker Volume Mounts](https://docs.docker.com/storage/volumes/)
- [W2T-BKIN Docker README](../../docker/README.md)
