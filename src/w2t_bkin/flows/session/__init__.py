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
    >>> from w2t_bkin.config import SessionConfig
    >>>
    >>> # Typical usage (config loaded from TOML at deployment time)
    >>> config = SessionConfig(...)
    >>> result = process_session_flow(
    ...     subject_dir="subject-001",
    ...     session_dir="session-001",
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

from w2t_bkin import utils
from w2t_bkin.config import SessionConfig
from w2t_bkin.flows.session import artifacts, ingestion, logging, sync
from w2t_bkin.models import SessionInfo, SessionResult
from w2t_bkin.tasks import artifacts as artifacts_tasks
from w2t_bkin.tasks import assembly as assembly_tasks
from w2t_bkin.tasks import discovery as discovery_tasks
from w2t_bkin.tasks import finalization as finalization_tasks
from w2t_bkin.tasks import ingestion as ingestion_tasks
from w2t_bkin.tasks import initialization as initialization_tasks
from w2t_bkin.tasks import sync as sync_tasks

logger = logging.getLogger(__name__)


@flow(
    name="process-session",
    description="Process single session with atomic task orchestration",
    log_prints=True,
    persist_result=True,
)
def process_session_flow(subject_dir: str, session_dir: str, config: SessionConfig) -> SessionResult:
    """Process a single session through the complete w2t-bkin pipeline.

    This flow orchestrates all atomic Prefect tasks to transform raw behavioral
    and pose data into a validated NWB file. Paths come from environment variables.

    Args:
        subject_dir: Subject identifier (e.g., "subject-001")
        session_dir: Session identifier (e.g., "session-001")
        config: Pipeline configuration (baked from configuration.toml at deployment time)

    Returns:
        SessionResult with success status, paths, and metadata
    """
    run_logger = get_run_logger()
    start_time = datetime.now()
    session_info = None

    try:
        run_logger.info(f"Starting session processing: {subject_dir}/{session_dir}")

        # =====================================================================
        # Phase 0: Initialization
        # =====================================================================
        run_logger.info("Phase 0: Loading session configuration")
        session_info = initialization_tasks.setup_flow_session_task(subject_dir, session_dir, config)
        nwbfile = initialization_tasks.create_nwb_file_task(session_info)

        # Setup flow-run-isolated file logging
        with flow_run_file_logger(session_info.processed_dir, run_logger):
            return _execute_session_pipeline(nwbfile, session_info, start_time, run_logger)

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

        return SessionResult(success=False, subject_dir=subject_dir, session_dir=session_dir, error=str(e), duration_seconds=duration)


def _execute_session_pipeline(nwbfile, info: SessionInfo, config: SessionConfig, run_logger) -> SessionResult:
    """Execute the main session processing pipeline.

    Extracted to keep the flow function clean and allow proper context manager usage.
    """

    # =====================================================================
    # Phase 1: Discovery
    # =====================================================================
    run_logger.info("Phase 1: Discovering files")
    discovery = discovery_tasks.discover_all_files_task(info)
    run_logger.info("Discovered files:")  # TODO: log here short summary of discovered files

    # =====================================================================
    # Phase 2: Artifact Generation
    # =====================================================================
    run_logger.info("Phase 2: Resolving pose plan and generating artifacts")
    match config.artifacts.mode:
        case "generate":
            artifacts = artifacts_tasks.generate_artifacts_task(discovery, info, config.artifacts)
            logger.info("Generated pose artifacts")
        case "discover":
            artifacts = artifacts_tasks.discover_artifacts_task(discovery, info)
            logger.info("Discovered existing pose artifacts")
        case "auto":
            artifacts = artifacts_tasks.auto_artifacts_task(discovery, info, config.artifacts)
            logger.info("Auto-resolved and processed pose artifacts")
        case "off":
            artifacts = {}
            logger.info("Pose artifact generation skipped (mode='off')")
        case _:
            raise ValueError(f"Invalid artifacts.mode: {config.artifacts.mode}")
    logger.debug(f"Artifacts: {artifacts}")

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

    if config.discovery.camera_ttl_mismatch.enable:
        run_logger.info("Verifying camera/TTL synchronization")
        discovery_tasks.verify_camera_ttl_sync_task(discovery, config.discovery)
    else:
        run_logger.info("Verification skipped (disabled)")

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
    nwb_path = session_info.output_dir / f"{session_dir}.nwb"
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
        subject_dir=subject_dir,
        session_dir=session_dir,
        nwb_path=nwb_path,
        validation=validation_results,
        artifacts={"dlc": dlc_artifacts or {}, "sleap": sleap_artifacts or {}},
        duration_seconds=duration,
    )

    run_logger.info(f"Session processing complete: {subject_dir}/{session_dir} (duration: {duration:.1f}s)")
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
