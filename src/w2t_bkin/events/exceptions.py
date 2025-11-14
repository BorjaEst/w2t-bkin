"""Exception types for events module.

Defines all custom exceptions for Bpod parsing, validation, and event extraction.
"""

# Re-export from domain.exceptions for backward compatibility
from ..domain.exceptions import BpodParseError, BpodValidationError, EventsError

__all__ = [
    "EventsError",
    "BpodParseError",
    "BpodValidationError",
]
