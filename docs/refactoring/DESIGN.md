# Prefect-Friendly Refactoring - Technical Design

## Current Structure

```
src/w2t_bkin/
├── tasks/                    # ❌ CONFUSING: PipelineTask, not Prefect @task
│   ├── base.py
│   ├── dlc.py
│   └── sleap.py
│
├── orchestration/            # ❌ UNCLEAR: Mixed multiprocessing + Prefect
│   └── flows.py              # 354 lines, multiple concerns
│
├── core/
│   ├── pipeline/
│   │   ├── phases/           # ✅ PERFECT: 7 phase functions
│   │   │   ├── initialization.py      # run_phase_0()
│   │   │   ├── discovery.py           # run_phase_1()
│   │   │   ├── preprocessing.py       # run_phase_2()
│   │   │   ├── ingestion.py           # run_phase_3()
│   │   │   ├── synchronization.py     # run_phase_4()
│   │   │   ├── assembly.py            # run_phase_5()
│   │   │   └── finalization.py        # run_phase_6()
│   │   ├── models.py         # ✅ PipelineContext, RunOptions
│   │   └── pipeline.py       # ✅ SessionPipeline (legacy)
│   ├── session.py
│   └── validate.py
│
├── container/                # ✅ Container runtime (separate from orchestration)
├── processors/               # ✅ Processing modules
├── ingest/                   # ✅ Data ingestion
├── sync/                     # ✅ Synchronization
└── figures/                  # ✅ Visualization
```

## Target Structure

```
src/w2t_bkin/
├── preprocessing/            # ✅ RENAMED: Clear it's not Prefect tasks
│   ├── base.py               # PipelineTask abstract class
│   ├── dlc.py
│   └── sleap.py
│
├── prefect/                  # ✅ RENAMED: All Prefect code here
│   ├── __init__.py           # Public API + compatibility layer
│   ├── flows.py              # Flow definitions only
│   ├── tasks.py              # Phase task wrappers
│   ├── deployments.py        # Declarative deployments
│   └── infrastructure.py     # Work pools, blocks
│
├── core/                     # ✅ UNCHANGED: Pure business logic
│   ├── pipeline/
│   │   ├── phases/           # Phase functions (wrapped by prefect/tasks.py)
│   │   ├── models.py
│   │   └── pipeline.py
│   ├── session.py
│   └── validate.py
│
├── container/                # ✅ UNCHANGED
├── processors/               # ✅ UNCHANGED
├── ingest/                   # ✅ UNCHANGED
├── sync/                     # ✅ UNCHANGED
└── figures/                  # ✅ UNCHANGED
```

## Module Design

### `preprocessing/` (Renamed from `tasks/`)

**Purpose**: Preprocessing task framework for DLC/SLEAP pose estimation

**No changes to logic**, just renamed for clarity.

```python
# preprocessing/base.py
class PipelineTask(ABC):
    """Abstract base for preprocessing tasks (NOT Prefect)."""
    @abstractmethod
    def execute(self, task_config): ...
```

### `prefect/tasks.py` (NEW)

**Purpose**: Prefect `@task` wrappers for pipeline phases

**Key Design**: Thin wrappers around existing phase functions

