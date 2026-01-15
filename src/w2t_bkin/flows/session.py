"""Session-level flow orchestration for w2t-bkin pipeline.

This module defines the main Prefect flow for processing a single session.
It orchestrates all atomic tasks in the correct sequence, with parallel
execution for camera-level operations and comprehensive error handling.

Architecture:
    Pure functions (operations/) → Atomic tasks (tasks/) → Flow orchestration (here)
    Phase helpers extracted to session_steps/ for clarity and maintainability.

Flow Phases:
    0. Configuration: Load config and create NWB file
    1. Discovery: Find all data files
    2. Artifacts: Generate DLC/SLEAP poses (parallel per camera)
    3. Ingestion: Load Bpod, pose, and TTL data
    4. Synchronization: Compute alignment statistics
    5. Assembly: Build NWB data structures
    6. Finalization: Write, validate, and create sidecars

Example:
    >>> from w2t_bkin.flows import process_session_flow
    >>> from w2t_bkin.config import SessionFlowConfig
    >>>
    >>> # Typical usage (config loaded from TOML at deployment time)
    >>> config = SessionFlowConfig(...)
    >>> result = process_session_flow(
    ...     subject_id="subject-001",
    ...     session_id="session-001",
    ...     config=config
    ... )
    >>> print(f"Success: {result.success}, NWB: {result.nwb_path}")
"""

from datetime import datetime
import logging

from prefect import flow, get_run_logger

from w2t_bkin import tasks, utils
from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.flows import session_steps
from w2t_bkin.models import SessionResult

logger = logging.getLogger(__name__)


@flow(
    name="process-session",
    description="Process single session with atomic task orchestration",
    log_prints=True,
    persist_result=True,
)
def process_session_flow(subject_id: str, session_id: str, config: SessionFlowConfig) -> SessionResult:
    """Process a single session through the complete w2t-bkin pipeline.

    This flow orchestrates all atomic Prefect tasks to transform raw behavioral
    and pose data into a validated NWB file. Paths come from environment variables.

    Args:
        subject_id: Subject identifier (e.g., "subject-001")
        session_id: Session identifier (e.g., "session-001")
        config: Pipeline configuration (baked from configuration.toml at deployment time)

    Returns:
        SessionResult with success status, paths, and metadata
    """
    run_logger = get_run_logger()
    start_time = datetime.now()
    session_info = None

    try:
        run_logger.info(f"Starting session processing: {subject_id}/{session_id}")

        # =====================================================================
        # Phase 0: Configuration
        # =====================================================================
        run_logger.info("Phase 0: Loading session configuration")
        session_info = tasks.setup_flow_session_task(subject_id, session_id, config)

        # Setup flow-run-isolated file logging
        with session_steps.flow_run_file_logger(session_info.output_dir, run_logger):
            return _execute_session_pipeline(subject_id, session_id, session_info, start_time, run_logger)

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        run_logger.error(f"Session processing failed: {e}", exc_info=True)

        # Write error profile if possible
        if session_info:
            try:
                profile_path = session_info.output_dir / "pipeline_profile.json"
                utils.write_json({"success": False, "error": str(e), "phases": []}, profile_path)
            except Exception:
                pass  # Ignore errors during error handling

        return SessionResult(success=False, subject_id=subject_id, session_id=session_id, error=str(e), duration_seconds=duration)


