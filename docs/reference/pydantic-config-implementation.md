# Pydantic Configuration System - Implementation Summary

## Overview

Successfully implemented Pydantic-based configuration models for Prefect flows, enabling auto-generated UI forms with validation in Prefect Cloud/Server.

**Implementation Date:** December 11, 2025  
**Status:** ✅ Complete and tested

## What Was Implemented

### 1. Configuration Models (`src/w2t_bkin/flows/config_models.py`)

**SessionFlowConfig:**

- Required: `config_path`, `subject_id`, `session_id`
- Optional: 5 skip flags (bpod, pose, dlc, sleap, nwb_validation)
- Validation: Path must end with `.toml`, IDs match pattern `^[\w\-]+$`

**BatchFlowConfig:**

- Required: `config_path`
- Optional: `subject_filter`, `session_filter`, `max_parallel` (1-16), skip flags
- Validation: Path format, parallel count constraints

### 2. Flow Updates

**Modified Files:**

- `src/w2t_bkin/flows/session.py`: Updated signature to `process_session_flow(config: SessionFlowConfig)`
- `src/w2t_bkin/flows/batch.py`: Updated signature to `batch_process_flow(config: BatchFlowConfig)`
- `src/w2t_bkin/flows/__init__.py`: Export config models

**Key Changes:**

- Replaced individual parameters with single Pydantic model parameter
- Extract values from model at flow start for internal use
- BatchFlowConfig creates SessionFlowConfig for each discovered session

### 3. Deployment Script (`docker/deploy_flows.py`)

**Python API deployment script with 4 pre-configured deployment variants:**

| Deployment                      | Purpose                  | Settings                       |
| ------------------------------- | ------------------------ | ------------------------------ |
| `process-session-standard`      | Normal single session    | All steps enabled              |
| `process-session-quick`         | Fast single session      | `skip_nwb_validation=true`     |
| `batch-process-standard`        | Normal batch (4 workers) | Standard parallelism           |
| `batch-process-high-throughput` | Large batch (16 workers) | Max parallelism, no validation |

**Features:**

- Uses `flow.deploy()` Python API - no YAML needed
- Prefect automatically discovers schemas from Pydantic models
- No manual OpenAPI schema writing (eliminates duplication)
- Parameters validated against Pydantic model automatically
- Command-line options for work pool and Docker image selection

### 4. Documentation (`docs/prefect-ui-configuration.md`)

**Comprehensive guide covering:**

- Configuration model reference
- UI usage instructions
- CLI and Python API examples
- Common workflows
- Validation rules and examples
- Troubleshooting guide
- Custom deployment creation

## Benefits

### For Users

✅ **No more raw JSON**: User-friendly forms in Prefect UI  
✅ **Immediate validation**: Errors caught before execution  
✅ **Guided input**: Field descriptions, examples, and defaults  
✅ **Type safety**: Wrong types rejected automatically  
✅ **Constraints enforced**: Min/max values validated

### For Developers

✅ **Single source of truth**: Pydantic models define structure once  
✅ **Auto-generated schemas**: No manual OpenAPI schema writing  
✅ **IDE support**: Full autocompletion and type hints  
✅ **Easy maintenance**: Update model → UI updates automatically  
✅ **Consistent validation**: Same rules for UI, API, and CLI

## Testing Results

All tests passed successfully:

```
✓ Valid config creation
✓ Constraint validation (max_parallel: 1-16)
✓ Pattern validation (subject_id, session_id)
✓ Path format validation (.toml required)
✓ Schema generation for UI
✓ Model serialization for API
✓ Flow signature compatibility
```

## Usage Examples

### Python API

```python
from w2t_bkin.flows import SessionFlowConfig, process_session_flow

config = SessionFlowConfig(
    config_path="/configs/standard.toml",
    subject_id="subject-001",
    session_id="session-001",
    skip_nwb_validation=True
)
result = process_session_flow(config)
```

### Deployment Script

Deployments are created automatically when the Prefect server container starts.
Default parameters are controlled by environment variables:

```bash
# Configure in docker/.env
DEFAULT_CONFIG_FILE=standard.toml      # Config file in /configs/
DEFAULT_MAX_WORKERS=4                   # Max parallel sessions
DEFAULT_SUBJECT_FILTER=subject-.*       # Optional: filter subjects
DEFAULT_SESSION_FILTER=session-.*       # Optional: filter sessions

# Manual redeployment (if needed)
docker compose exec server python /usr/local/bin/deploy_flows.py
```

### Prefect UI

1. Deploy flows using the deployment script
2. Navigate to deployment in UI
3. Click "Run" → "Custom"
4. Fill form fields with auto-generated validation
5. Click "Run"

### CLI

```bash
prefect deployment run w2t-bkin/process-session-standard \
  --param config='{"config_path": "/configs/standard.toml", "subject_id": "subject-001", "session_id": "session-001"}'
```

## File Changes

**Created:**

- `src/w2t_bkin/flows/config_models.py` (177 lines) - Pydantic models
- `docker/deploy_flows.py` (180 lines) - Containerized Python API deployment script
- `docs/prefect-ui-configuration.md` (400+ lines) - User guide
- `docs/pydantic-config-implementation.md` - Implementation summary

**Modified:**

- `src/w2t_bkin/flows/session.py` - Updated flow signature and imports
- `src/w2t_bkin/flows/batch.py` - Updated flow signature and session config creation
- `src/w2t_bkin/flows/__init__.py` - Export config models
- `docs/README.md` - Added Pydantic configuration documentation links

**Removed:**

- `prefect.yaml` - Replaced with Python API approach (eliminates schema duplication)

## Migration Notes

### Backward Compatibility

⚠️ **Breaking change**: Flow signatures changed from individual parameters to single Pydantic model.

**Before:**

```python
process_session_flow(
    config_path="/configs/standard.toml",
    subject_id="subject-001",
    session_id="session-001",
    skip_bpod=False
)
```

**After:**

```python
config = SessionFlowConfig(
    config_path="/configs/standard.toml",
    subject_id="subject-001",
    session_id="session-001",
    skip_bpod=False
)
process_session_flow(config)
```

### Migration Script

For existing code, wrap parameters in config model:

```python
# Old code
result = process_session_flow(config_path, subject_id, session_id)

# New code
from w2t_bkin.flows import SessionFlowConfig
config = SessionFlowConfig(
    config_path=config_path,
    subject_id=subject_id,
    session_id=session_id
)
result = process_session_flow(config)
```

## Next Steps

### Immediate

1. ✅ Deploy flows: Automatic on container startup (or `docker compose exec server python /usr/local/bin/deploy_flows.py`)
2. ✅ Test UI forms in Prefect dashboard
3. ✅ Verify validation works as expected

### Future Enhancements

- [ ] Add Prefect Blocks for reusable configurations
- [ ] Implement Prefect Variables for environment-specific settings
- [ ] Create configuration presets library
- [ ] Add configuration import/export utilities
- [ ] Implement configuration versioning

## References

- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Prefect Parameters**: https://docs.prefect.io/concepts/deployments/#parameters
- **OpenAPI Schema**: https://spec.openapis.org/oas/v3.0.3
- **Project Documentation**: `docs/prefect-ui-configuration.md`

## Support

For issues or questions:

1. Check validation rules in `docs/prefect-ui-configuration.md`
2. Review Pydantic models in `src/w2t_bkin/flows/config_models.py`
3. Test locally with Python API before deploying
4. Check Prefect server logs for deployment issues
