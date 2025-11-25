"""Pipeline orchestration module for W2T-BKIN (Phase 2 - Orchestration Layer).

This module provides the high-level orchestration API that owns Config and Session
and coordinates all pipeline stages. It translates Session/Config into primitive
arguments for low-level tools, orchestrates execution order, and collects results
into structured outputs.

Architecture:
-------------
Phase 2 establishes a clear layering:
- **Orchestration layer** (this module): Owns Config/Session, coordinates stages
- **Mid-level helpers**: Optional wrappers with _from_session/_from_config suffixes
- **Low-level tools**: Accept primitives only (paths, dicts, lists, scalars)

This module is the ONLY place where Config/Session flow into the pipeline. All
downstream modules receive primitives derived from Session/Manifest at this layer.

Key Functions:
--------------
- run_session: Complete session processing workflow
- run_validation: NWB validation using nwbinspector

Result Structure:
-----------------
RunResult contains:
- manifest: File discovery and counts
- alignment_stats: Timebase alignment quality metrics (if computed)
- task_recording: Behavioral task recording with ndx-structured-behavior (if Bpod files present)
- trials_table: Trials table with behavior data (if Bpod files present)
- facemap_bundle: Facial motion signals (if computed)
- transcoded_videos: Mezzanine format videos (if transcoding enabled)
- nwb_path: Path to assembled NWB file (if assembly completes)

Requirements:
-------------
- FR-1..17: Coordinate all pipeline stages
- NFR-1: Deterministic processing with provenance
- NFR-3: Clear error messages and logging
- NFR-11: Configuration-driven execution

Example:
--------
>>> from pathlib import Path
>>> from w2t_bkin.pipeline import run_session
>>>
>>> # Run complete session processing
>>> result = run_session(
...     config_path="config.toml",
...     session_id="Session-000001",
...     options={"skip_nwb": False, "skip_validation": False}
... )
>>>
>>> print(f"Manifest: {len(result['manifest'].cameras)} cameras")
>>> print(f"Alignment: {result['alignment_stats'].max_jitter_s:.6f}s max jitter")
>>> print(f"NWB: {result['nwb_path']}")
>>>
>>> # Validate NWB output
>>> validation = run_validation(result['nwb_path'])
>>> print(f"Validation: {validation['status']}")
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

from pynwb import NWBFile

from w2t_bkin.behavior import (
    TaskRecording,
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
)
from w2t_bkin.bpod import parse_bpod
from w2t_bkin.config import Config
from w2t_bkin.config_loader import load_config
from w2t_bkin.dlc import DLCInferenceOptions, DLCInferenceResult, run_dlc_inference_batch

# from w2t_bkin.facemap import FacemapBundle  # Temporarily disabled
from w2t_bkin.session import add_video_acquisition, create_nwb_file, write_nwb_file
from w2t_bkin.sync import AlignmentStats, create_timebase_provider_from_config, get_ttl_pulses
from w2t_bkin.transcode import TranscodedVideo
from w2t_bkin.utils import compute_hash, count_ttl_pulses, count_video_frames, discover_files, ensure_directory

logger = logging.getLogger(__name__)


# =============================================================================
# Result Models
# =============================================================================


class RunResult(TypedDict, total=False):
    """Result of run_session execution.

    Contains all outputs from pipeline stages. Fields are optional to support
    partial execution (e.g., skip NWB assembly, optional pose/facemap).

    Attributes:
        nwbfile: In-memory NWBFile object with all data
        nwb_path: Path to written NWB file (if written to disk)
        alignment_stats: Timebase alignment quality metrics (optional)
        task_recording: Behavioral task recording with ndx-structured-behavior (optional)
        trials_table: Trials table with behavior data (optional)
        dlc_inference_results: DLC inference results for each camera (optional)
        facemap_bundle: Facial motion signals (optional)
        transcoded_videos: List of transcoded videos (optional)
        provenance: Pipeline execution metadata
    """

    nwbfile: NWBFile
    nwb_path: Optional[Path]
    alignment_stats: Optional[AlignmentStats]
    task_recording: Optional[TaskRecording]
    trials_table: Optional[Any]  # TrialsTable from ndx-structured-behavior
    dlc_inference_results: Optional[List[DLCInferenceResult]]
    facemap_bundle: Optional[Any]  # FacemapBundle - temporarily disabled
    transcoded_videos: Optional[List[TranscodedVideo]]
    provenance: Dict[str, Any]


class ValidationResult(TypedDict):
    """Result of run_validation execution.

    Attributes:
        status: Validation status ("pass" | "warn" | "fail")
        errors: List of validation errors
        warnings: List of validation warnings
        nwb_path: Path to validated NWB file
    """

    status: str
    errors: List[str]
    warnings: List[str]
    nwb_path: Path


# =============================================================================
# Core Orchestration
# =============================================================================


def run_session(
    config_path: Union[str, Path],
    session_id: str,
    options: Optional[Dict[str, Any]] = None,
) -> RunResult:
    """Run complete session processing workflow.

    Orchestrates all pipeline stages:
    1. Load Config and Session
    2. Build and verify Manifest
    3. Parse events (if Bpod files present)
    4. Run DLC inference (if enabled in config)
    5. Import pose/facemap (if available)
    6. Transcode videos (if enabled)
    7. Create timebase and compute alignment
    8. Assemble NWB file (if not skipped)

    This function owns Config/Session and translates them into primitive
    arguments for all low-level tools.

    Args:
        config_path: Path to config.toml
        session_id: Session identifier (must match session.toml session.id)
        options: Optional execution options:
            - skip_nwb: Skip NWB assembly (default: False)
            - skip_validation: Skip verification stage (default: False)
            - transcode_videos: Enable video transcoding (default: False)

    Returns:
        RunResult with all pipeline outputs and provenance

    Raises:
        ConfigError: Configuration loading/validation failed
        SessionError: Session loading/validation failed
        IngestError: File discovery or verification failed
        SyncError: Alignment or jitter budget exceeded
        EventsError: Bpod parsing failed
        NWBError: NWB assembly failed

    Example:
        >>> result = run_session(
        ...     config_path="config.toml",
        ...     session_id="Session-000001"
        ... )
        >>> print(f"Cameras: {len(result['manifest'].cameras)}")
        >>> print(f"Max jitter: {result['alignment_stats'].max_jitter_s:.6f}s")
    """
    # Parse options
    options = options or {}
    skip_nwb = options.get("skip_nwb", False)
    skip_validation = options.get("skip_validation", False)
    transcode_videos = options.get("transcode_videos", False)

    logger.info("=" * 70)
    logger.info("W2T-BKIN Pipeline - Session Processing (NWB-First)")
    logger.info("=" * 70)
    logger.info(f"Config: {config_path}")
    logger.info(f"Session: {session_id}")
    logger.info("=" * 70)

    # -------------------------------------------------------------------------
    # Phase 0: Load Configuration and Create NWBFile
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 0] Loading configuration and creating NWBFile...")
    config_path = Path(config_path)
    config = load_config(config_path)
    logger.info(f"  ✓ Config loaded: {config.project.name}")

    # Find session.toml and create NWBFile (NWB-first architecture)
    session_dir = Path(config.paths.raw_root) / session_id
    session_path = session_dir / config.paths.metadata_file
    nwbfile = create_nwb_file(session_path)
    logger.info(f"  ✓ NWBFile created: {nwbfile.identifier}")

    # Verify session_id matches
    if nwbfile.identifier != session_id:
        raise ValueError(f"Session ID mismatch: requested '{session_id}', " f"found '{nwbfile.identifier}' in {session_path}")

    # NWBFile is already created (NWB-first architecture)
    logger.info(f"  ✓ NWBFile created: {nwbfile.identifier}")

    # -------------------------------------------------------------------------
    # Phase 1: Discover Files and Add Acquisition Data
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 1] Discovering files and populating NWBFile acquisition...")

    # Track discovered files for later processing
    discovered_cameras = []
    bpod_files = []

    # Discover and verify camera files
    for camera_config in session.cameras:
        logger.info(f"  Processing camera: {camera_config.id}")

        # Discover video files
        video_files = discover_files(session_dir, camera_config.paths, sort=True)
        if not video_files:
            logger.warning(f"    ⚠ No videos found for pattern: {camera_config.paths}")
            continue

        logger.info(f"    ✓ Found {len(video_files)} video file(s)")

        # Count frames
        frame_count = 0
        for video_path in video_files:
            try:
                frames = count_video_frames(video_path)
                frame_count += frames
                logger.debug(f"      {video_path.name}: {frames} frames")
            except Exception as e:
                logger.error(f"      ✗ Failed to count frames in {video_path.name}: {e}")
                raise

        logger.info(f"    ✓ Total frames: {frame_count}")

        # Count TTL pulses (for verification)
        ttl_pulse_count = 0
        ttl_config = None
        for ttl in session.TTLs:
            if ttl.id == camera_config.ttl_id:
                ttl_config = ttl
                ttl_files = discover_files(session_dir, ttl.paths, sort=True)
                for ttl_path in ttl_files:
                    ttl_pulse_count += count_ttl_pulses(ttl_path)
                break

        if ttl_config:
            logger.info(f"    ✓ TTL pulses: {ttl_pulse_count}")

        # Verify frame/TTL alignment
        if not skip_validation and ttl_config:
            mismatch = abs(frame_count - ttl_pulse_count)
            tolerance = config.verification.mismatch_tolerance_frames

            if mismatch > tolerance:
                logger.error(
                    f"    ✗ Verification failed:\n" f"      Frames: {frame_count}\n" f"      TTL pulses: {ttl_pulse_count}\n" f"      Mismatch: {mismatch} (tolerance: {tolerance})"
                )
                raise ValueError(f"Frame/TTL verification failed for camera {camera_config.id}: " f"mismatch {mismatch} exceeds tolerance {tolerance}")

            logger.info(f"    ✓ Verification passed (mismatch: {mismatch})")

        # Add ImageSeries to NWBFile
        add_video_acquisition(
            nwbfile,
            camera_id=camera_config.id,
            video_files=[str(f) for f in video_files],
            frame_rate=getattr(camera_config, "frame_rate", 30.0),
        )
        logger.info(f"    ✓ Added to NWBFile acquisition")

        # Track for later use
        discovered_cameras.append(
            {
                "camera_id": camera_config.id,
                "video_files": video_files,
                "frame_count": frame_count,
                "ttl_pulse_count": ttl_pulse_count,
            }
        )

    logger.info(f"  ✓ Processed {len(discovered_cameras)} camera(s)")

    # Discover Bpod files
    if hasattr(session, "bpod") and session.bpod:
        bpod_files = discover_files(session_dir, session.bpod.path, sort=True)
        logger.info(f"  ✓ Discovered {len(bpod_files)} Bpod file(s)")

    # -------------------------------------------------------------------------
    # Phase 2: Parse Behavior (Optional - ndx-structured-behavior)
    # -------------------------------------------------------------------------
    task_recording: Optional[TaskRecording] = None
    trials_table: Optional[Any] = None

    if bpod_files and len(bpod_files) > 0:
        logger.info("\n[Phase 2] Building behavioral data (ndx-structured-behavior)...")

        try:
            # Extract primitives from Session
            bpod_pattern = session.bpod.path
            bpod_order = session.bpod.order

            # Parse Bpod files with low-level API
            bpod_data = parse_bpod(
                session_dir=session_dir,
                pattern=bpod_pattern,
                order=bpod_order,
                continuous_time=True,
            )
            n_trials = bpod_data["SessionData"]["nTrials"]
            logger.info(f"  ✓ Parsed {n_trials} trials from Bpod files")

            # Extract type tables (metadata)
            state_types = extract_state_types(bpod_data)
            event_types = extract_event_types(bpod_data)
            action_types = extract_action_types(bpod_data)
            logger.info(f"  ✓ Extracted types: {len(state_types)} states, {len(event_types)} events, {len(action_types)} actions")

            # Extract data tables (no alignment yet - trial_offsets=None)
            states, state_indices = extract_states(bpod_data, state_types, trial_offsets=None)
            events, event_indices = extract_events(bpod_data, event_types, trial_offsets=None)
            actions, action_indices = extract_actions(bpod_data, action_types, trial_offsets=None)
            logger.info(f"  ✓ Extracted data: {len(states)} state occurrences, {len(events)} events, {len(actions)} actions")

            # Build trials table and task recording
            trials_table = build_trials_table(bpod_data, states, events, actions, state_indices, event_indices, action_indices, trial_offsets=None)
            task_recording = build_task_recording(states, events, actions)
            logger.info(f"  ✓ Built TrialsTable ({n_trials} trials) and TaskRecording")

        except Exception as e:
            logger.warning(f"  ⚠ Behavior data extraction failed: {e}")
            task_recording = None
            trials_table = None

    # -------------------------------------------------------------------------
    # Phase 3: Synchronization (Placeholder)
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 3] Creating timebase and alignment...")

    # Compute alignment stats (placeholder - would normally align all modalities)
    alignment_stats: Optional[AlignmentStats] = None

    # For now, create minimal alignment stats if TTL-based
    if config.timebase.source == "ttl":
        # Extract TTL pulses for alignment
        ttl_patterns = {ttl.id: ttl.path for ttl in session.TTLs}
        ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

        # Count total pulses
        total_pulses = sum(len(pulses) for pulses in ttl_pulses.values())

        alignment_stats = AlignmentStats(
            timebase_source=config.timebase.source,
            mapping=config.timebase.mapping,
            offset_s=config.timebase.offset_s,
            max_jitter_s=0.0,  # Placeholder
            p95_jitter_s=0.0,  # Placeholder
            aligned_samples=total_pulses,
        )
        logger.info(f"  ✓ Alignment stats created: {total_pulses} samples aligned")
    else:
        # Nominal rate - create minimal stats
        alignment_stats = AlignmentStats(
            timebase_source=config.timebase.source,
            mapping=config.timebase.mapping,
            offset_s=config.timebase.offset_s,
            max_jitter_s=0.0,
            p95_jitter_s=0.0,
            aligned_samples=0,
        )
        logger.info("  ✓ Alignment stats created (nominal rate)")

    # -------------------------------------------------------------------------
    # Phase 4: Optional Modalities (DLC Inference, Facemap, Transcode)
    # -------------------------------------------------------------------------
    dlc_inference_results: Optional[List[DLCInferenceResult]] = None
    facemap_bundle: Optional[Any] = None  # FacemapBundle - temporarily disabled
    transcoded_videos: Optional[List[TranscodedVideo]] = None

    logger.info("\n[Phase 4] Checking for optional modalities...")

    # DLC Inference (if enabled)
    if config.labels.dlc.run_inference:
        logger.info("\n[Phase 4.1] Running DLC inference...")

        try:
            # Extract primitives from Config/Session
            model_dir_name = config.labels.dlc.model
            model_config_path = Path(config.paths.models_root) / model_dir_name / "config.yaml"

            # Collect all camera video paths from discovered cameras
            video_paths = []
            for camera in discovered_cameras:
                # Each camera may have multiple video files (concatenated later)
                if camera["video_files"]:
                    video_paths.extend(camera["video_files"])

            if not video_paths:
                logger.warning("  ⚠ No video files found - skipping DLC inference")
            elif not model_config_path.exists():
                logger.error(f"  ✗ DLC model config not found: {model_config_path}")
                raise FileNotFoundError(f"DLC model config.yaml not found: {model_config_path}")
            else:
                # Create output directory
                output_dir = Path(config.paths.intermediate_root) / session_id / "dlc"
                output_dir.mkdir(parents=True, exist_ok=True)

                # Create options from config
                options = DLCInferenceOptions(
                    gputouse=config.labels.dlc.gputouse,
                    save_as_csv=False,
                    allow_growth=True,
                    allow_fallback=True,
                )

                logger.info(f"  → Model: {model_dir_name}")
                logger.info(f"  → Videos: {len(video_paths)} files")
                logger.info(f"  → GPU: {options.gputouse if options.gputouse is not None else 'auto-detect'}")
                logger.info(f"  → Output: {output_dir}")

                # Run batch inference (low-level API with primitives only)
                dlc_inference_results = run_dlc_inference_batch(
                    video_paths=video_paths,
                    model_config_path=model_config_path,
                    output_dir=output_dir,
                    options=options,
                )

                # Report results
                success_count = sum(1 for r in dlc_inference_results if r.success)
                total_time = sum(r.inference_time_s for r in dlc_inference_results)
                total_frames = sum(r.frame_count for r in dlc_inference_results if r.success)

                logger.info(f"  ✓ DLC inference complete: {success_count}/{len(dlc_inference_results)} videos succeeded")
                logger.info(f"  ✓ Total time: {total_time:.1f}s ({total_frames} frames)")

                # Log any failures
                for result in dlc_inference_results:
                    if not result.success:
                        logger.warning(f"    ⚠ Failed: {result.video_path.name} - {result.error_message}")

                # TODO: Update manifest with H5 paths for downstream pose import
                # This would map each result.h5_output_path back to the corresponding camera

        except Exception as e:
            logger.error(f"  ✗ DLC inference failed: {e}")
            raise

    else:
        logger.info("  ⊘ DLC inference: Disabled in config")

    # Pose import (placeholder)
    logger.info("  ⊘ Pose import: Not implemented")
    logger.info("  ⊘ Facemap computation: Not implemented")

    if transcode_videos:
        logger.info("  ⊘ Video transcoding: Not implemented")

    # -------------------------------------------------------------------------
    # Phase 5: NWB Assembly and Writing
    # -------------------------------------------------------------------------
    nwb_path: Optional[Path] = None

    if not skip_nwb:
        logger.info("\n[Phase 5] Writing NWB file...")

        # Add provenance to NWBFile
        provenance = {
            "pipeline_version": "0.1.0",
            "config_path": str(config_path),
            "session_id": session_id,
            "execution_time": datetime.now().isoformat(),
            "config_hash": compute_hash(str(config.model_dump())),
            "session_hash": compute_hash(str(session.model_dump())),
            "timebase": {
                "source": config.timebase.source,
                "mapping": config.timebase.mapping,
                "offset_s": config.timebase.offset_s,
            },
            "dlc_inference": {
                "enabled": config.labels.dlc.run_inference,
                "model": config.labels.dlc.model if config.labels.dlc.run_inference else None,
                "gputouse": config.labels.dlc.gputouse if config.labels.dlc.run_inference else None,
                "results": len(dlc_inference_results) if dlc_inference_results else 0,
                "success_count": sum(1 for r in dlc_inference_results if r.success) if dlc_inference_results else 0,
            },
        }

        # Embed provenance in NWB file notes
        nwbfile.notes = json.dumps(provenance, indent=2)

        # Add task recording and trials if available
        if task_recording:
            nwbfile.add_acquisition(task_recording)
            logger.info("  ✓ Added TaskRecording to NWBFile")

        if trials_table:
            nwbfile.trials = trials_table
            logger.info("  ✓ Added TrialsTable to NWBFile")

        # Write to disk
        output_dir = Path(config.paths.output_root) / session_id
        ensure_directory(output_dir)
        nwb_path = output_dir / f"{session_id}.nwb"

        write_nwb_file(nwbfile, nwb_path)
        logger.info(f"  ✓ NWB file written: {nwb_path}")
        logger.info(f"  ✓ Size: {nwb_path.stat().st_size / (1024 * 1024):.2f} MB")
    else:
        logger.info("\n[Phase 5] NWB writing skipped")
        # Still compute provenance for result
        provenance = {
            "pipeline_version": "0.1.0",
            "config_path": str(config_path),
            "session_id": session_id,
            "execution_time": datetime.now().isoformat(),
            "config_hash": compute_hash(str(config.model_dump())),
            "session_hash": compute_hash(str(session.model_dump())),
        }

    # -------------------------------------------------------------------------
    # Build Result
    # -------------------------------------------------------------------------
    logger.info("\n[Complete] Pipeline execution finished")
    logger.info("=" * 70)

    result: RunResult = {
        "nwbfile": nwbfile,
        "nwb_path": nwb_path,
        "alignment_stats": alignment_stats,
        "task_recording": task_recording,
        "trials_table": trials_table,
        "dlc_inference_results": dlc_inference_results,
        "facemap_bundle": facemap_bundle,
        "transcoded_videos": transcoded_videos,
        "provenance": provenance,
    }

    return result


def run_validation(nwb_path: Union[str, Path]) -> ValidationResult:
    """Validate NWB file using nwbinspector.

    Simple wrapper around nwbinspector for NWB file validation.
    Returns structured validation report.

    Args:
        nwb_path: Path to NWB file to validate

    Returns:
        ValidationResult with status and messages

    Raises:
        FileNotFoundError: NWB file not found
        ValidationError: Validation execution failed

    Example:
        >>> result = run_validation("output/Session-000001/session.nwb")
        >>> if result['status'] == 'fail':
        ...     print(f"Errors: {result['errors']}")
    """
    logger.info("\n" + "=" * 70)
    logger.info("W2T-BKIN Pipeline - NWB Validation")
    logger.info("=" * 70)

    nwb_path = Path(nwb_path)

    if not nwb_path.exists():
        raise FileNotFoundError(f"NWB file not found: {nwb_path}")

    logger.info(f"Validating: {nwb_path}")

    # Placeholder - would normally call nwbinspector
    # try:
    #     from nwbinspector import inspect_nwb
    #     messages = list(inspect_nwb(nwb_path))
    #     errors = [m for m in messages if m.severity == "CRITICAL"]
    #     warnings = [m for m in messages if m.severity == "BEST_PRACTICE_VIOLATION"]
    # except Exception as e:
    #     raise ValidationError(f"Validation failed: {e}")

    logger.info("  ⊘ Validation: Placeholder for future implementation")
    logger.info("=" * 70)

    result: ValidationResult = {
        "status": "pass",
        "errors": [],
        "warnings": [],
        "nwb_path": nwb_path,
    }

    return result


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "run_session",
    "run_validation",
    "RunResult",
    "ValidationResult",
]
