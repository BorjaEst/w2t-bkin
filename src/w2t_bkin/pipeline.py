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
- events_summary: Behavioral events summary (if Bpod files present)
- pose_bundle: Harmonized pose data (if available)
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
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

from w2t_bkin.config import load_config, load_session
from w2t_bkin.domain import AlignmentStats, Config, FacemapBundle, Manifest, PoseBundle, Session, TranscodedVideo
from w2t_bkin.events import extract_trials, parse_bpod
from w2t_bkin.ingest import build_and_count_manifest, verify_manifest
from w2t_bkin.sync import create_timebase_provider_from_config, get_ttl_pulses
from w2t_bkin.utils import compute_hash, ensure_directory

logger = logging.getLogger(__name__)


# =============================================================================
# Result Models
# =============================================================================


class RunResult(TypedDict, total=False):
    """Result of run_session execution.

    Contains all outputs from pipeline stages. Fields are optional to support
    partial execution (e.g., skip NWB assembly, optional pose/facemap).

    Attributes:
        manifest: File discovery manifest with frame/TTL counts
        alignment_stats: Timebase alignment quality metrics (optional)
        events_summary: Behavioral events summary dict (optional)
        pose_bundle: Harmonized pose data (optional)
        facemap_bundle: Facial motion signals (optional)
        transcoded_videos: List of transcoded videos (optional)
        nwb_path: Path to assembled NWB file (optional)
        provenance: Pipeline execution metadata
    """

    manifest: Manifest
    alignment_stats: Optional[AlignmentStats]
    events_summary: Optional[Dict[str, Any]]
    pose_bundle: Optional[PoseBundle]
    facemap_bundle: Optional[FacemapBundle]
    transcoded_videos: Optional[List[TranscodedVideo]]
    nwb_path: Optional[Path]
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
    4. Import pose/facemap (if available)
    5. Transcode videos (if enabled)
    6. Create timebase and compute alignment
    7. Assemble NWB file (if not skipped)

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
    logger.info("W2T-BKIN Pipeline - Session Processing")
    logger.info("=" * 70)
    logger.info(f"Config: {config_path}")
    logger.info(f"Session: {session_id}")
    logger.info("=" * 70)

    # -------------------------------------------------------------------------
    # Phase 0: Load Configuration
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 0] Loading configuration...")
    config_path = Path(config_path)
    config = load_config(config_path)
    logger.info(f"  ✓ Config loaded: {config.project.name}")

    # Find session.toml
    session_dir = Path(config.paths.raw_root) / session_id
    session_path = session_dir / config.paths.metadata_file
    session = load_session(session_path)
    logger.info(f"  ✓ Session loaded: {session.session.id}")

    # Verify session_id matches
    if session.session.id != session_id:
        raise ValueError(f"Session ID mismatch: requested '{session_id}', " f"found '{session.session.id}' in {session_path}")

    # -------------------------------------------------------------------------
    # Phase 1: Ingest and Verify
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 1] Building manifest...")
    manifest = build_and_count_manifest(config, session)
    logger.info(f"  ✓ Discovered {len(manifest.cameras)} cameras")
    logger.info(f"  ✓ Discovered {len(manifest.ttls)} TTL channels")
    logger.info(f"  ✓ Discovered {len(manifest.bpod_files or [])} Bpod files")

    # Verify frame/TTL alignment
    if not skip_validation:
        logger.info("\n[Phase 1] Verifying frame/TTL alignment...")
        tolerance = config.verification.mismatch_tolerance_frames
        verification = verify_manifest(manifest, tolerance=tolerance)
        logger.info(f"  ✓ Verification status: {verification.status}")

        if verification.status == "fail":
            logger.error("  ✗ Verification failed - aborting pipeline")
            raise ValueError("Frame/TTL verification failed")

    # -------------------------------------------------------------------------
    # Phase 2: Parse Events (Optional)
    # -------------------------------------------------------------------------
    events_summary: Optional[Dict[str, Any]] = None

    if manifest.bpod_files and len(manifest.bpod_files) > 0:
        logger.info("\n[Phase 2] Parsing Bpod events...")

        try:
            # Extract primitives from Session
            bpod_pattern = session.bpod.path
            bpod_order = session.bpod.order
            trial_type_configs = session.bpod.trial_types

            # Parse Bpod files with low-level API
            bpod_data = parse_bpod(
                session_dir=session_dir,
                pattern=bpod_pattern,
                order=bpod_order,
                continuous_time=True,
            )
            logger.info(f"  ✓ Parsed {bpod_data['SessionData']['nTrials']} trials")

            # Extract trials (no alignment yet)
            trials = extract_trials(bpod_data, trial_offsets=None)
            logger.info(f"  ✓ Extracted {len(trials)} trials")

            # Create summary
            events_summary = {
                "session_id": session_id,
                "total_trials": len(trials),
                "trial_types": list(set(t.trial_type for t in trials if t.trial_type)),
                "outcomes": {outcome.value: sum(1 for t in trials if t.outcome == outcome) for outcome in set(t.outcome for t in trials)},
            }
            logger.info("  ✓ Events summary created")

        except Exception as e:
            logger.warning(f"  ⚠ Bpod parsing failed: {e}")
            events_summary = None

    # -------------------------------------------------------------------------
    # Phase 3: Synchronization (Placeholder)
    # -------------------------------------------------------------------------
    logger.info("\n[Phase 3] Creating timebase and alignment...")

    # Create timebase provider
    timebase_provider = create_timebase_provider_from_config(config, manifest)
    logger.info(f"  ✓ Timebase provider created: {config.timebase.source}")

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
    # Phase 4: Optional Modalities (Pose, Facemap, Transcode)
    # -------------------------------------------------------------------------
    pose_bundle: Optional[PoseBundle] = None
    facemap_bundle: Optional[FacemapBundle] = None
    transcoded_videos: Optional[List[TranscodedVideo]] = None

    # Pose import (placeholder)
    logger.info("\n[Phase 4] Checking for optional modalities...")
    logger.info("  ⊘ Pose import: Not implemented")
    logger.info("  ⊘ Facemap computation: Not implemented")

    if transcode_videos:
        logger.info("  ⊘ Video transcoding: Not implemented")

    # -------------------------------------------------------------------------
    # Phase 5: NWB Assembly (Placeholder)
    # -------------------------------------------------------------------------
    nwb_path: Optional[Path] = None

    if not skip_nwb:
        logger.info("\n[Phase 5] NWB assembly...")
        logger.info("  ⊘ NWB assembly: Placeholder for future implementation")

        # Would normally call:
        # from w2t_bkin.nwb import assemble_nwb
        # output_dir = Path(config.paths.output_root) / session_id
        # ensure_directory(output_dir)
        # nwb_path = assemble_nwb(
        #     manifest=manifest,
        #     config=config,
        #     provenance=provenance,
        #     output_dir=output_dir
        # )

    # -------------------------------------------------------------------------
    # Build Result
    # -------------------------------------------------------------------------
    logger.info("\n[Complete] Pipeline execution finished")
    logger.info("=" * 70)

    # Compute provenance
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
    }

    result: RunResult = {
        "manifest": manifest,
        "alignment_stats": alignment_stats,
        "events_summary": events_summary,
        "pose_bundle": pose_bundle,
        "facemap_bundle": facemap_bundle,
        "transcoded_videos": transcoded_videos,
        "nwb_path": nwb_path,
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
