"""Prefect orchestration for W2T Body Kinematics Pipeline.

This module provides Prefect-based orchestration with two execution modes:

1. Monolithic (fast, simple):
   - Entire session as one task
   - Current proven behavior
   - Best for production

2. Phase-level (observable, debuggable):
   - Each pipeline phase as separate task
   - Maximum observability in Prefect UI
   - Best for debugging and development

Quick Start:
------------
>>> from w2t_bkin.prefect import batch_process_sessions
>>>
>>> # Production (monolithic mode - faster)
>>> batch_process_sessions(
...     config_path="config.toml",
...     subject_filter="SNA-*",
...     use_phases=False,  # Default
... )
>>>
>>> # Debug (phase-level mode - more observable)
>>> batch_process_sessions(
...     config_path="config.toml",
...     subject_filter="SNA-*",
...     use_phases=True,
... )

Available Flows:
----------------
- batch_process_sessions: Batch processing with mode selection
- process_session_with_phases: Single session, phase-level tasks
- process_session_monolithic: Single session, monolithic task

Available Tasks:
----------------
- initialization_task: Phase 0 wrapper
- discovery_task: Phase 1 wrapper
- preprocessing_task: Phase 2 wrapper
- ingestion_task: Phase 3 wrapper
- synchronization_task: Phase 4 wrapper
- assembly_task: Phase 5 wrapper
- finalization_task: Phase 6 wrapper
- process_session_monolithic_task: Monolithic task wrapper
"""

import warnings

from .flows import batch_process_sessions, process_session_monolithic, process_session_with_phases

# Import flows
from .flows import batch_process_sessions_prefect  # Backward compat alias

# Import tasks
from .tasks import assembly_task, discovery_task, finalization_task, ingestion_task, initialization_task, preprocessing_task, process_session_monolithic_task, synchronization_task


# Backward compatibility for old names
def process_single_session(*args, **kwargs):
    """Deprecated: Use process_session_monolithic_task instead.

    .. deprecated:: 2.0
        Use :func:`process_session_monolithic_task` instead.
    """
    warnings.warn(
        "process_single_session is deprecated. " "Use process_session_monolithic_task instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return process_session_monolithic_task(*args, **kwargs)


def __getattr__(name: str):
    """Handle backward compatibility for renamed exports."""
    if name == "batch_process_sessions_prefect":
        warnings.warn(
            "batch_process_sessions_prefect is deprecated. " "Use batch_process_sessions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return batch_process_sessions
    elif name == "process_single_session":
        warnings.warn(
            "process_single_session is deprecated. " "Use process_session_monolithic or process_session_monolithic_task instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return process_session_monolithic_task

    raise AttributeError(f"module 'w2t_bkin.prefect' has no attribute '{name}'")


__all__ = [
    # Flows (new preferred names)
    "batch_process_sessions",
    "process_session_with_phases",
    "process_session_monolithic",
    # Tasks
    "initialization_task",
    "discovery_task",
    "preprocessing_task",
    "ingestion_task",
    "synchronization_task",
    "assembly_task",
    "finalization_task",
    "process_session_monolithic_task",
    # Deprecated (backward compatibility - will be removed in v3.0)
    "batch_process_sessions_prefect",
    "process_single_session",
]
