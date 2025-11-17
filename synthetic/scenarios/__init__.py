"""Pre-built synthetic data scenarios for common test patterns.

This package provides ready-to-use scenarios for testing different aspects
of the W2T-BKIN pipeline. Each scenario is a pre-configured session generator
that represents a specific test case.

Available Scenarios:
--------------------
- happy_path: Complete session that should pass all validation
- mismatch_counts: Frame/TTL count mismatch beyond tolerance
- jitter_exceeds_budget: TTL jitter exceeds configured budget
- no_ttl: Session without TTL synchronization
- multi_camera: Multiple cameras with different TTL channels

Usage:
------
>>> from pathlib import Path
>>> from synthetic.scenarios import happy_path
>>>
>>> # Generate a happy path session
>>> session = happy_path.make_session(Path("temp/test"))
>>>
>>> # Use in tests
>>> from w2t_bkin.config import load_config, load_session
>>> config = load_config(session.config_path)
>>> session_data = load_session(session.session_path)
"""

__all__ = [
    "happy_path",
    "mismatch_counts",
    "jitter_exceeds_budget",
    "no_ttl",
    "multi_camera",
]
