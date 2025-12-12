# Prefect UI Configuration Guide

This guide explains how to configure and run w2t-bkin pipeline flows using the Prefect UI with structured configuration forms.

## Overview

The w2t-bkin pipeline uses **Pydantic models** for flow configuration, which automatically generate user-friendly forms in the Prefect UI. This eliminates the need to manually write JSON and provides:

- ✅ **Type-safe validation**: Invalid inputs are caught before execution
- ✅ **Auto-complete**: Field descriptions and examples guide you
- ✅ **Default values**: Sensible defaults pre-filled for all optional fields
- ✅ **Constraints**: Min/max values enforced (e.g., max_parallel: 1-16)
- ✅ **Pattern matching**: Subject/session IDs validated with regex

## Configuration Models

### SessionFlowConfig

Used for processing a single experimental session.

**Required Fields:**

- `config_path`: Path to configuration TOML file (e.g., `/configs/standard.toml`)
- `subject_id`: Subject identifier (e.g., `subject-001`)
- `session_id`: Session identifier (e.g., `session-001`)

**Optional Fields (all default to `false`):**

- `skip_bpod`: Skip Bpod behavioral data processing
- `skip_pose`: Skip all pose estimation (DLC + SLEAP)
- `skip_dlc`: Skip DeepLabCut only
- `skip_sleap`: Skip SLEAP only
- `skip_ecephys`: Skip electrophysiology (Neuropixels) processing
- `skip_camera_sync`: Skip camera-TTL frame counting verification (speeds up processing)
- `skip_nwb_validation`: Skip NWB file validation

**Validation Rules:**

- `config_path` must end with `.toml`
- `subject_id` must match pattern: `^[\w\-]+$`
- `session_id` must match pattern: `^[\w\-]+$`

### BatchFlowConfig

Used for parallel processing of multiple sessions.

**Required Fields:**

- `config_path`: Path to configuration TOML file

**Optional Fields:**

- `subject_filter`: Glob pattern for subjects (e.g., `subject-*`, `SNA-*`)
- `session_filter`: Glob pattern for sessions (e.g., `session-00*`)
- `max_parallel`: Concurrent sessions (1-16, default: 4)
- `skip_bpod`: Skip Bpod for all sessions (default: false)
- `skip_pose`: Skip pose estimation for all sessions (default: false)
- `skip_ecephys`: Skip electrophysiology for all sessions (default: false)
- `skip_camera_sync`: Skip camera synchronization verification for all sessions (default: false)
- `skip_nwb_validation`: Skip validation for all sessions (default: false)

**Validation Rules:**

- `config_path` must end with `.toml`
- `max_parallel` must be between 1 and 16

## Using the Prefect UI

### 1. Deploy Flows

Flows are automatically deployed when the Prefect server container starts.
Deployment parameters are controlled by environment variables in `docker/.env`:

```bash
# Environment variables (in docker/.env)
DEFAULT_CONFIG_FILE=standard.toml      # Config file in /configs/
DEFAULT_MAX_WORKERS=4                   # Max parallel sessions
DEFAULT_SUBJECT_FILTER=                 # Optional: regex for subjects
DEFAULT_SESSION_FILTER=                 # Optional: regex for sessions
```

This creates two deployments:

- `process-session`: Single session processing with example defaults
- `batch-processing`: Parallel batch processing with environment-controlled defaults

**Manual Deployment** (if needed):

```bash
# From Docker container
docker compose exec server python /usr/local/bin/deploy_flows.py
```

**Why Python API instead of YAML?** Prefect automatically discovers parameter schemas from your Pydantic models, eliminating manual schema writing and preventing drift between code and configuration.

### 2. Navigate to Deployments

