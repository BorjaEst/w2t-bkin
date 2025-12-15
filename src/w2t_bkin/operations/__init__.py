"""Domain logic operations for w2t-bkin pipeline.

This module contains atomic business logic functions that are Prefect-compatible
but don't directly use Prefect decorators. These functions represent the core
domain operations of the pipeline.

Design Principles:
- Atomic operations only (no session-level orchestration)
- Can use standard Python libraries (logging, pathlib, etc.)
- Can perform I/O and have side effects
- Cannot import Prefect decorators (@task, @flow)
- Should be independently testable with mocked dependencies

The tasks/ layer wraps these operations with @task decorators to add:
- Retry logic
- Caching
- Prefect observability
- Session-level convenience functions
"""

from w2t_bkin.operations.assembly import add_skeletons_container, assemble_behavior_tables, assemble_pose_estimation
from w2t_bkin.operations.config_loader import create_nwb_file, load_session_config
from w2t_bkin.operations.dlc_generator import discover_dlc_poses, generate_dlc_poses, generate_dlc_poses_for_session
from w2t_bkin.operations.file_discovery import discover_all_files, discover_bpod_files, discover_camera_files, discover_ttl_files
from w2t_bkin.operations.finalization import create_provenance_data, finalize_session, validate_nwb_file, write_nwb_file, write_sidecar_files
from w2t_bkin.operations.ingestion import align_trials_to_ttl, ingest_bpod_data, ingest_dlc_poses, ingest_session_data, ingest_sleap_poses, ingest_ttl_pulses
from w2t_bkin.operations.sleap_generator import discover_sleap_poses, discover_sleap_poses_for_session, generate_sleap_poses
from w2t_bkin.operations.synchronization import compute_alignment_statistics, compute_alignment_statistics_from_result
from w2t_bkin.operations.verification import count_all_camera_frames, count_all_ttl_pulses, verify_camera_ttl_sync, verify_session_inputs

__all__ = [
    # Config operations
    "load_session_config",
    "create_nwb_file",
    # Discovery operations
    "discover_camera_files",
    "discover_bpod_files",
    "discover_ttl_files",
    "discover_all_files",
    # Verification operations
    "count_all_camera_frames",
    "count_all_ttl_pulses",
    "verify_camera_ttl_sync",
    "verify_session_inputs",
    # Artifact generation operations
    "discover_dlc_poses",
    "generate_dlc_poses",
    "generate_dlc_poses_for_session",
    "discover_sleap_poses",
    "discover_sleap_poses_for_session",
    "generate_sleap_poses",
    # Ingestion operations
    "ingest_bpod_data",
    "ingest_dlc_poses",
    "ingest_sleap_poses",
    "ingest_ttl_pulses",
    "align_trials_to_ttl",
    "ingest_session_data",
    # Synchronization operations
    "compute_alignment_statistics",
    "compute_alignment_statistics_from_result",
    # Assembly operations
    "assemble_behavior_tables",
    "assemble_pose_estimation",
    "add_skeletons_container",
    # Finalization operations
    "write_nwb_file",
    "create_provenance_data",
    "write_sidecar_files",
    "validate_nwb_file",
    "finalize_session",
]