def _execute_session_pipeline(subject_id: str, session_id: str, session_info, start_time, run_logger) -> SessionResult:
    """Execute the main session processing pipeline.

    Extracted to keep the flow function clean and allow proper context manager usage.
    """
    # Create NWB file
    nwbfile = tasks.create_nwb_file_task(session_info)

    # =====================================================================
    # Phase 1: Discovery
    # =====================================================================
    run_logger.info("Phase 1: Discovering files")
    discovery = tasks.discover_all_files_task(session_info)
    run_logger.info(f"Discovered: {len(discovery.camera_files)} cameras, {len(discovery.bpod_files)} bpod files, {len(discovery.ttl_files)} TTL files")

    # Phase 1.5: Verification (Fail-Fast)
    if session_info.config.verification.enabled:
        run_logger.info("Phase 1.5: Verifying session inputs")
        verification_result = tasks.verify_session_inputs_task(discovery, session_info)

        if session_info.config.verification.check_frame_counts:
            total_frames = sum(verification_result.get("frame_counts", {}).values())
            run_logger.info(f"Verified frame counts: {total_frames} total frames")

        if session_info.config.verification.check_sync_mismatch:
            verified_cameras = verification_result.get("verified_cameras", [])
            run_logger.info(f"Verified synchronization for {len(verified_cameras)} cameras")
    else:
        run_logger.info("Verification skipped (disabled in configuration)")

    # =====================================================================
    # Phase 2: Artifact Generation
    # =====================================================================
    run_logger.info("Phase 2: Resolving pose plan and generating artifacts")
    pose_plan = session_steps.resolve_pose_plan(session_info, run_logger)
    dlc_artifacts, sleap_artifacts = session_steps.process_pose_artifacts(pose_plan, session_info, run_logger)

    # =====================================================================
    # Phase 3: Ingestion
    # =====================================================================
    run_logger.info("Phase 3: Ingesting data")

    # Ingest Bpod behavioral data
    bpod_data = None
    if session_info.config.bpod.parse and discovery.bpod_files:
        pattern, order, continuous_time = session_steps.resolve_bpod_ingest_params(session_info)
        bpod_data = tasks.ingest_bpod_task(session_info.session_dir, pattern=pattern, order=order, continuous_time=continuous_time)
        run_logger.info(f"Ingested Bpod data: {bpod_data.n_trials} trials")

    # Ingest pose data using the resolved plan
    pose_data = session_steps.ingest_pose_data(pose_plan, dlc_artifacts, sleap_artifacts, discovery, session_info, run_logger)

    # Ingest TTL pulses
    ttl_data = {}
    if discovery.ttl_files:
        ttl_patterns = session_steps.resolve_ttl_patterns(session_info)
        ttl_data = tasks.ingest_ttl_task(session_dir=session_info.session_dir, ttl_patterns=ttl_patterns)
        run_logger.info(f"Ingested TTL data for {len(ttl_data)} channels")

    # Align trials with TTL
    trial_alignment = session_steps.align_trials_with_ttl(bpod_data, ttl_data, session_info, run_logger)

    # =====================================================================
    # Phase 4: Synchronization
    # =====================================================================
    run_logger.info("Phase 4: Computing synchronization statistics")
    alignment_stats = session_steps.compute_sync_stats(trial_alignment, ttl_data, run_logger)

    # =====================================================================
    # Phase 5: Assembly
    # =====================================================================
    run_logger.info("Phase 5: Assembling NWB data structures")

    # Assemble behavior tables
    if bpod_data:
        trial_offsets = trial_alignment.trial_offsets if trial_alignment else []
        tasks.assemble_behavior_task(nwbfile, bpod_data, trial_offsets)
        run_logger.info("Assembled behavior tables")

    # Assemble pose estimation data
    session_steps.assemble_pose_data(nwbfile, pose_data, session_info, ttl_data, run_logger)

    # =====================================================================
    # Phase 6: Finalization
    # =====================================================================
    run_logger.info("Phase 6: Writing and validating NWB file")

    # Create provenance metadata
    config_dict = {"nwb": session_info.config.nwb.model_dump(mode="json"), "metadata": session_info.metadata}
    provenance = tasks.create_provenance_task(config_dict=config_dict, alignment_stats=alignment_stats, pipeline_version="v2")

    # Write NWB file with provenance
    nwb_path = session_info.output_dir / f"{session_id}.nwb"
    nwb_path = tasks.write_nwb_task(nwbfile=nwbfile, output_path=nwb_path, provenance=provenance)
    run_logger.info(f"Wrote NWB file: {nwb_path}")

    # Write sidecar files
    sidecar_paths = tasks.write_sidecars_task(output_dir=session_info.output_dir, alignment_stats=alignment_stats, provenance=provenance)
    run_logger.info(f"Wrote {len(sidecar_paths)} sidecar files")

    # Validate NWB file
    validation_results = tasks.validate_nwb_task(nwb_path=nwb_path, skip_validation=False)
    run_logger.info(f"NWB validation: {len(validation_results) if validation_results else 0} issues")

    # Generate diagnostic figures
    try:
        pipeline_profile_path = session_info.output_dir / "pipeline_profile.json"
        figure_paths = tasks.generate_figures_task(
            output_dir=session_info.output_dir,
            alignment_stats=alignment_stats,
            trial_alignment=trial_alignment,
            bpod_data=bpod_data,
            ttl_data=ttl_data,
            pose_data=pose_data,
            nwb_path=nwb_path,
            pipeline_profile_path=pipeline_profile_path if pipeline_profile_path.exists() else None,
        )
        run_logger.info(f"Generated {len(figure_paths)} diagnostic figures")
    except Exception as e:
        run_logger.warning(f"Figure generation failed: {e}")

    # Build successful result
    duration = (datetime.now() - start_time).total_seconds()
    result = SessionResult(
        success=True,
        subject_id=subject_id,
        session_id=session_id,
        nwb_path=nwb_path,
        validation=validation_results,
        artifacts={"dlc": dlc_artifacts or {}, "sleap": sleap_artifacts or {}},
        duration_seconds=duration,
    )

    run_logger.info(f"Session processing complete: {subject_id}/{session_id} (duration: {duration:.1f}s)")
    return result
