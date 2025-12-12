"""Prefect flow orchestration for w2t-bkin pipeline.

This module provides Prefect @flow definitions that orchestrate the atomic tasks
from the tasks module. Flows handle task sequencing, parallel execution, error
handling, and state management.

Flows:
- session_flow.py: Single session processing orchestration
- batch_flow.py: Multi-session parallel batch processing

Note: Flow configuration models are in w2t_bkin.api for clear API/domain separation.
"""

from ..api import BatchFlowConfig, SessionFlowConfig
from .batch import batch_process_flow
from .session import process_session_flow

__all__ = [
    "process_session_flow",
    "batch_process_flow",
    "SessionFlowConfig",
    "BatchFlowConfig",
]
