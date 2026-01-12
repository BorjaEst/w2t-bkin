# Docker Volume Mounting Implementation Summary

## Problem

Flow runs in Docker containers failed with:

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/borja/w2t-bkin/temp/p2/data/raw'
```

**Root Cause**: Container runtime config used host-absolute paths (`/home/borja/...`) but no Docker volume mounts were configured, so containers couldn't access host directories.

## Solution

Implemented **Prefect-standard Docker volume mounting**:

1. **Work pool configures volume mounts** (infrastructure layer)
2. **Container-native config paths** (application layer)
3. **Automatic setup** via `w2t-bkin server start`

## Changes Made

### 1. Server Configuration (`src/w2t_bkin/cli/server.py`)

**Modified Functions**:

- `_load_and_normalize_config(config_path, for_container=False)`

  - Added `for_container` parameter
  - When `True`: generates container-native paths (`/data/raw`, `/models`, `/output`)
  - When `False`: generates host-absolute paths (for dev mode)

- `_create_work_pool(project_root)`

  - Now takes `project_root` parameter
  - Automatically configures Docker volume mounts in work pool job template:
    - `{project_root}/data:/data:rw`
    - `{project_root}/models:/models:ro`
    - `{project_root}/output:/output:rw`
    - `{project_root}/configuration.toml:/configs/configuration.toml:ro`
  - Uses Prefect CLI to set base job template with volumes

- `_deploy_flows(config_path, project_root)`

  - Calls `_load_and_normalize_config(config_path, for_container=True)`
  - Injects container-native config via `W2T_RUNTIME_CONFIG_JSON`

- `_handle_prod_mode(config_path, project_root)`
  - Passes `project_root` to `_create_work_pool()`

### 2. Worker Environment Template (`templates/.workers.env`)

**Created**: New template file for `.workers/.env` with:

- Documented Docker image configuration (`W2T_DOCKER_IMAGE`)
- Explained automatic volume mounting behavior
- Clarified precedence: `.workers/.env` for infrastructure, `configuration.toml` for pipeline config
- Added optional environment variable overrides (currently not used in production)

### 3. Data Init Command (`src/w2t_bkin/cli/data.py`)

**Modified**: `init()` command to:

- Copy `.workers.env` template to project `.workers/.env`
- Substitute `{project_root}` placeholder
- Remove dependency on non-existent `.workers-README.md` template

### 4. Documentation

**Created**: `docs/user-guide/docker-volumes-and-paths.md`

- Comprehensive guide to volume mounting architecture
- Path resolution flow diagrams
- Common scenarios and troubleshooting
- Best practices

**Updated**: `docker/README.md`

- Added "Data Volume Mounts" section
- Explained automatic volume configuration
- Documented path override environment variables
- Clarified work pool job template behavior

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Host (Project Root: /home/user/experiment)                  │
├─────────────────────────────────────────────────────────────┤
│ configuration.toml:                                         │
│   [paths]                                                   │
│   raw_root = "data/raw"        # Relative paths            │
│   models_root = "models"                                    │
└─────────────────────────────────────────────────────────────┘
                        ↓
        w2t-bkin server start (production mode)
                        ↓
    ┌───────────────────────────────────────────┐
    │ Work Pool: docker-pool                    │
    │ ┌───────────────────────────────────────┐ │
    │ │ Base Job Template:                    │ │
    │ │   volumes:                            │ │
    │ │     - /home/user/experiment/data:/data│ │
    │ │     - /home/user/experiment/models:   │ │
    │ │       /models                         │ │
    │ │     - /home/user/experiment/output:   │ │
    │ │       /output                         │ │
    │ └───────────────────────────────────────┘ │
    └───────────────────────────────────────────┘
                        ↓
    ┌───────────────────────────────────────────┐
    │ Deployment Config (W2T_RUNTIME_CONFIG_JSON)│
    │ {                                         │
    │   "paths": {                              │
    │     "raw_root": "/data/raw",              │
    │     "intermediate_root": "/data/interim", │
    │     "output_root": "/output",             │
    │     "models_root": "/models"              │
    │   }                                       │
    │ }                                         │
    └───────────────────────────────────────────┘
                        ↓
              Flow Run Container
    ┌───────────────────────────────────────────┐
    │ Container Filesystem:                     │
    │   /data/raw         → (mounted from host) │
    │   /data/interim     → (mounted from host) │
    │   /output           → (mounted from host) │
    │   /models           → (mounted from host) │
    │                                           │
    │ Flow reads from /data/raw ✓               │
    │ Flow writes to /output ✓                  │
    └───────────────────────────────────────────┘
```

## Testing Steps

To verify the implementation:

1. **Create/update a test project**:

   ```bash
   cd /home/borja/w2t-bkin/temp/p2
   w2t-bkin data init . --lab "Test Lab" --institution "Test" --experimenters "Test" -y
   ```

2. **Verify `.workers/.env` was created**:

   ```bash
   cat .workers/.env
   # Should contain W2T_DOCKER_IMAGE=w2t-bkin:local
   ```

3. **Start server in production mode**:

   ```bash
   w2t-bkin server start
   # Should create docker-pool with volume mounts
   ```

4. **Inspect work pool configuration**:

   ```bash
   prefect work-pool inspect docker-pool
   # Look for "volumes" in job_configuration
   ```

5. **Start worker**:

   ```bash
   # In new terminal
   cd /home/borja/w2t-bkin/temp/p2
   w2t-bkin worker start --pool docker-pool --type docker
   ```

6. **Trigger a flow run** (via Prefect UI) and verify:
   - Container starts successfully
   - No `FileNotFoundError` for `/home/borja/...` paths
   - Flow can read from `/data/raw` and write to `/output`
   - Host files appear in `temp/p2/output/`

## Key Benefits

1. **Prefect-Standard**: Uses work pool job templates (recommended approach)
2. **Automatic**: No manual `docker run -v` commands needed
3. **Portable**: Container-native paths work across environments
4. **Clean Separation**: Infrastructure (work pool) vs application (config) concerns
5. **User-Friendly**: `w2t-bkin server start` handles everything

## Migration Notes

Existing users need to:

1. **Delete old work pool** (if it exists without volumes):

   ```bash
   prefect work-pool delete docker-pool
   ```

2. **Restart server** to recreate pool with volume mounts:

   ```bash
   w2t-bkin server start
   ```

3. **Verify mounts** before running flows:
   ```bash
   prefect work-pool inspect docker-pool | grep -A 10 volumes
   ```

No code changes required in user projects - the system handles path conversion automatically.

## Future Enhancements

Potential improvements (not currently implemented):

1. **Environment variable path overrides** in production mode

   - Merge `W2T_RAW_ROOT` etc. into runtime config
   - Requires updating `operations/config_loader.py`

2. **Per-deployment volume customization**

   - Allow custom volumes via deployment parameters
   - Useful for experiments with non-standard layouts

3. **Validation checks**

   - Pre-flight check that required host directories exist
   - Warn if volume mounts don't match config paths

4. **Work pool update detection**
   - Auto-update job template if project root changes
   - Currently requires manual pool deletion/recreation
