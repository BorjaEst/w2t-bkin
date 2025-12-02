"""Task framework for pipeline preprocessing and intermediate data management.

This module provides a task-based architecture for managing preprocessing steps
that produce intermediate artifacts (e.g., DLC pose estimation, video transcoding).

Tasks are composable, dependency-aware, and support both automatic generation
and manual user-provided intermediate files.

Public API:
    - PipelineTask: Base class for all preprocessing tasks
    - TaskStatus: Enumeration of task execution states
    - DLCPoseTask: DeepLabCut pose estimation task
"""

from .base import PipelineTask, TaskStatus
from .dlc import DLCPoseTask

__all__ = [
    "PipelineTask",
    "TaskStatus",
    "DLCPoseTask",
]
