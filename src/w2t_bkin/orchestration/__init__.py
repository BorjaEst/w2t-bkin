"""Backward compatibility layer for w2t_bkin.orchestration (renamed to prefect).

This module provides backward compatibility for code importing from w2t_bkin.orchestration.
All imports are redirected to w2t_bkin.prefect with deprecation warnings.

.. deprecated:: 2.0
    Use :mod:`w2t_bkin.prefect` instead. This compatibility layer will be
    removed in v3.0.

Examples:
    >>> # Old (deprecated but works with warning)
    >>> from w2t_bkin.orchestration import batch_process_sessions

    >>> # New (recommended)
    >>> from w2t_bkin.prefect import batch_process_sessions
"""

from typing import Any
import warnings

# Import everything from prefect
from ..prefect import *  # noqa: F401, F403

# Emit deprecation warning when module is imported
warnings.warn(
    "w2t_bkin.orchestration is deprecated and will be removed in v3.0. " "Use w2t_bkin.prefect instead.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    """Redirect attribute access to prefect module with deprecation warning."""
    from .. import prefect

    if hasattr(prefect, name):
        warnings.warn(
            f"Importing {name} from w2t_bkin.orchestration is deprecated. " f"Use 'from w2t_bkin.prefect import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(prefect, name)

    raise AttributeError(f"module 'w2t_bkin.orchestration' has no attribute '{name}'")


__all__ = ["batch_process_sessions", "batch_process_sessions_prefect"]
