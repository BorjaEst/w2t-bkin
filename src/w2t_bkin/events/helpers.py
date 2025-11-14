"""Helper utilities for events module.

Provides low-level utilities for numpy array handling, validation, and sanitization.
These are internal helpers used across the events submodules.
"""

import logging
from pathlib import Path
from typing import Any, List, Union

import numpy as np

from ..utils import is_nan_or_none, sanitize_string, validate_against_whitelist, validate_file_exists, validate_file_size
from .exceptions import BpodValidationError

logger = logging.getLogger(__name__)

# Constants
VALID_OUTCOMES = frozenset(["hit", "miss", "correct_rejection", "false_alarm", "unknown"])
MAX_BPOD_FILE_SIZE_MB = 100


# =============================================================================
# Numpy Array Handling
# =============================================================================


def to_scalar(value: Union[Any, np.ndarray], index: int) -> Any:
    """Safely extract scalar value from numpy array or list.

    Handles both numpy arrays and regular Python lists/tuples.

    Args:
        value: Value to extract from (ndarray, list, tuple, or scalar)
        index: Index to extract

    Returns:
        Scalar value at index

    Raises:
        IndexError: If index is out of bounds
    """
    if isinstance(value, np.ndarray):
        # Handle numpy arrays (including 0-d arrays)
        if value.ndim == 0:
            return value.item()
        return value[index].item() if hasattr(value[index], "item") else value[index]
    elif isinstance(value, (list, tuple)):
        return value[index]
    else:
        # Assume it's already a scalar
        return value


def to_list(value: Union[Any, np.ndarray]) -> List[Any]:
    """Convert numpy array or scalar to Python list.

    Args:
        value: Value to convert (ndarray, list, tuple, or scalar)

    Returns:
        Python list
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, (list, tuple)):
        return list(value)
    else:
        # Scalar value
        return [value]


# =============================================================================
# Validation and Security
# =============================================================================


def validate_bpod_path(path: Path) -> None:
    """Validate Bpod file path for security.

    Args:
        path: Path to Bpod .mat file

    Raises:
        BpodValidationError: If path is invalid or file too large
    """
    # Validate file exists
    validate_file_exists(path, BpodValidationError, "Bpod file not found")

    # Check file extension
    if path.suffix.lower() not in [".mat"]:
        raise BpodValidationError(f"Invalid file extension: {path.suffix}", file_path=str(path))

    # Check file size (prevent memory exhaustion)
    try:
        file_size_mb = validate_file_size(path, max_size_mb=MAX_BPOD_FILE_SIZE_MB)
        logger.debug(f"Validated Bpod file: {path.name} ({file_size_mb:.2f}MB)")
    except ValueError as e:
        # Re-raise as BpodValidationError for consistent error handling
        raise BpodValidationError(str(e), file_path=str(path))


def sanitize_event_type(event_type: str) -> str:
    """Sanitize event type string from external data.

    Removes potentially dangerous characters and limits length.

    Args:
        event_type: Raw event type string from .mat file

    Returns:
        Sanitized event type string
    """
    return sanitize_string(event_type, max_length=100, allowed_pattern="printable", default="unknown_event")


def validate_outcome(outcome: str) -> str:
    """Validate trial outcome against whitelist.

    Args:
        outcome: Inferred outcome string

    Returns:
        Validated outcome (defaults to 'unknown' if invalid)
    """
    return validate_against_whitelist(outcome, VALID_OUTCOMES, default="unknown", warn=True)
