"""W2T Body Kinematics Pipeline (w2t_bkin).

A modular, reproducible Python pipeline for processing multi-camera rodent
behavior recordings with synchronization, pose estimation, facial metrics,
and behavioral events into standardized NWB datasets.

Architecture: NWB-First
------------------------
This pipeline uses NWB (Neurodata Without Borders) as its foundational data layer.
All processing modules produce NWB-native data structures directly, eliminating
intermediate models and conversion layers.

Modules:
--------
- utils: Shared utilities (hashing, paths, JSON I/O, video analysis, frame counting)
- config: Configuration and session file loading
- session: NWB file creation from session metadata
- sync: Timebase providers and alignment
- behavior: Behavioral task recording (ndx-structured-behavior)
- bpod: Bpod .mat file parsing
- ttl: TTL hardware signals loading and EventsTable extraction (ndx-events)
- transcode: Video transcoding to mezzanine format
- pose: Pose estimation import and harmonization (DLC/SLEAP with ndx-pose)
- facemap: Facial metrics computation and alignment
- pipeline: High-level orchestration (NWB-first workflow)

Pipeline Phases:
----------------
Phase 0 (Foundation): Load config, create NWBFile from metadata.toml
Phase 1 (Discovery): Discover files, verify, add ImageSeries to NWBFile
Phase 2 (Behavior): Parse Bpod, add TaskRecording/TrialsTable to NWBFile
Phase 3 (Sync): Compute alignment stats, select timebase
Phase 4 (Optionals): DLC inference, pose, facemap
Phase 5 (Output): Write NWBFile to disk, validate

Quick Start:
-----------
>>> from w2t_bkin.pipeline import run_session
>>>
>>> # Run complete pipeline (NWB-first)
>>> result = run_session(
...     config_path="config.toml",
...     session_id="Session-000001"
... )
>>>
>>> # Access NWBFile
>>> nwbfile = result['nwbfile']
>>> print(f"Identifier: {nwbfile.identifier}")
>>> print(f"Acquisition: {list(nwbfile.acquisition.keys())}")
>>>
>>> # NWB file written to disk
>>> print(f"Output: {result['nwb_path']}")

Requirements:
-------------
- Python 3.10+
- pynwb~=3.1.0, hdmf~=4.1.0
- ndx-pose~=0.2.0, ndx-structured-behavior~=0.1.0
- scipy, numpy, pydantic

License:
--------
Apache-2.0

Documentation:
--------------
See docs/ for detailed module documentation and design principles.
"""

__version__ = "0.0.11"

__all__ = [
    "behavior",
    "bpod",
    "config",
    "facemap",
    "pose",
    "session",
    "sync",
    "transcode",
    "ttl",
    "utils",
]


def __getattr__(name: str):
    """Lazy-load modules to avoid importing worker dependencies at package import time.

    This defers imports of modules like sync (requires scipy), processors (may import
    heavy dependencies), etc. until they are actually accessed. This keeps the base
    CLI installation lightweight.
    """
    from importlib import import_module
    import sys

    # Submodules - import directly to avoid recursion
    if name == "config":
        import w2t_bkin.config

        return w2t_bkin.config
    elif name == "sync":
        import w2t_bkin.sync

        return w2t_bkin.sync
    elif name == "utils":
        import w2t_bkin.utils

        return w2t_bkin.utils
    elif name == "session":
        from w2t_bkin.core import session

        return session
    elif name == "behavior":
        from w2t_bkin.ingest import behavior

        return behavior
    elif name == "bpod":
        from w2t_bkin.ingest import bpod

        return bpod
    elif name == "pose":
        from w2t_bkin.ingest import pose

        return pose
    elif name == "ttl":
        import w2t_bkin.ttl

        return w2t_bkin.ttl
    elif name == "facemap":
        from w2t_bkin.processors import facemap

        return facemap
    elif name == "transcode":
        from w2t_bkin.processors import transcode

        return transcode

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
