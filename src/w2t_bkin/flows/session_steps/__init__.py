"""Session flow helper modules.

Extracted phase helpers to keep the main session flow thin and readable.
"""

from w2t_bkin.flows.session_steps.ingestion import resolve_bpod_ingest_params, resolve_ttl_patterns
from w2t_bkin.flows.session_steps.logging import flow_run_file_logger
from w2t_bkin.flows.session_steps.pose import assemble_pose_data, ingest_pose_data, process_pose_artifacts, resolve_pose_plan, validate_dlc_generate_mode
from w2t_bkin.flows.session_steps.sync import align_trials_with_ttl, compute_sync_stats

__all__ = [
    # Logging
    "flow_run_file_logger",
    # Ingestion helpers
    "resolve_bpod_ingest_params",
    "resolve_ttl_patterns",
    # Pose helpers
    "validate_dlc_generate_mode",
    "resolve_pose_plan",
    "process_pose_artifacts",
    "ingest_pose_data",
    "assemble_pose_data",
    # Sync helpers
    "align_trials_with_ttl",
    "compute_sync_stats",
]