1. Open Prefect UI (http://localhost:4200 for local server)
2. Navigate to **Deployments** in the sidebar
3. Find your deployment (e.g., `w2t-bkin/process-session-standard`)

### 3. Run with Custom Parameters

**Option A: Use UI Form (Recommended)**

1. Click **Run** → **Custom**
2. Fill in the form fields:
   - **Config Path**: `/configs/standard.toml`
   - **Subject ID**: `subject-001`
   - **Session ID**: `session-001`
   - Toggle checkboxes for skip options
3. Click **Run**

The UI will validate inputs before submitting:

- Empty required fields → Error
- Invalid patterns → Error message
- Out-of-range values → Error with allowed range

**Option B: Use JSON (Advanced)**

If you prefer JSON, click "Switch to JSON" and provide:

```json
{
  "config": {
    "config_path": "/configs/standard.toml",
    "subject_id": "subject-001",
    "session_id": "session-001",
    "skip_bpod": false,
    "skip_pose": false,
    "skip_dlc": false,
    "skip_sleap": false,
    "skip_ecephys": false,
    "skip_camera_sync": false,
    "skip_nwb_validation": false
  }
}
```

### 4. Schedule Recurring Runs

Create a schedule for automated processing:

1. In deployment view, click **Add Schedule**
2. Choose schedule type:
   - **Interval**: Run every N hours/days
   - **Cron**: Use cron expression (e.g., `0 2 * * *` for daily at 2 AM)
   - **RRule**: Complex recurrence rules
3. Set parameters using the form
4. Click **Save**

## Programmatic Usage

### Python API

```python
from w2t_bkin.flows import process_session_flow, SessionFlowConfig

# Create config
config = SessionFlowConfig(
    config_path="/configs/standard.toml",
    subject_id="subject-001",
    session_id="session-001",
    skip_nwb_validation=True
)

# Run flow
result = process_session_flow(config)
print(f"Success: {result.success}")
print(f"NWB file: {result.nwb_path}")
```

### Batch Processing

```python
from w2t_bkin.flows import batch_process_flow, BatchFlowConfig

config = BatchFlowConfig(
    config_path="/configs/standard.toml",
    subject_filter="subject-*",
    session_filter="session-00*",
    max_parallel=4,
    skip_nwb_validation=True
)

result = batch_process_flow(config)
print(f"Completed {result.successful}/{result.total} sessions")
```

### Prefect CLI

Run deployments directly from the command line:

```bash
# Run deployment with parameters file
prefect deployment run w2t-bkin/process-session-standard \
  --params-file session-params.json

# Run with inline parameters
prefect deployment run w2t-bkin/batch-process-standard \
  --param config='{"config_path": "/configs/standard.toml", "max_parallel": 8}'
```

**Example params file** (`session-params.json`):

```json
{
  "config": {
    "config_path": "/configs/standard.toml",
    "subject_id": "subject-001",
    "session_id": "session-001"
  }
}
```

### Custom Deployments

Create custom deployments programmatically:

```python
from w2t_bkin.flows import process_session_flow, SessionFlowConfig

# Deploy with custom configuration
process_session_flow.deploy(
    name="my-custom-deployment",
    work_pool_name="my-work-pool",
    image="ghcr.io/myorg/w2t-bkin:custom",
    parameters={
        "config": SessionFlowConfig(
            config_path="/my/custom/config.toml",
            skip_nwb_validation=True
        ).model_dump()
    },
    tags=["custom", "experiment-123"],
    description="Custom deployment for specific experiment",
    version="1.0.0"
)
```

Prefect automatically generates UI forms from the `SessionFlowConfig` Pydantic model!

## Deployment Variants

### Session Processing

| Deployment                 | Use Case          | Pre-configured Settings    |
| -------------------------- | ----------------- | -------------------------- |
| `process-session-standard` | Normal processing | All steps enabled          |
| `process-session-quick`    | Fast turnaround   | `skip_nwb_validation=true` |

### Batch Processing

| Deployment                      | Use Case       | Pre-configured Settings                         |
| ------------------------------- | -------------- | ----------------------------------------------- |
| `batch-process-standard`        | Normal batches | 4 parallel workers                              |
| `batch-process-high-throughput` | Large batches  | 16 parallel workers, `skip_nwb_validation=true` |

## Common Workflows

### Process Single Session

**UI:** Deploy → `process-session-standard` → Run → Fill form

**CLI:**

```bash
prefect deployment run w2t-bkin/process-session-standard \
  --param config='{"config_path": "/configs/standard.toml", "subject_id": "subject-001", "session_id": "session-001"}'
```

### Process All Sessions for Subject

**UI:** Deploy → `batch-process-standard` → Run → Set `subject_filter="subject-001"`

**CLI:**

```bash
prefect deployment run w2t-bkin/batch-process-standard \
  --param config='{"config_path": "/configs/standard.toml", "subject_filter": "subject-001"}'
```

### Process Specific Session Pattern

**UI:** Deploy → `batch-process-standard` → Run → Set `session_filter="session-00*"`

**CLI:**

```bash
prefect deployment run w2t-bkin/batch-process-standard \
  --param config='{"config_path": "/configs/standard.toml", "session_filter": "session-00*", "max_parallel": 8}'
```

### High-Throughput Processing

Use the pre-configured high-throughput deployment:

```bash
prefect deployment run w2t-bkin/batch-process-high-throughput \
  --param config='{"config_path": "/configs/standard.toml"}'
```

This automatically uses 16 parallel workers and disables validation.

## Validation Examples

### Valid Inputs

✅ **Subject IDs:**

- `subject-001`
- `SNA-12345`
- `mouse_2024-01`

✅ **Session IDs:**

- `session-001`
- `2024-01-15`
- `test_session`

✅ **Filters:**

- `subject-*` (all subjects)
- `SNA-*` (subjects starting with SNA)
- `session-00*` (sessions 000-009)

### Invalid Inputs

❌ **Invalid patterns:**

- `subject 001` (contains space)
- `session/001` (contains /)
- `@invalid` (starts with @)

❌ **Out of range:**

- `max_parallel: 0` (minimum is 1)
- `max_parallel: 20` (maximum is 16)

❌ **Wrong format:**

- `config_path: "/configs/config.txt"` (must be .toml)

## Troubleshooting

### "Invalid input" errors in UI

**Cause:** Input doesn't match validation rules

**Solution:** Check:

- Required fields are filled
- IDs match pattern `^[\w\-]+$` (letters, numbers, underscore, dash only)
- `max_parallel` is between 1-16
- `config_path` ends with `.toml`

### "Missing required field" errors

**Cause:** Required fields not provided

**Solution:** Ensure you provide:

- **SessionFlowConfig**: `config_path`, `subject_id`, `session_id`
- **BatchFlowConfig**: `config_path`

### Parameters not showing in UI

**Cause:** Deployment not using `enforce_parameter_schema`

**Solution:** Redeploy with:

```bash
prefect deploy --all
```

Ensure `prefect.yaml` has `enforce_parameter_schema: true`.

## Advanced: Custom Deployments

Create custom deployment variants in `prefect.yaml`:

```yaml
deployments:
  - name: my-custom-deployment
    version: "1.0.0"
    description: "Custom configuration for my specific use case"
    entrypoint: src/w2t_bkin/flows/session.py:process_session_flow
    work_pool:
      name: my-work-pool

    parameters:
      config:
        config_path: "/my/custom/config.toml"
        skip_nwb_validation: true
        # ... other pre-configured values

    parameter_openapi_schema:
      # Copy schema from existing deployment and customize

    enforce_parameter_schema: true
```

Then deploy:

```bash
prefect deploy -n my-custom-deployment
```

## Next Steps

- **Docker Deployment**: See `docs/containerization/deployment-guide.md`
- **Configuration Parameters**: See [configuration-parameters.md](configuration-parameters.md)
- **Batch Processing**: See [../cli/pipeline-commands.md](../cli/pipeline-commands.md) (Batch Processing section)
