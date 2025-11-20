"""Scenario builders for synthetic session fixtures.

Pre-configured test scenarios that wrap synthetic data generators with
specific parameter combinations for common test cases:

- happy_path: Perfect alignment, minimal setup (1 camera, 1 TTL)
- mismatch_counts: Intentional frame/TTL count mismatch for verification tests
- no_ttl: Camera-only with nominal timebase (no TTL files)
- multi_camera: Multiple cameras with individual TTL channels

Each scenario returns a RawSessionBuildResult with paths to generated
config.toml, session.toml, and all raw data files.

Example:
    >>> from synthetic.scenarios import happy_path
    >>> session = happy_path.make_session(root="/tmp/test", n_frames=100)
    >>> print(session.config_path)
    >>> print(session.session_path)
"""

from . import happy_path, mismatch_counts, multi_camera, no_ttl

__all__ = [
    "happy_path",
    "mismatch_counts",
    "no_ttl",
    "multi_camera",
]
