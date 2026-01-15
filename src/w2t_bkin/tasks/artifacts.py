"""Prefect tasks for artifact generation (DLC, SLEAP)."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from prefect import task

from w2t_bkin import utils
from w2t_bkin.config import DiscoveryConfig
from w2t_bkin.exceptions import IngestError
from w2t_bkin.models import ArtifactsResult, DiscoveryResult, SessionInfo
from w2t_bkin.operations import pose_generator

logger = logging.getLogger(__name__)


@task(
    name="Discover All Files",
    description="Discover all input files (cameras, Bpod, TTL)",
    tags=["discovery", "io"],
    cache_policy=None,
    retries=1,
)
def generate_artifacts_task(discovery: DiscoveryResult, info: SessionInfo, config: DiscoveryConfig) -> ArtifactsResult:
    pass  # TODO: Implement this task using generate_artifacts operation


@task(
    name="Discover Artifacts",
    description="Discover intermediate artifacts (pose, TTL, etc.)",
    tags=["discovery", "io", "artifacts"],
    cache_policy=None,
    retries=1,
)
def discover_artifacts_task(discovery: DiscoveryResult, info: SessionInfo, config: DiscoveryConfig) -> ArtifactsResult:
    pass  # TODO: Implement this task using generate_artifacts operation


@task(
    name="Auto Artifacts",
    description="Automatically handle intermediate artifacts (pose, TTL, etc.) based on config",
    tags=["discovery", "io", "artifacts", "auto"],
    cache_policy=None,
    retries=1,
)
def auto_artifacts_task(discovery: DiscoveryResult, info: SessionInfo, config: DiscoveryConfig) -> ArtifactsResult:
    logger.info(f"Auto-processing artifacts for session {info.session_dir}")
    # artifacts = ArtifactsResult() or similar initialization

    for camera in info.metadata.pose.models:
        model_used = info.metadata.pose.models[camera.model_id]
        logger.info(f"Processing artifacts for model {camera}")
        if discovery.pose_files.get(camera):  # If files already exist we use the files
            logger.info(f"  Found existing pose files for model {camera}, skipping generation")
            # artiffacts add discovery.pose_files[camera]
        elif discovery.model_files[model_used]:  # If model files exist we generate pose files
            logger.info(f"  Generating pose files for model {camera} using {model_used}")
            # artifacts add pose_generation.generate_pose_files(...)
        else:  # No files and model, cannot generate pose files
            logger.warning(f"  No model files found for model {camera}, cannot generate pose files")
            # artifacts add None

    # return artifacts
