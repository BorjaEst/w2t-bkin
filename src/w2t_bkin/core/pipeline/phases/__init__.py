"""Pipeline phases for W2T Body Kinematics.

This module contains the 7 phases of the pipeline execution:

Phase 0: Initialization - Load config, create NWBFile
Phase 1: Discovery - Discover cameras, TTLs, Bpod data
Phase 2: Preprocessing - Run DLC/SLEAP pose estimation
Phase 3: Ingestion - Ingest Bpod, pose, TTL data
Phase 4: Synchronization - Align timebases
Phase 5: Assembly - Assemble behavior and pose data
Phase 6: Finalization - Write NWB, validate
"""

from .initialization import run_phase_0
from .discovery import run_phase_1
from .preprocessing import run_phase_2
from .ingestion import run_phase_3
from .synchronization import run_phase_4
from .assembly import run_phase_5
from .finalization import run_phase_6

__all__ = [
    "run_phase_0",
    "run_phase_1",
    "run_phase_2",
    "run_phase_3",
    "run_phase_4",
    "run_phase_5",
    "run_phase_6",
]
