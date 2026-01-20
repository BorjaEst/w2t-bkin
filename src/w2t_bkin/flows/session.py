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
def process_session_flow(subject_id: str, session_id: str, config: SessionConfig) -> SessionResult:
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
        # Phase 0: Initialization
        # =====================================================================
        run_logger.info("Phase 0: Loading session configuration")
        session_info = initialization_tasks.setup_flow_session_task(subject_id, session_id, config)

        # Setup flow-run-isolated file logging
        with flow_run_file_logger(session_info.processed_dir, run_logger):
            return _execute_session_pipeline(session_info, config, run_logger)

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        run_logger.error(f"Session processing failed: {e}", exc_info=True)

        # Write error profile if possible
        if session_info:
            try:
                profile_path = session_info.processed_dir / "pipeline_profile.json"
                utils.write_json({"success": False, "error": str(e), "phases": []}, profile_path)
            except Exception:
                pass  # Ignore errors during error handling

        return SessionResult(
            success=False,
            subject_id=subject_id if session_info is None else session_info.subject_id,
            session_id=session_id if session_info is None else session_info.session_id,
            error=str(e),
            duration_seconds=duration,
        )


def _execute_session_pipeline(info: SessionInfo, config: SessionConfig, run_logger) -> SessionResult:
    """Execute the main session processing pipeline.

    Extracted to keep the flow function clean and allow proper context manager usage.
    """
    start_time = datetime.now()  # Track total duration

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
    # Phase 3: Ingestion and verification
    # =====================================================================
    run_logger.info("Phase 3: Ingesting data")
    data = {}

    # Ingest TTL pulses signals from ttl files
    if config.ingestion.ttl_signals.enable_loading:
        run_logger.info("Ingesting TTL pulse signals")
        data["ttl"] = ttl_data = ingestion_tasks.ingest_ttl_task(discovery, info, config.ingestion)
    else:
        ttl_data = None
        run_logger.info("TTL pulse ingestion skipped (disabled in config)")
    run_logger.debug(f"TTL Data: {ttl_data}")

    # Ingest Cameras (frame data, transcoding, etc.)
    if config.ingestion.video.enable_loading:
        run_logger.info("Ingesting video data")
        data["video"] = video_data = ingestion_tasks.ingest_video_task(discovery, info, config.ingestion, ttl_data)  # Pass ttl_data for validation
    else:
        video_data = None
        run_logger.info("Camera data ingestion skipped (disabled in config)")
    run_logger.debug(f"Video Data: {video_data}")

    # Ingest Bpod data from mat files into dict structure
    if config.ingestion.bpod.enable_loading:
        run_logger.info("Ingesting Bpod data")
        data["bpod"] = bpod_data = ingestion_tasks.ingest_bpod_task(discovery, info, config.ingestion)
    else:
        bpod_data = None
        run_logger.info("Bpod data ingestion skipped (disabled in config)")
    run_logger.debug(f"Bpod Data: {bpod_data}")

    # Ingest pose data using the resolved plan for DLC
    if config.ingestion.pose.enable_loading:
        run_logger.info("Ingesting pose data")
        data["pose"] = pose_data = ingestion_tasks.ingest_pose_task(discovery, artifacts, info, config.ingestion)
    else:
        pose_data = None
        run_logger.info("Pose data ingestion skipped (disabled in config)")
    run_logger.debug(f"Pose Data: {pose_data}")

    # =====================================================================
    # Phase 4: Synchronization
    # =====================================================================
    run_logger.info("Phase 4: Computing synchronization statistics")
    match config.synchronization.strategy:
        case "rate_based" if data.get("ttl") is not None:
            offsets = sync_tasks.compute_rate_based_offsets_task(data, config.synchronization)
            logger.info("Generated pose artifacts")
        case "hardware_pulse" if data.get("ttl") is not None:
            offsets = sync_tasks.compute_hardware_pulse_offsets_task(data, config.synchronization)
            logger.info("Discovered existing pose artifacts")
        case "network_stream" if data.get("ttl") is not None:
            offsets = sync_tasks.compute_network_stream_offsets_task(data, config.synchronization)
            logger.info("Auto-resolved and processed pose artifacts")
        case _:
            offsets = {}  # No synchronization
            run_logger.info("Synchronization skipped (no TTL data or disabled)")
    logger.debug(f"Computed Offsets: {offsets}")

    # =====================================================================
    # Phase 5: Assembly
    # =====================================================================
    run_logger.info("Phase 5: Assembling NWB data structures")
    nwbfile = assembly_tasks.create_nwb_file_task(info)

    # Assemble TTL data
    if config.assembly.ttls.mode == "skip":
        logger.info("Skipping TTL data assembly into NWB")
    else:
        logger.info("Assembling TTL data into NWB")
        assembly_tasks.assemble_events_table(nwbfile, ttl_data, config.assembly)

    # Assemble Bpod data
    if config.assembly.behavior.mode == "skip":
        logger.info("Skipping Bpod data assembly into NWB")
    else:
        logger.info("Assembling Bpod data into NWB")
        assembly_tasks.assemble_behavior_tables(nwbfile, bpod_data, offsets, config.assembly)

    # Assemble Pose Estimation data
    if config.assembly.pose.mode == "skip":
        logger.info("Skipping pose estimation data assembly into NWB")
    else:
        logger.info("Assembling pose estimation data into NWB")
        assembly_tasks.assemble_pose_estimation(nwbfile, pose_data, video_data, ttl_data, config.assembly)

    # Assemble Video data
    if config.assembly.videos.mode == "skip":
        logger.info("Skipping video data assembly into NWB")
    elif config.assembly.videos.mode == "link":
        logger.info("Assembling linked video data into NWB")
        assembly_tasks.assemble_linked_videos_into_nwb(nwbfile, video_data, config.assembly)
    else:
        logger.info("Assembling video data into NWB")
        assembly_tasks.assemble_videos_into_nwb(nwbfile, video_data, config.assembly)

    logger.debug("NWB assembly completed")

    # =====================================================================
    # Phase 6: Finalization
    # =====================================================================
    run_logger.info("Phase 6: Writing and validating NWB file")

    # Create provenance metadata
    result = finalization_tasks.write_nwb_file_task(nwbfile, info, config.finalization)
    logger.info("NWB file written successfully")

    # Write sidecar files
    if config.finalization.qc_report:
        qc_result = finalization_tasks.write_qc_report_task(info, data, offsets)
        logger.info("Generated QC report sidecar files")
    else:
        qc_result = None
        logger.info("Sidecar file generation skipped (disabled in config)")

    # Generate alignment statistics
    if config.finalization.alignment_stats and offsets and data.get("ttl"):
        alignment_stats = sync_tasks.compute_alignment_stats_task(offsets, data.get("ttl", {}))
        logger.info("Computed alignment statistics for NWB")
    else:
        alignment_stats = None
        logger.info("Alignment statistics generation skipped (disabled in config)")

    # Generate provenance metadata
    if config.finalization.provenance:
        provenance = finalization_tasks.create_provenance_data_task(info, data, config)
        logger.info("Created provenance metadata")
    else:
        provenance = None
        logger.info("Provenance metadata creation skipped (disabled in config)")

    # Validate NWB file
    validation_results = finalization_tasks.validate_nwb_file_task(result.nwb_path, config.finalization.skip_validation)
    logger.info("NWB file validation completed")

    # Build successful result
    return SessionResult(
        success=True,
        subject_id=info.subject_id,
        session_id=info.session_id,
        nwb_path=info.processed_dir / f"{info.session_id}.nwb",
        validation=validation_results,
        duration=(datetime.now() - start_time).total_seconds(),
    )


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