```python
from prefect import task
from ..core.pipeline.phases import (
    run_phase_0, run_phase_1, run_phase_2, run_phase_3,
    run_phase_4, run_phase_5, run_phase_6
)
from ..core.pipeline.models import PipelineContext

@task(
    name="phase-0-initialization",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "initialization"],
)
def initialization_task(context: PipelineContext) -> PipelineContext:
    """Phase 0: Load configuration and create NWBFile.

    Retry Logic: 1 retry (config loading failures usually transient)
    """
    run_phase_0(context)
    return context

@task(
    name="phase-1-discovery",
    retries=2,
    retry_delay_seconds=15,
    tags=["pipeline", "discovery"],
)
def discovery_task(context: PipelineContext) -> PipelineContext:
    """Phase 1: Discover cameras, TTLs, and Bpod data.

    Retry Logic: 2 retries (file system operations)
    """
    run_phase_1(context)
    return context

@task(
    name="phase-2-preprocessing",
    retries=2,
    retry_delay_seconds=30,
    tags=["pipeline", "preprocessing", "pose"],
)
def preprocessing_task(context: PipelineContext) -> PipelineContext:
    """Phase 2: Run DLC/SLEAP pose estimation.

    Retry Logic: 2 retries, longer delay (GPU operations)
    """
    run_phase_2(context)
    return context

@task(
    name="phase-3-ingestion",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "ingestion"],
)
def ingestion_task(context: PipelineContext) -> PipelineContext:
    """Phase 3: Ingest Bpod, pose, and TTL data into NWB."""
    run_phase_3(context)
    return context

@task(
    name="phase-4-synchronization",
    retries=2,
    retry_delay_seconds=20,
    tags=["pipeline", "sync"],
)
def synchronization_task(context: PipelineContext) -> PipelineContext:
    """Phase 4: Align timebases and synchronize data streams."""
    run_phase_4(context)
    return context

@task(
    name="phase-5-assembly",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "assembly"],
)
def assembly_task(context: PipelineContext) -> PipelineContext:
    """Phase 5: Assemble behavior and pose data."""
    run_phase_5(context)
    return context

@task(
    name="phase-6-finalization",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "finalization", "nwb"],
)
def finalization_task(context: PipelineContext) -> PipelineContext:
    """Phase 6: Write NWB file, sidecars, and validate."""
    run_phase_6(context)
    return context

# Helper task for session processing (monolithic)
@task(
    name="process-session-monolithic",
    retries=2,
    retry_delay_seconds=60,
    tags=["pipeline", "session", "monolithic"],
)
def process_session_monolithic_task(
    config_path: str,
    subject_id: str,
    session_id: str,
) -> dict:
    """Process entire session as one task (existing behavior)."""
    from ..core.pipeline import SessionPipeline
    from ..core.pipeline.models import RunOptions
    from pathlib import Path

    pipeline = SessionPipeline(
        config_path=Path(config_path),
        subject_id=subject_id,
        session_id=session_id,
        options=RunOptions(),
    )
    pipeline.run()

    return {
        "success": True,
        "subject_id": subject_id,
        "session_id": session_id,
    }
```

### `prefect/flows.py` (REFACTORED)

**Purpose**: Flow definitions using task building blocks

