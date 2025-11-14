"""Synchronization exceptions."""


class SyncError(Exception):
    """Error during synchronization/alignment."""

    pass


class JitterBudgetExceeded(SyncError):
    """Jitter exceeds configured budget."""

    pass
