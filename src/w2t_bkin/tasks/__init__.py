"""Prefect task wrappers for w2t-bkin pipeline operations.

This module provides atomic Prefect tasks that wrap the pure business logic
functions from the operations module. Each task is fine-grained, cacheable,
and independently executable.

Task Organization:
- config_tasks.py: Configuration and initialization tasks
- discovery_tasks.py: File discovery tasks
- artifact_tasks.py: DLC/SLEAP artifact generation tasks
- ingestion_tasks.py: Data ingestion tasks
- sync_tasks.py: Synchronization tasks
- assembly_tasks.py: NWB assembly tasks
- finalization_tasks.py: NWB writing and validation tasks
"""

from w2t_bkin.tasks.artifacts import discover_sleap_poses_task, generate_dlc_poses_task, generate_dlc_session_task
from w2t_bkin.tasks.assembly import add_skeletons_task, assemble_behavior_task, assemble_pose_task
from w2t_bkin.tasks.discovery import discover_all_files_task, discover_bpod_files_task, discover_camera_files_task, discover_ttl_files_task
from w2t_bkin.tasks.finalization import create_provenance_task, finalize_session_task, generate_figures_task, validate_nwb_task, write_nwb_task, write_sidecars_task
from w2t_bkin.tasks.ingestion import align_trials_task, ingest_bpod_task, ingest_dlc_poses_task, ingest_sleap_poses_task, ingest_ttl_task
from w2t_bkin.tasks.initialization import create_nwb_file_task, load_session_config_task
from w2t_bkin.tasks.synchronization import compute_alignment_stats_task
from w2t_bkin.tasks.verification import verify_session_inputs_task

__all__ = [
    # Config tasks
    "load_session_config_task",
    "create_nwb_file_task",
    # Discovery tasks
    "discover_camera_files_task",
    "discover_bpod_files_task",
    "discover_ttl_files_task",
    "discover_all_files_task",
    # Verification tasks
    "verify_session_inputs_task",
    # Artifact tasks
    "generate_dlc_poses_task",
    "generate_dlc_session_task",
    "discover_sleap_poses_task",
    # Ingestion tasks
    "ingest_bpod_task",
    "ingest_dlc_poses_task",
    "ingest_sleap_poses_task",
    "ingest_ttl_task",
    "align_trials_task",
    # Sync tasks
    "compute_alignment_stats_task",
    # Assembly tasks
    "assemble_behavior_task",
    "assemble_pose_task",
    "add_skeletons_task",
    # Finalization tasks
    "write_nwb_task",
    "write_sidecars_task",
    "validate_nwb_task",
    "create_provenance_task",
    "finalize_session_task",
    # Figure generation
    "generate_figures_task",
]