```python
from pathlib import Path
from typing import Optional
from prefect import flow
from ..core.pipeline.models import PipelineContext, RunOptions
from ..utils import discover_sessions
from .tasks import (
    initialization_task,
    discovery_task,
    preprocessing_task,
    ingestion_task,
    synchronization_task,
    assembly_task,
    finalization_task,
    process_session_monolithic_task,
)

@flow(
    name="process-session-with-phases",
    log_prints=True,
    description="Process session with phase-level granularity for maximum observability",
)
def process_session_with_phases(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
    options: Optional[RunOptions] = None,
) -> dict:
    """Process a single session with each phase as a separate task.

    Advantages:
    - Phase-level retry logic
    - Detailed observability in Prefect UI
    - Can see which phase failed
    - Per-phase duration tracking

    Disadvantages:
    - Slightly slower (task overhead)
    - More complex execution graph
    """
    if options is None:
        options = RunOptions()

    # Initialize context
    context = PipelineContext(
        config_path=Path(config_path),
        subject_id=subject_id,
        session_id=session_id,
        options=options,
    )

    # Run phases sequentially
    # Context is passed through and updated by each phase
    context = initialization_task(context)
    context = discovery_task(context)
    context = preprocessing_task(context)
    context = ingestion_task(context)
    context = synchronization_task(context)
    context = assembly_task(context)
    context = finalization_task(context)

    return {
        "success": True,
        "subject_id": subject_id,
        "session_id": session_id,
        "phases_completed": 7,
    }

@flow(
    name="process-session-monolithic",
    log_prints=True,
    description="Process session as single task (faster, less observable)",
)
def process_session_monolithic(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
    options: Optional[RunOptions] = None,
) -> dict:
    """Process entire session as one monolithic task.

    Advantages:
    - Faster (no task overhead)
    - Simpler execution graph
    - Current proven behavior

    Disadvantages:
    - Limited observability
    - Can't see which phase failed
    - Less granular retry logic
    """
    return process_session_monolithic_task(
        str(config_path),
        subject_id,
        session_id,
    )

@flow(
    name="batch-process-sessions",
    log_prints=True,
    description="Batch process multiple sessions in parallel",
)
def batch_process_sessions(
    config_path: str | Path,
    subject_filter: Optional[str] = None,
    session_filter: Optional[str] = None,
    max_workers: int = 4,
    use_phases: bool = False,
) -> dict:
    """Batch process multiple subjects/sessions.

    Args:
        config_path: Path to configuration file
        subject_filter: Optional subject ID filter
        session_filter: Optional session ID filter
        max_workers: Concurrency hint (not enforced by Prefect)
        use_phases: Use phase-level tasks (slower, more observable)

    Returns:
        Summary dict with total, successful, failed counts and results
    """
    # Discover sessions
    sessions = discover_sessions(config_path, subject_filter, session_filter)

    if not sessions:
        return {"total": 0, "successful": 0, "failed": 0, "results": []}

    # Choose flow based on granularity preference
    flow_fn = process_session_with_phases if use_phases else process_session_monolithic

    # Submit all sessions as parallel sub-flow runs
    futures = [
        flow_fn.submit(
            config_path=str(config_path),
            subject_id=session["subject"],
            session_id=session["session"],
        )
        for session in sessions
    ]

    # Wait for all to complete and collect results
    results = []
    for future in futures:
        try:
            result = future.result()
            results.append(result)
        except Exception as e:
            # Log error but continue processing other sessions
            results.append({
                "success": False,
                "error": str(e),
            })

    successful = sum(1 for r in results if r.get("success", False))
    failed = len(results) - successful

    return {
        "total": len(sessions),
        "successful": successful,
        "failed": failed,
        "results": results,
        "mode": "phases" if use_phases else "monolithic",
    }
```

### `prefect/deployments.py` (NEW)

**Purpose**: Declarative deployment definitions

```python
from prefect.deployments import Deployment
from .flows import batch_process_sessions

# Production deployment (monolithic, fast)
batch_prod_deployment = Deployment.build_from_flow(
    flow=batch_process_sessions,
    name="batch-processing",
    work_pool_name="docker-pool",
    work_queue_name="default",
    description="Batch process sessions (monolithic mode)",
    tags=["w2t-bkin", "batch", "production", "monolithic"],
    parameters={
        "config_path": "/configs/container.toml",
        "max_workers": 4,
        "use_phases": False,
    },
    version="2.0.0",
)

# Debug deployment (phase-level, observable)
batch_debug_deployment = Deployment.build_from_flow(
    flow=batch_process_sessions,
    name="batch-processing-debug",
    work_pool_name="docker-pool",
    work_queue_name="debug",
    description="Batch process sessions (phase-level mode for debugging)",
    tags=["w2t-bkin", "batch", "debug", "phases"],
    parameters={
        "config_path": "/configs/container.toml",
        "max_workers": 2,
        "use_phases": True,
    },
    version="2.0.0",
)

# Single session deployment (for testing)
from .flows import process_session_with_phases

single_session_deployment = Deployment.build_from_flow(
    flow=process_session_with_phases,
    name="process-single-session",
    work_pool_name="docker-pool",
    work_queue_name="default",
    description="Process single session with phase-level observability",
    tags=["w2t-bkin", "session", "phases"],
    parameters={
        "config_path": "/configs/container.toml",
        "subject_id": "subject-001",
        "session_id": "session_20251201",
    },
    version="2.0.0",
)
```

### `prefect/__init__.py` (PUBLIC API)

**Purpose**: Expose clean API with backward compatibility

