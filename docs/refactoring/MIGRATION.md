# Migration Guide: Prefect-Friendly Refactoring

## Overview

This guide helps you update your code to use the new Prefect-friendly module structure. The refactoring improves code organization and adds phase-level execution capabilities while maintaining backward compatibility.

**Backward compatibility is maintained in v2.x** - your existing code will continue to work with deprecation warnings.

## Quick Summary

| Change                | Old Path                         | New Path                     |
| --------------------- | -------------------------------- | ---------------------------- |
| Preprocessing tasks   | `w2t_bkin.tasks`                 | `w2t_bkin.preprocessing`     |
| Prefect orchestration | `w2t_bkin.orchestration`         | `w2t_bkin.prefect`           |
| Batch flow name       | `batch_process_sessions_prefect` | `batch_process_sessions`     |
| Session task name     | `process_single_session`         | `process_session_monolithic` |

## Module Renames

### `tasks/` → `preprocessing/`

**Reason**: Avoid confusion with Prefect `@task` decorator

#### Before

```python
from w2t_bkin.tasks import PipelineTask, DLCPoseTask, SLEAPPoseTask

class MyCustomTask(PipelineTask):
    def execute(self, task_config):
        ...
```

#### After

```python
from w2t_bkin.preprocessing import PipelineTask, DLCPoseTask, SLEAPPoseTask

class MyCustomTask(PipelineTask):
    def execute(self, task_config):
        ...
```

### `orchestration/` → `prefect/`

**Reason**: Clear separation of Prefect-specific code

#### Before

```python
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

# Run batch
batch_process_sessions_prefect.deploy(
    name="my-deployment",
    work_pool_name="default",
)
```

#### After

```python
from w2t_bkin.prefect import batch_process_sessions

# Run batch
batch_process_sessions.deploy(
    name="my-deployment",
    work_pool_name="default",
)
```

## API Changes

### Flow Names

#### `batch_process_sessions_prefect` → `batch_process_sessions`

**Before:**

```python
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

result = batch_process_sessions_prefect(
    config_path="config.toml",
    subject_filter="subject-001",
)
```

**After:**

```python
from w2t_bkin.prefect import batch_process_sessions

result = batch_process_sessions(
    config_path="config.toml",
    subject_filter="subject-001",
)
```

#### `process_single_session` → `process_session_monolithic`

**Before:**

```python
from w2t_bkin.orchestration.flows import process_single_session

result = process_single_session(
    config_path="config.toml",
    subject_id="subject-001",
    session_id="session_20251201",
)
```

**After:**

```python
from w2t_bkin.prefect import process_session_monolithic

result = process_session_monolithic(
    config_path="config.toml",
    subject_id="subject-001",
    session_id="session_20251201",
)
```

## New Features

### Phase-Level Execution

The refactoring adds a new execution mode that exposes individual pipeline phases as separate Prefect tasks.

#### Monolithic Mode (Default - Faster)

```python
from w2t_bkin.prefect import batch_process_sessions

# Process sessions with entire pipeline as one task per session
result = batch_process_sessions(
    config_path="config.toml",
    use_phases=False,  # Default
)
```

**Prefect UI shows:**

- 1 task per session
- Fast execution
- Simple graph

#### Phase-Level Mode (New - More Observable)

```python
from w2t_bkin.prefect import batch_process_sessions

# Process sessions with each phase as separate task
result = batch_process_sessions(
    config_path="config.toml",
    use_phases=True,  # New option
)
```

**Prefect UI shows:**

- 7 tasks per session (one per phase)
- Detailed execution graph
- Per-phase duration and logs
- Exact failure point visible

### Direct Phase-Level Flow

```python
from w2t_bkin.prefect import process_session_with_phases

# Process single session with phase-level granularity
result = process_session_with_phases(
    config_path="config.toml",
    subject_id="subject-001",
    session_id="session_20251201",
)
```

**Phases exposed:**

1. Phase 0: Initialization (load config, create NWBFile)
2. Phase 1: Discovery (find cameras, TTLs, Bpod data)
3. Phase 2: Preprocessing (run DLC/SLEAP)
4. Phase 3: Ingestion (load Bpod, pose, TTL data)
5. Phase 4: Synchronization (align timebases)
6. Phase 5: Assembly (assemble behavior and pose)
7. Phase 6: Finalization (write NWB, validate)

### When to Use Each Mode

| Use Case                    | Mode        | Reason                      |
| --------------------------- | ----------- | --------------------------- |
| Production batch processing | Monolithic  | Faster, proven, simpler     |
| Debugging pipeline issues   | Phase-level | See which phase fails       |
| Development                 | Phase-level | Better visibility           |
| Performance-critical        | Monolithic  | Lower overhead (~5% faster) |
| Learning the pipeline       | Phase-level | Educational                 |

## Backward Compatibility

### Automatic Compatibility (v2.x)

The old import paths and names continue to work:

```python
# These still work but emit deprecation warnings:
from w2t_bkin.tasks import DLCPoseTask  # OK, warns
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect  # OK, warns
```

### Deprecation Timeline

- **v2.x**: Old paths work with warnings
- **v3.0**: Old paths removed (planned)

### Suppressing Warnings (Not Recommended)

If you need to suppress deprecation warnings temporarily:

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Your code using old imports
```

**Better approach:** Update your imports now.

## Container Deployments

### Docker Compose

No changes required - the `docker-compose.yml` and container configuration continue to work.

### Deployment Scripts

**Before:**

```python
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

batch_process_sessions_prefect.deploy(
    name="batch-processing",
    work_pool_name="docker-pool",
)
```

**After:**

```python
from w2t_bkin.prefect import batch_process_sessions

