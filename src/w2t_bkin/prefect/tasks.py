"""Prefect task wrappers for pipeline phases.

This module provides Prefect @task decorated wrappers around the core pipeline
phase functions. Each wrapper configures appropriate retry policies and
metadata for observability in the Prefect UI.

Phase Tasks:
------------
- initialization_task: Phase 0 - Load config, create NWBFile
- discovery_task: Phase 1 - Discover cameras, TTLs, Bpod data
- preprocessing_task: Phase 2 - Run DLC/SLEAP pose estimation
- ingestion_task: Phase 3 - Ingest Bpod, pose, TTL data
- synchronization_task: Phase 4 - Align timebases
- assembly_task: Phase 5 - Assemble behavior and pose data
- finalization_task: Phase 6 - Write NWB, validate

Monolithic Task:
----------------
- process_session_monolithic_task: Entire session as one task (backward compat)

Retry Policies:
---------------
Each phase has customized retry settings based on failure characteristics:
- File I/O phases: 2 retries, 15s delay
- GPU phases: 2 retries, 30s delay (longer for GPU availability)
- Deterministic phases: 1 retry, 10s delay
"""

import logging
from pathlib import Path

from prefect import task

from ..core.pipeline import SessionPipeline
from ..core.pipeline.models import PipelineContext, RunOptions
from ..core.pipeline.phases import (
    run_phase_0,
    run_phase_1,
    run_phase_2,
    run_phase_3,
    run_phase_4,
    run_phase_5,
    run_phase_6,
)

logger = logging.getLogger(__name__)


@task(
    name="phase-0-initialization",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "initialization"],
    log_prints=True,
)
def initialization_task(context: PipelineContext) -> PipelineContext:
    """Phase 0: Load configuration and create NWBFile.
    
    Retry Logic: 1 retry (config loading failures usually deterministic)
    
    Args:
        context: Pipeline context with config path and session info
        
    Returns:
        Updated context with config and NWBFile
        
    Raises:
        ConfigError: If configuration is invalid
        IngestError: If NWBFile creation fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Initialization", total=None)
        run_phase_0(context, progress, task_id)
    
    return context


@task(
    name="phase-1-discovery",
    retries=2,
    retry_delay_seconds=15,
    tags=["pipeline", "discovery"],
    log_prints=True,
)
def discovery_task(context: PipelineContext) -> PipelineContext:
    """Phase 1: Discover cameras, TTLs, and Bpod data.
    
    Retry Logic: 2 retries (file system operations can be transiently unavailable)
    
    Args:
        context: Pipeline context with session directory
        
    Returns:
        Updated context with discovered files
        
    Raises:
        IngestError: If required files not found
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Discovery", total=None)
        run_phase_1(context, progress, task_id)
    
    return context


@task(
    name="phase-2-preprocessing",
    retries=2,
    retry_delay_seconds=30,
    tags=["pipeline", "preprocessing", "pose"],
    log_prints=True,
)
def preprocessing_task(context: PipelineContext) -> PipelineContext:
    """Phase 2: Run DLC/SLEAP pose estimation.
    
    Retry Logic: 2 retries, longer delay (GPU operations, may be temporarily busy)
    
    Args:
        context: Pipeline context with discovered videos
        
    Returns:
        Updated context with pose estimation results
        
    Raises:
        IngestError: If pose estimation fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Preprocessing", total=None)
        run_phase_2(context, progress, task_id)
    
    return context


@task(
    name="phase-3-ingestion",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "ingestion"],
    log_prints=True,
)
def ingestion_task(context: PipelineContext) -> PipelineContext:
    """Phase 3: Ingest Bpod, pose, and TTL data into NWB.
    
    Retry Logic: 1 retry (data loading usually deterministic)
    
    Args:
        context: Pipeline context with data files
        
    Returns:
        Updated context with ingested data
        
    Raises:
        IngestError: If data ingestion fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Ingestion", total=None)
        run_phase_3(context, progress, task_id)
    
    return context


@task(
    name="phase-4-synchronization",
    retries=2,
    retry_delay_seconds=20,
    tags=["pipeline", "sync"],
    log_prints=True,
)
def synchronization_task(context: PipelineContext) -> PipelineContext:
    """Phase 4: Align timebases and synchronize data streams.
    
    Retry Logic: 2 retries (computational, might hit memory limits)
    
    Args:
        context: Pipeline context with ingested data
        
    Returns:
        Updated context with synchronized data
        
    Raises:
        SyncError: If synchronization fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Synchronization", total=None)
        run_phase_4(context, progress, task_id)
    
    return context


@task(
    name="phase-5-assembly",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "assembly"],
    log_prints=True,
)
def assembly_task(context: PipelineContext) -> PipelineContext:
    """Phase 5: Assemble behavior and pose data.
    
    Retry Logic: 1 retry (usually succeeds if data is present)
    
    Args:
        context: Pipeline context with synchronized data
        
    Returns:
        Updated context with assembled data
        
    Raises:
        IngestError: If assembly fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Assembly", total=None)
        run_phase_5(context, progress, task_id)
    
    return context


@task(
    name="phase-6-finalization",
    retries=1,
    retry_delay_seconds=10,
    tags=["pipeline", "finalization", "nwb"],
    log_prints=True,
)
def finalization_task(context: PipelineContext) -> PipelineContext:
    """Phase 6: Write NWB file, sidecars, and validate.
    
    Retry Logic: 1 retry (file write can transiently fail)
    
    Args:
        context: Pipeline context with complete data
        
    Returns:
        Updated context with file paths
        
    Raises:
        IngestError: If finalization fails
        ValidationError: If NWB validation fails
    """
    from rich.progress import Progress
    
    with Progress() as progress:
        task_id = progress.add_task("Finalization", total=None)
        run_phase_6(context, progress, task_id)
    
    return context


@task(
    name="process-session-monolithic",
    retries=2,
    retry_delay_seconds=60,
    tags=["pipeline", "session", "monolithic"],
    log_prints=True,
)
def process_session_monolithic_task(
    config_path: str | Path,
    subject_id: str,
    session_id: str,
) -> dict:
    """Process entire session as one task (existing behavior).
    
    This is the monolithic approach where the entire SessionPipeline.run()
    is wrapped as a single task. Provides fastest execution but limited
    observability compared to phase-level execution.
    
    Args:
        config_path: Path to configuration TOML file
        subject_id: Subject identifier
        session_id: Session identifier
        
    Returns:
        Result dictionary with success status and file paths
        
    Raises:
        ConfigError: If configuration is invalid
        IngestError: If pipeline execution fails
    """
    try:
        pipeline = SessionPipeline(
            config_path=Path(config_path),
            subject_id=subject_id,
            session_id=session_id,
            options=RunOptions(),
        )
        
        nwb_path = pipeline.run()
        
        return {
            "success": True,
            "subject_id": subject_id,
            "session_id": session_id,
            "nwb_path": str(nwb_path) if nwb_path else None,
            "error": None,
        }
        
    except Exception as e:
        logger.error(f"Session {subject_id}/{session_id} failed: {e}")
        return {
            "success": False,
            "subject_id": subject_id,
            "session_id": session_id,
            "nwb_path": None,
            "error": str(e),
        }


__all__ = [
    # Phase tasks
    "initialization_task",
    "discovery_task",
    "preprocessing_task",
    "ingestion_task",
    "synchronization_task",
    "assembly_task",
    "finalization_task",
    # Monolithic task
    "process_session_monolithic_task",
]
