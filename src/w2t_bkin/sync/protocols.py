"""Protocol definitions for sync module dependencies.

Protocols provide structural subtyping to break circular dependencies
while maintaining type safety. Sync modules use these protocols instead
of importing concrete types from domain.

This allows sync to remain decoupled from domain configuration models.
"""

from typing import Literal, Protocol


class TimebaseConfigProtocol(Protocol):
    """Protocol for timebase configuration access.

    Defines minimal interface needed by sync modules without importing
    from domain.config.TimebaseConfig.

    Attributes:
        mapping: Alignment strategy ("nearest" or "linear")
        jitter_budget_s: Maximum acceptable jitter in seconds
    """

    mapping: Literal["nearest", "linear"]
    jitter_budget_s: float


class BpodTrialTypeProtocol(Protocol):
    """Protocol for Bpod trial type configuration access.

    Defines minimal interface needed by sync.behavior module without
    importing from domain.session.BpodTrialType.

    Attributes:
        trial_type: Trial type identifier
        sync_signal: Bpod state/event name for alignment
        sync_ttl: TTL channel ID for sync pulses
        description: Human-readable description
    """

    trial_type: int
    sync_signal: str
    sync_ttl: str
    description: str
