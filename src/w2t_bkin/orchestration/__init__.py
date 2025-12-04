"""Prefect orchestration for batch processing.

This module provides Prefect-based batch processing capabilities for the
W2T Body Kinematics Pipeline. It wraps the existing SessionPipeline with
Prefect flows and tasks to enable:

- Automatic retry logic with configurable delays
- Real-time observability via Prefect UI dashboard
- Intelligent resource management and concurrency control
- Distributed execution (ready for HPC/Kubernetes)
- Structured logging and error tracking

Key Components:
---------------
- process_single_session: Prefect task for single session processing
- batch_process_sessions: Prefect flow for batch orchestration

Example:
--------
>>> from w2t_bkin.orchestration import batch_process_sessions
>>>
>>> # Process all sessions with 4 parallel workers
>>> result = batch_process_sessions("config.toml", max_workers=4)
>>> print(f"Completed {result['successful']}/{result['total']} sessions")
>>>
>>> # With filters
>>> result = batch_process_sessions(
...     "config.toml",
...     subject_filter="subject-001",
...     max_workers=2,
... )

CLI Usage:
----------
$ python -m w2t_bkin.cli batch config.toml --max-workers 4
$ python -m w2t_bkin.cli batch config.toml --subject subject-001

With Prefect UI (recommended):
$ prefect server start  # Terminal 1
$ python -m w2t_bkin.cli batch config.toml  # Terminal 2
# Open http://localhost:4200 for dashboard

See Also:
---------
- docs/batch-processing.md: Comprehensive batch processing guide
- Prefect docs: https://docs.prefect.io/
"""

from .flows import batch_process_sessions, process_single_session

__all__ = ["batch_process_sessions", "process_single_session"]
