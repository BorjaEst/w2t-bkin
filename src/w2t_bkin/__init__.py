"""W2T Body Kinematics Pipeline (w2t_bkin).

A modular, reproducible Python pipeline for processing multi-camera rodent
behavior recordings with synchronization, pose estimation, facial metrics,
and behavioral events into standardized NWB datasets.

Modules:
--------
- utils: Shared utilities (hashing, paths, JSON I/O, video analysis)
- domain: Pydantic models for type-safe data contracts
- config: Configuration and session file loading
- ingest: File discovery and manifest building
- sync: Timebase providers and alignment
- events: Bpod .mat file parsing and behavioral data extraction
- transcode: Video transcoding to mezzanine format
- pose: Pose estimation import and harmonization (DLC/SLEAP)
- facemap: Facial metrics computation and alignment
- nwb: NWB file assembly with pynwb

Pipeline Phases:
----------------
Phase 0 (Foundation): utils, domain, config
Phase 1 (Ingest): File discovery and manifest
Phase 2 (Sync): Timebase and alignment
Phase 3 (Optionals): events, transcode, pose, facemap
Phase 4 (Output): nwb assembly
Phase 5 (QC): validation and reporting (planned)

Quick Start:
-----------
>>> from w2t_bkin import config, ingest, nwb
>>>
>>> # Load configuration
>>> cfg = config.load_config("config.toml")
>>> session = config.load_session("Session-000001/session.toml")
>>>
>>> # Build manifest
>>> manifest = ingest.build_and_count_manifest(cfg, session)
>>>
>>> # Assemble NWB
>>> provenance = {"config_hash": "abc123", "software": {"name": "w2t_bkin"}}
>>> nwb_path = nwb.assemble_nwb(manifest, cfg, provenance, output_dir)

Requirements:
-------------
- Python 3.10+
- pynwb, scipy, numpy, pydantic

License:
--------
Apache-2.0

Documentation:
--------------
See docs/modules/ for detailed module documentation.
"""

__version__ = "0.1.0"
__author__ = "Borja Esteban"

# Import main modules for convenient access
from . import config, domain, events, facemap, ingest, nwb, pose, sync, transcode, utils

__all__ = [
    "config",
    "domain",
    "events",
    "facemap",
    "ingest",
    "nwb",
    "pose",
    "sync",
    "transcode",
    "utils",
]