```python
"""Prefect orchestration for W2T-BKIN pipeline.

This module provides Prefect-based orchestration with two execution modes:

1. Monolithic (fast, simple):
   - Entire session as one task
   - Current proven behavior
   - Best for production

2. Phase-level (observable, debuggable):
   - Each pipeline phase as separate task
   - Maximum observability in Prefect UI
   - Best for debugging and development
"""

# New preferred API
from .flows import (
    batch_process_sessions,
    process_session_with_phases,
    process_session_monolithic,
)

from .tasks import (
    initialization_task,
    discovery_task,
    preprocessing_task,
    ingestion_task,
    synchronization_task,
    assembly_task,
    finalization_task,
)

# Backward compatibility (deprecated but functional)
# These will be removed in v3.0
batch_process_sessions_prefect = batch_process_sessions
process_single_session = process_session_monolithic_task

__all__ = [
    # Flows (new preferred names)
    "batch_process_sessions",
    "process_session_with_phases",
    "process_session_monolithic",

    # Phase tasks
    "initialization_task",
    "discovery_task",
    "preprocessing_task",
    "ingestion_task",
    "synchronization_task",
    "assembly_task",
    "finalization_task",

    # Deprecated (backward compatibility)
    "batch_process_sessions_prefect",  # Use batch_process_sessions
    "process_single_session",  # Use process_session_monolithic
]

# Deprecation warnings
import warnings

def __getattr__(name):
    if name == "batch_process_sessions_prefect":
        warnings.warn(
            "batch_process_sessions_prefect is deprecated, use batch_process_sessions instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return batch_process_sessions
    elif name == "process_single_session":
        warnings.warn(
            "process_single_session is deprecated, use process_session_monolithic instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return process_session_monolithic_task
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Data Flow

### Monolithic Mode (Current)

```
batch_process_sessions(use_phases=False)
  └─> [parallel] process_session_monolithic()
        └─> process_session_monolithic_task()
              └─> SessionPipeline.run()  # Black box
```

### Phase Mode (New)

```
batch_process_sessions(use_phases=True)
  └─> [parallel] process_session_with_phases()
        ├─> initialization_task()    → run_phase_0()
        ├─> discovery_task()         → run_phase_1()
        ├─> preprocessing_task()     → run_phase_2()
        ├─> ingestion_task()         → run_phase_3()
        ├─> synchronization_task()   → run_phase_4()
        ├─> assembly_task()          → run_phase_5()
        └─> finalization_task()      → run_phase_6()
```

## Prefect UI Benefits

### Monolithic Mode

- 1 task per session
- Simple graph
- Duration: total session time

### Phase Mode

- 7 tasks per session
- Detailed graph showing phase relationships
- Duration: per-phase breakdown
- Logs: organized by phase
- Failures: exact phase identified
- Retries: per-phase configuration

## Performance Considerations

| Aspect                | Monolithic     | Phase-Level                    |
| --------------------- | -------------- | ------------------------------ |
| **Speed**             | Faster         | Slightly slower (~5% overhead) |
| **Observability**     | Limited        | Excellent                      |
| **Debugging**         | Difficult      | Easy                           |
| **Retry Granularity** | Session-level  | Phase-level                    |
| **Prefect Overhead**  | 1 task/session | 7 tasks/session                |
| **Best For**          | Production     | Development/Debug              |

## Migration Strategy

1. **Phase 1**: Rename directories, update imports
2. **Phase 2**: Split flows.py, maintain compatibility
3. **Phase 3**: Add phase tasks, deploy both modes
4. **Phase 4**: Users gradually adopt phase mode for debugging
5. **v3.0**: Consider removing backward compatibility

## Testing Strategy

- Unit tests for each phase task wrapper
- Integration tests for both flow modes
- Verify both modes produce identical NWB output
- Performance comparison tests
- Container deployment tests

## Deployment Strategy

- Keep current deployment (`batch-processing`) using monolithic mode
- Add new deployment (`batch-processing-debug`) using phase mode
- Users choose based on needs
- Document trade-offs in deployment guide