# Deploy production version (monolithic)
batch_process_sessions.deploy(
    name="batch-processing",
    work_pool_name="docker-pool",
    parameters={"use_phases": False},
)

# Deploy debug version (phase-level)
batch_process_sessions.deploy(
    name="batch-processing-debug",
    work_pool_name="docker-pool",
    parameters={"use_phases": True},
)
```

### Updated `deploy_flows.py`

The `docker/deploy_flows.py` script has been updated:

```bash
# Deploy using updated script
python docker/deploy_flows.py
```

This now deploys:

1. `batch-processing` (monolithic mode)
2. `batch-processing-debug` (phase-level mode)
3. `process-single-session` (phase-level mode)

## Testing Your Code

### Update Tests

**Before:**

```python
from w2t_bkin.tasks import DLCPoseTask
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

def test_batch_processing():
    result = batch_process_sessions_prefect(...)
    assert result["successful"] > 0
```

**After:**

```python
from w2t_bkin.preprocessing import DLCPoseTask
from w2t_bkin.prefect import batch_process_sessions

def test_batch_processing():
    result = batch_process_sessions(...)
    assert result["successful"] > 0
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Check for deprecation warnings
pytest tests/ -W default::DeprecationWarning

# Test both execution modes
pytest tests/integration/test_execution_modes.py -v
```

## Common Migration Patterns

### Pattern 1: Custom Preprocessing Task

**Before:**

```python
from w2t_bkin.tasks.base import PipelineTask

class MyTask(PipelineTask):
    def execute(self, config):
        # Implementation
        pass
```

**After:**

```python
from w2t_bkin.preprocessing.base import PipelineTask

class MyTask(PipelineTask):
    def execute(self, config):
        # Implementation
        pass
```

### Pattern 2: Batch Processing Script

**Before:**

```python
#!/usr/bin/env python
from pathlib import Path
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

def main():
    batch_process_sessions_prefect(
        config_path=Path("config.toml"),
        subject_filter="SNA-*",
    )

if __name__ == "__main__":
    main()
```

**After:**

```python
#!/usr/bin/env python
from pathlib import Path
from w2t_bkin.prefect import batch_process_sessions

def main():
    batch_process_sessions(
        config_path=Path("config.toml"),
        subject_filter="SNA-*",
        use_phases=False,  # Explicit mode selection
    )

if __name__ == "__main__":
    main()
```

### Pattern 3: Container Deployment

**Before:**

```python
from prefect.deployments import Deployment
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

deployment = Deployment.build_from_flow(
    flow=batch_process_sessions_prefect,
    name="my-deployment",
)
deployment.apply()
```

**After:**

```python
from prefect.deployments import Deployment
from w2t_bkin.prefect import batch_process_sessions

# Option 1: Use monolithic mode (recommended for production)
deployment = Deployment.build_from_flow(
    flow=batch_process_sessions,
    name="my-deployment-prod",
    parameters={"use_phases": False},
)
deployment.apply()

# Option 2: Use phase mode (recommended for debugging)
deployment_debug = Deployment.build_from_flow(
    flow=batch_process_sessions,
    name="my-deployment-debug",
    parameters={"use_phases": True},
)
deployment_debug.apply()
```

## Troubleshooting

### Issue: Import Error After Update

**Error:**

```
ImportError: cannot import name 'batch_process_sessions_prefect' from 'w2t_bkin.prefect'
```

**Solution:**

Update import to new name:

```python
# Old
from w2t_bkin.prefect import batch_process_sessions_prefect

# New
from w2t_bkin.prefect import batch_process_sessions
```

Or use backward compatibility (temporary):

```python
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect
```

### Issue: Deprecation Warnings

**Warning:**

```
DeprecationWarning: batch_process_sessions_prefect is deprecated, use batch_process_sessions instead
```

**Solution:**

This is expected. Update your code to use new names. The old names will be removed in v3.0.

### Issue: Phase Mode Slower Than Expected

**Observation:**

Phase-level mode takes ~10% longer than monolithic mode.

**Explanation:**

This is expected. Phase mode adds Prefect task overhead for better observability. Use monolithic mode for performance-critical production workloads.

### Issue: Container Deployment Not Found

**Error:**

```
Deployment 'batch-processing' not found
```

**Solution:**

Re-deploy using updated script:

```bash
cd /home/borja/w2t-bkin
python docker/deploy_flows.py
```

## Getting Help

### Documentation

- [Refactoring Overview](./OVERVIEW.md)
- [Technical Design](./DESIGN.md)
- [Requirements](./REQUIREMENTS.md)
- [Task Checklist](./TASKS.md)

### Examples

Check updated examples in:

- `examples/bpod_camera_sync.py`
- `examples/pose_camera_nwb.py`
- `docs/quick-start-batch.md`

### Support

- GitHub Issues: Report bugs or ask questions
- Team Slack: Real-time help from maintainers
- Email: Contact project maintainers

## Summary Checklist

Use this checklist to migrate your code:

- [ ] Update `w2t_bkin.tasks` → `w2t_bkin.preprocessing` imports
- [ ] Update `w2t_bkin.orchestration` → `w2t_bkin.prefect` imports
- [ ] Rename `batch_process_sessions_prefect` → `batch_process_sessions`
- [ ] Rename `process_single_session` → `process_session_monolithic`
- [ ] Decide execution mode (`use_phases=False` vs `True`)
- [ ] Update deployment scripts
- [ ] Update tests
- [ ] Run test suite to verify
- [ ] Update documentation/comments
- [ ] Remove deprecation warning suppressions (if any)

## Timeline

- **Now**: v2.x with backward compatibility
- **6 months**: Deprecation warnings increase in visibility
- **12 months**: v3.0 release, old paths removed

**Recommendation:** Migrate as soon as possible to avoid rushing when v3.0 is released.
