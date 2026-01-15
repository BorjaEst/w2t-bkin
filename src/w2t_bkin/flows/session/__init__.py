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

from contextlib import contextmanager
from datetime import datetime
import logging
from pathlib import Path

from prefect import flow, get_run_logger
from prefect.runtime import flow_run as flow_run_runtime

from w2t_bkin import tasks, utils
from w2t_bkin.config import SessionFlowConfig
from w2t_bkin.flows.session import artifacts, ingestion, logging, sync
from w2t_bkin.models import SessionInfo, SessionResult

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
        with flow_run_file_logger(session_info.output_dir, run_logger):
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


def _execute_session_pipeline(subject_id: str, session_id: str, session_info: SessionInfo, start_time, run_logger) -> SessionResult:
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

    if discovery.    


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
    pose_plan: artifacts.PosePlan = artifacts.resolve_pose_plan(session_info, run_logger)
    run_logger.info(f"Pose plan: DLC={pose_plan.should_generate_dlc}, SLEAP={pose_plan.should_generate_sleap}")

    if pose_plan.should_generate_dlc:
        tasks.validate_dlc_generate_mode(session_info)
        force_rerun = session_info.config.preprocessing.force_rerun
        run_logger.info(f"{'⚠️  Regenerating' if force_rerun else 'Using cached'} DLC poses")
        dlc_artifacts = tasks.generate_dlc_artifacts(session_info, force_rerun)
        run_logger.info(f"Generated DLC artifacts for {len(dlc_artifacts)} cameras")
    elif pose_plan.dlc_mode == "discover":
        dlc_artifacts = tasks.discover_dlc_artifacts(session_info)
        run_logger.info("DLC discover mode: skipping generation (ingestion in Phase 3)")
    else:
        dlc_artifacts = {}
        run_logger.info("DLC disabled")

    if pose_plan.should_generate_sleap:
        tasks.validate_sleap_generate_mode(session_info)
        force_rerun = session_info.config.preprocessing.force_rerun
        run_logger.info(f"{'⚠️  Regenerating' if force_rerun else 'Using cached'} SLEAP poses")
        sleap_artifacts = tasks.generate_sleap_artifacts(session_info, force_rerun)
    elif pose_plan.sleap_mode == "discover":
        sleap_artifacts = tasks.discover_sleap_artifacts(session_info)
        run_logger.info("SLEAP discover mode: skipping generation (ingestion in Phase 3)")
    else:
        sleap_artifacts = {}
        run_logger.info("SLEAP disabled")

    # =====================================================================
    # Phase 3: Ingestion
    # =====================================================================
    run_logger.info("Phase 3: Ingesting data")

    # Ingest Bpod behavioral data
    bpod_data = None
    if session_info.config.bpod.parse and discovery.bpod_files:
        pattern, order, continuous_time = ingestion.resolve_bpod_ingest_params(session_info)
        bpod_data = tasks.ingest_bpod_task(session_info.session_dir, pattern=pattern, order=order, continuous_time=continuous_time)
        run_logger.info(f"Ingested Bpod data: {bpod_data.n_trials} trials")

    # Ingest pose data using the resolved plan for DLC
    pose_ingest = ingestion.resolve_pose_plan(session_info)
    if pose_plan.ingestion_strategy == "none":
        run_logger.info("No pose data to ingest (both DLC and SLEAP disabled)")
        pose_data = {}
    elif pose_plan.ingestion_strategy == "metadata_stem":
        run_logger.info("Ingesting pose data via metadata stem-matching")
        pose_data = tasks.ingest_pose_via_metadata_stem(dlc_artifacts, sleap_artifacts, discovery, session_info)
    elif pose_plan.ingestion_strategy == "artifact_list":
        run_logger.info("Ingesting pose data via artifact list")
        pose_data = tasks.ingest_pose_via_artifact_list(dlc_artifacts, sleap_artifacts, discovery, session_info)

    # Ingest TTL pulses
    ttl_ingestion = ingestion.resolve_ttl_patterns(session_info)
    if ttl_ingestion.has_patterns:
        ttl_data, warnings = tasks.ingest_ttl_task(session_info.session_dir, ttl_ingestion.patterns)
        for warning in warnings:
            run_logger.warning(f"TTL ingestion: {warning}")
        run_logger.info(f"Ingested TTL data for {len(ttl_data)} channels")
    else:
        ttl_data = {}
        run_logger.info("No TTL patterns found in metadata; skipping TTL ingestion")

    # Align trials with TTL
    trial_alignment = ingestion.align_trials_with_ttl(bpod_data, ttl_data, session_info, run_logger)

    # =====================================================================
    # Phase 4: Synchronization
    # =====================================================================
    run_logger.info("Phase 4: Computing synchronization statistics")

    # Align behavioral trials with TTL pulses
    bpod_plan = sync.prepare_bpod_sync_plan(bpod_data, session_info)
    if bpod_plan.requires_alignment:
        run_logger.info("Skipping trial alignment (missing Bpod or TTL data)")
        trial_alignment = None
    elif bpod_plan.no_trial_types:
        run_logger.info("Skipping trial alignment (no trial_type configs in metadata)")
        trial_alignment = None
    else:
        ttl_pulses = {ttl_id: ttl.timestamps for ttl_id, ttl in ttl_data.items()}
        trial_alignment, warnings = tasks.align_trials_task(trial_type_configs, bpod_data.data, ttl_pulses)
        for warning in warnings:
            run_logger.warning(f"Trial alignment: {warning}")
        run_logger.info("Aligned behavioral trials with TTL pulses")

    alignment_stats = sync.compute_sync_stats(trial_alignment, ttl_data, run_logger)

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
    assembly.assemble_pose_data(nwbfile, pose_data, session_info, ttl_data, run_logger)

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


@contextmanager
def flow_run_file_logger(output_dir: Path, run_logger):
    """Context manager for flow-run-isolated file logging.

    Sets up a file handler bound to the current Prefect flow run to prevent
    cross-session contamination in concurrent execution.

    Args:
        output_dir: Directory to write pipeline.log
        run_logger: Prefect flow logger for status messages

    Yields:
        None (side effect: attaches/detaches file handler)
    """
    log_file = output_dir / "pipeline.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    handler_attached = False

    try:
        # Bind handler to current Prefect flow-run context
        flow_run_id = flow_run_runtime.id
        if flow_run_id is None:
            raise RuntimeError("No Prefect flow run context available")

        flow_run_filter = utils.PrefectFlowRunFilter(flow_run_id)
        file_handler.addFilter(flow_run_filter)
        logging.getLogger("w2t_bkin").addHandler(file_handler)
        handler_attached = True
        run_logger.info(f"File logging enabled: {log_file} (bound to flow-run {flow_run_id})")

        yield

    except Exception as e:
        # Skip file logging if no Prefect context isolation available
        run_logger.warning(f"File logging disabled - no Prefect context isolation: {e}")
        if not handler_attached:
            file_handler.close()
        raise

    finally:
        # Clean up file handler to prevent cross-session contamination
        if handler_attached:
            logging.getLogger("w2t_bkin").removeHandler(file_handler)
            file_handler.close()
