"""Prefect flow orchestration for w2t-bkin pipeline.

This module provides Prefect @flow definitions that orchestrate the atomic tasks
from the tasks module. Flows handle task sequencing, parallel execution, error
handling, and state management.

Flows:
- session_flow.py: Single session processing orchestration
- batch_flow.py: Multi-session parallel batch processing

Flow Parameters:
- SessionConfig: Pipeline configuration (from configuration.toml, no paths/project)
- BatchFlowConfig: Batch configuration with SessionConfig + filters

Implementation Note:
    Flow imports are deferred using __getattr__ to prevent importing worker
    dependencies (DeepLabCut, PyTorch, etc.) during CLI initialization.
    This ensures base installation remains lightweight (~30MB) while worker
    extras remain optional for execution environments.
"""

from w2t_bkin.config import BatchFlowConfig, SessionConfig

__all__ = [
    "process_session_flow",
    "batch_process_flow",
    "SessionConfig",
    "BatchFlowConfig",
]


def __getattr__(name: str):
    """Lazy import flows to avoid loading worker dependencies during CLI init.

    This defers the import chain: flows → tasks → operations → processors
    until flows are actually needed (e.g., during deployment or execution).

    Without lazy loading, importing this module would trigger module-level
    imports all the way down to processor modules, even though processors
    themselves use lazy imports for heavy dependencies.

    Args:
        name: Attribute name being accessed

    Returns:
        The requested flow function

    Raises:
        AttributeError: If the requested attribute doesn't exist
    """
    if name == "process_session_flow":
        from w2t_bkin.flows.session import process_session_flow

        return process_session_flow
    elif name == "batch_process_flow":
        from w2t_bkin.flows.batch import batch_process_flow

        return batch_process_flow

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
