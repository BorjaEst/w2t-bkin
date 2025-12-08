"""Backward compatibility layer for w2t_bkin.tasks (renamed to preprocessing).

This module provides backward compatibility for code importing from w2t_bkin.tasks.
All imports are redirected to w2t_bkin.preprocessing with deprecation warnings.

.. deprecated:: 2.0
    Use :mod:`w2t_bkin.preprocessing` instead. This compatibility layer will be
    removed in v3.0.

Examples:
    >>> # Old (deprecated but works with warning)
    >>> from w2t_bkin.tasks import DLCPoseTask

    >>> # New (recommended)
    >>> from w2t_bkin.preprocessing import DLCPoseTask
"""

from typing import Any
import warnings

# Import everything from preprocessing
from ..preprocessing import *  # noqa: F401, F403

# Emit deprecation warning when module is imported
warnings.warn(
    "w2t_bkin.tasks is deprecated and will be removed in v3.0. " "Use w2t_bkin.preprocessing instead.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    """Redirect attribute access to preprocessing module with deprecation warning."""
    from .. import preprocessing

    if hasattr(preprocessing, name):
        warnings.warn(
            f"Importing {name} from w2t_bkin.tasks is deprecated. " f"Use 'from w2t_bkin.preprocessing import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(preprocessing, name)

    raise AttributeError(f"module 'w2t_bkin.tasks' has no attribute '{name}'")


# Expose commonly used items for introspection
__all__ = ["DLCPoseTask", "SLEAPPoseTask", "PipelineTask", "TaskConfig", "TaskStatus"]
