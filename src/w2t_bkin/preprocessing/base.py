"""Base classes for pipeline preprocessing tasks.

This module defines the core task abstraction used for managing preprocessing
steps that produce intermediate artifacts.

Tasks follow a common lifecycle:
1. Check if output exists (manual or cached)
2. Validate dependencies and prerequisites
3. Execute (if needed and configured)
4. Verify output

Architecture:
    - PipelineTask: Abstract base class defining task interface
    - TaskStatus: Enumeration of execution states
    - TaskConfig: Configuration data for task execution
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a pipeline task execution."""

    PENDING = "pending"  # Not yet checked
    SKIP = "skip"  # Skipped (disabled or no inputs)
    CACHED = "cached"  # Output exists, using cached version
    REQUIRED = "required"  # Must run (output missing)
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"  # Execution failed


@dataclass
class TaskConfig:
    """Configuration for task execution.

    Attributes:
        enabled: Whether task is enabled in config
        force_rerun: Force regeneration even if output exists
        session_dir: Session raw data directory
        interim_dir: Intermediate data output directory
        metadata: Session metadata dictionary
        config: Full pipeline configuration
    """

    enabled: bool
    force_rerun: bool
    session_dir: Path
    interim_dir: Path
    metadata: Dict[str, Any]
    config: Any  # w2t_bkin.config.Config


class PipelineTask(ABC):
    """Abstract base class for pipeline preprocessing tasks.

    Subclasses must implement:
        - check_dependencies: Verify prerequisites (inputs, models, etc.)
        - check_output: Verify output files exist and are valid
        - execute: Generate output from inputs

    Example:
        >>> class MyTask(PipelineTask):
        ...     def check_dependencies(self, task_config):
        ...         # Check for input files
        ...         return True, None
        ...
        ...     def check_output(self, task_config):
        ...         # Check if output exists
        ...         return output_path.exists()
        ...
        ...     def execute(self, task_config):
        ...         # Generate output
        ...         pass
        >>>
        >>> task = MyTask(name="my_task")
        >>> status, output_files = task.run(task_config)
    """

    def __init__(self, name: str, description: str = ""):
        """Initialize task.

        Args:
            name: Unique task identifier
            description: Human-readable description
        """
        self.name = name
        self.description = description
        self.status = TaskStatus.PENDING
        self.error: Optional[str] = None
        self.output_files: List[Path] = []

    @abstractmethod
    def check_dependencies(self, task_config: TaskConfig) -> tuple[bool, Optional[str]]:
        """Check if task dependencies are satisfied.

        Args:
            task_config: Task configuration

        Returns:
            Tuple of (dependencies_met, error_message)
            If dependencies_met is False, task will be skipped
        """
        pass

    @abstractmethod
    def check_output(self, task_config: TaskConfig) -> bool:
        """Check if valid output already exists.

        Args:
            task_config: Task configuration

        Returns:
            True if output exists and is valid, False otherwise
        """
        pass

    @abstractmethod
    def execute(self, task_config: TaskConfig) -> List[Path]:
        """Execute task to generate output.

        Args:
            task_config: Task configuration

        Returns:
            List of output file paths generated

        Raises:
            Exception: If task execution fails
        """
        pass

    def run(self, task_config: TaskConfig) -> tuple[TaskStatus, List[Path]]:
        """Run task with full lifecycle management.

        Args:
            task_config: Task configuration

        Returns:
            Tuple of (final_status, output_files)
        """
        logger.debug(f"Task '{self.name}': Starting")

        # Check if task is enabled
        if not task_config.enabled:
            self.status = TaskStatus.SKIP
            logger.info(f"Task '{self.name}': Skipped (disabled in config)")
            return self.status, []

        # Check dependencies
        deps_met, error = self.check_dependencies(task_config)
        if not deps_met:
            self.status = TaskStatus.SKIP
            self.error = error
            logger.info(f"Task '{self.name}': Skipped ({error or 'dependencies not met'})")
            return self.status, []

        # Check if output exists
        output_exists = self.check_output(task_config)

        if output_exists and not task_config.force_rerun:
            self.status = TaskStatus.CACHED
            logger.info(f"Task '{self.name}': Using cached output")
            # Try to find output files for reporting
            self.output_files = self._find_output_files(task_config)
            return self.status, self.output_files

        if output_exists and task_config.force_rerun:
            logger.info(f"Task '{self.name}': Forcing rerun (output exists but force_rerun=True)")

        if not output_exists:
            logger.debug(f"Task '{self.name}': Output not found, execution required")

        # Execute task
        try:
            self.status = TaskStatus.RUNNING
            logger.info(f"Task '{self.name}': Executing...")
            self.output_files = self.execute(task_config)
            self.status = TaskStatus.COMPLETED
            logger.info(f"Task '{self.name}': Completed ({len(self.output_files)} files generated)")
            return self.status, self.output_files

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            logger.error(f"Task '{self.name}': Failed - {e}", exc_info=True)
            return self.status, []

    def _find_output_files(self, task_config: TaskConfig) -> List[Path]:
        """Helper to find output files (used when cached).

        Override in subclasses if needed for custom output discovery.

        Args:
            task_config: Task configuration

        Returns:
            List of output file paths
        """
        return []
