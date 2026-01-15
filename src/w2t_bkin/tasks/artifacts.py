"""Prefect tasks for artifact resolution/generation (DLC, SLEAP)."""

import logging

from prefect import task

from w2t_bkin.config import ArtifactsConfig
from w2t_bkin.models import ArtifactsResult, DiscoveryResult, SessionInfo
from w2t_bkin.operations import pose_generator

logger = logging.getLogger(__name__)


@task(
    name="Generate Artifacts",
    description="Generate intermediate artifacts (pose, etc.)",
    tags=["artifacts", "pose", "dlc"],
    cache_policy=None,
    retries=1,
)
def generate_artifacts_task(discovery: DiscoveryResult, info: SessionInfo, config: ArtifactsConfig) -> ArtifactsResult:
    logger.info(f"Generating pose artifacts for session {info.subject_id}/{info.session_id}")
    return pose_generator.generate_pose_artifacts(discovery, info, config)


@task(
    name="Discover Artifacts",
    description="Discover intermediate artifacts (pose, TTL, etc.)",
    tags=["discovery", "io", "artifacts"],
    cache_policy=None,
    retries=1,
)
def discover_artifacts_task(discovery: DiscoveryResult, info: SessionInfo) -> ArtifactsResult:
    logger.info(f"Discovering pose artifacts for session {info.subject_id}/{info.session_id}")
    return pose_generator.discover_pose_artifacts(discovery, info)


@task(
    name="Auto Artifacts",
    description="Automatically handle intermediate artifacts (pose, TTL, etc.) based on config",
    tags=["discovery", "io", "artifacts", "auto"],
    cache_policy=None,
    retries=1,
)
def auto_artifacts_task(discovery: DiscoveryResult, info: SessionInfo, config: ArtifactsConfig) -> ArtifactsResult:
    logger.info(f"Auto-resolving pose artifacts for session {info.subject_id}/{info.session_id}")
    return pose_generator.auto_pose_artifacts(discovery, info, config)
