#!/usr/bin/env python3
"""Deploy W2T-BKIN flows to Prefect server during container startup.

This script creates Prefect deployments using the Python API with Pydantic models,
which automatically generates UI forms with validation. No manual schema writing needed!

Environment Variables (control defaults):
    DEFAULT_CONFIG_FILE: Config filename in /configs/ (default: standard.toml)
    DEFAULT_MAX_WORKERS: Max parallel sessions for batch processing (default: 4)
    DEFAULT_SUBJECT_FILTER: Regex pattern for subject filtering (optional)
    DEFAULT_SESSION_FILTER: Regex pattern for session filtering (optional)

IMPORTANT: Config files used in containers MUST use absolute paths
that reference mounted volumes:
    - /data/raw (not ./data/raw or data/raw)
    - /data/interim
    - /data/processed
    - /models

Note: Worker image is NOT specified in deployments. Workers connect to the
work pool and execute flows using their own container image (defined in
docker-compose.yml via WORKER_IMAGE environment variable).
"""

import logging
import os
import sys

from w2t_bkin.api import BatchFlowConfig, SessionFlowConfig
from w2t_bkin.flows import batch_process_flow, process_session_flow

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def deploy_flows() -> bool:
    """Deploy W2T-BKIN flows using Python API with Pydantic models.

    Deploys two flows:
    1. process-session: Single session processing
    2. batch-processing: Parallel batch processing

    Uses Pydantic models for automatic UI form generation and validation.
    Default parameters controlled by environment variables.

    Returns:
        True if deployment successful, False otherwise
    """
    try:
        logger.info("📦 Deploying W2T-BKIN flows with Pydantic schemas...")

        # Get default parameters from environment
        default_config = os.getenv("DEFAULT_CONFIG_FILE", "standard.toml")
        default_max_parallel = int(os.getenv("DEFAULT_MAX_WORKERS", "4"))
        default_subject_filter = os.getenv("DEFAULT_SUBJECT_FILTER") or None
        default_session_filter = os.getenv("DEFAULT_SESSION_FILTER") or None

        # Config path in container (mounted from CONFIG_ROOT)
        config_path = f"/configs/{default_config}"

        logger.info(f"   Config path: {config_path}")
        logger.info(f"   Max parallel: {default_max_parallel}")
        if default_subject_filter:
            logger.info(f"   Subject filter: {default_subject_filter}")
        if default_session_filter:
            logger.info(f"   Session filter: {default_session_filter}")

        # =====================================================================
        # Deploy 1: Single session processing
        # =====================================================================
        logger.info("\n[1/2] Deploying: process-session")

        session_config = SessionFlowConfig(
            config_path=config_path,
            subject_id="subject-001",  # Example default
            session_id="session-001",  # Example default
            skip_bpod=False,
            skip_pose=False,
            skip_ecephys=False,
            skip_camera_sync=False,
            skip_nwb_validation=False,
        )

        # Configure for Docker work pool with pre-built worker image
        #  Workers spawn containers using WORKER_IMAGE from docker-compose.yml
        process_session_flow.deploy(
            name="process-session",
            work_pool_name="docker-pool",
            image=os.getenv("WORKER_IMAGE", "ghcr.io/borjaest/w2t-bkin:worker"),
            build=False,  # Don't build - using pre-built images
            push=False,  # Don't push - using pre-built images
            parameters={"config": session_config.model_dump()},
            tags=["w2t-bkin", "single-session", "production"],
            description="""
Process a single experimental session through the w2t-bkin pipeline.

This deployment processes one session at a time with full validation.
All processing steps are enabled by default. Use skip flags to disable
specific operations (e.g., skip_nwb_validation for faster execution).

Pydantic validation ensures:
- config_path ends with .toml
- subject_id and session_id match pattern ^[\\w\\-]+$
- All skip flags are boolean
            """.strip(),
            version="0.0.10",
        )

        logger.info("  ✅ Deployed: process-session")
        logger.info("     Work pool: docker-pool")
        logger.info("     Default config: " + config_path)

        # =====================================================================
        # Deploy 2: Batch processing (parallel)
        # =====================================================================
        logger.info("\n[2/2] Deploying: batch-processing")

        batch_config = BatchFlowConfig(
            config_path=config_path,
            subject_filter=default_subject_filter,
            session_filter=default_session_filter,
            max_parallel=default_max_parallel,
            skip_bpod=False,
            skip_pose=False,
            skip_ecephys=False,
            skip_camera_sync=False,
            skip_nwb_validation=False,
        )

        batch_process_flow.deploy(
            name="batch-processing",
            work_pool_name="docker-pool",
            image=os.getenv("WORKER_IMAGE", "ghcr.io/borjaest/w2t-bkin:worker"),
            build=False,  # Don't build - using pre-built images
            push=False,  # Don't push - using pre-built images
            parameters={"config": batch_config.model_dump()},
            tags=["w2t-bkin", "batch", "production", "parallel"],
            description="""
Process multiple experimental sessions in parallel.

This deployment discovers sessions from the raw data directory,
filters them according to regex patterns, and processes them concurrently.

Pydantic validation ensures:
- config_path ends with .toml
- subject_filter and session_filter are valid regex (if provided)
- max_parallel is between 1 and 16
- All skip flags are boolean

Environment variables control default filters and parallelism.
            """.strip(),
            version="0.0.10",
        )

        logger.info("  ✅ Deployed: batch-processing")
        logger.info("     Work pool: docker-pool")
        logger.info("     Default config: " + config_path)
        logger.info(f"     Max parallel: {default_max_parallel}")
        if default_subject_filter:
            logger.info(f"     Subject filter: {default_subject_filter}")
        if default_session_filter:
            logger.info(f"     Session filter: {default_session_filter}")

        logger.info("\n✅ All deployments created successfully")
        logger.info("   Prefect UI will auto-generate forms from Pydantic models")
        logger.info("   Schemas cannot drift from code (single source of truth)")

        return True

    except Exception as e:
        logger.error(f"\n❌ Deployment failed: {e}")
        logger.exception("Deployment error")
        return False


if __name__ == "__main__":
    success = deploy_flows()
    sys.exit(0 if success else 1)
