#!/usr/bin/env python3
"""Deploy W2T-BKIN flows to Prefect server during container startup.

This script creates Prefect deployments without needing a long-running serve process.
It's designed to be run once during server initialization.
"""

import asyncio
import logging
import os
import sys

from prefect.client.orchestration import get_client

from w2t_bkin.flows.batch import batch_process_flow
from w2t_bkin.flows.session import process_session_flow

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def deploy_flows() -> bool:
    """Deploy W2T-BKIN flows to Prefect server using async API.

    Deploys two flows:
    1. process-session: Single session processing
    2. batch-processing: Parallel batch processing

    IMPORTANT: Config files used in containers MUST use absolute paths
    that reference mounted volumes:
    - /data/raw (not ./data/raw or data/raw)
    - /data/interim
    - /data/processed
    - /models

    Returns:
        True if deployment successful, False otherwise
    """
    try:
        logger.info("📦 Deploying W2T-BKIN flows...")

        # Get default parameters from environment
        default_config = os.getenv("DEFAULT_CONFIG_FILE", "standard.toml")
        default_max_parallel = int(os.getenv("DEFAULT_MAX_WORKERS", "4"))
        default_subject_filter = os.getenv("DEFAULT_SUBJECT_FILTER") or None
        default_session_filter = os.getenv("DEFAULT_SESSION_FILTER") or None

        # Config path in container (mounted from CONFIG_ROOT)
        config_path = f"/configs/{default_config}"

        async with get_client() as client:
            # Deploy Deployment 1: Single session processing
            flow_id_single = await client.create_flow_from_name(process_session_flow.name)
            deployment_id_single = await client.create_deployment(
                flow_id=flow_id_single,
                name="process-session",
                work_pool_name="docker-pool",
                work_queue_name="default",
                description="Process a single session with all operations",
                tags=["w2t-bkin", "single-session", "production"],
                parameters={
                    "config_path": config_path,
                    "subject_id": "subject-001",  # Example default
                    "session_id": "session-001",  # Example default
                    "skip_bpod": False,
                    "skip_pose": False,
                    "skip_nwb_validation": False,
                },
                version="0.0.10",
                entrypoint=f"{process_session_flow.__module__}:{process_session_flow.__name__}",
                path="/app/src",
            )

            logger.info(f"✅ Deployed: process-session (single session)")
            logger.info(f"   Flow ID: {flow_id_single}")
            logger.info(f"   Deployment ID: {deployment_id_single}")
            logger.info(f"   Default config: {config_path}")
            logger.info(f"   Queue: default")

            # Deploy Deployment 2: Batch processing (parallel)
            flow_id_batch = await client.create_flow_from_name(batch_process_flow.name)
            deployment_id_batch = await client.create_deployment(
                flow_id=flow_id_batch,
                name="batch-processing",
                work_pool_name="docker-pool",
                work_queue_name="default",
                description="Batch process multiple sessions in parallel",
                tags=["w2t-bkin", "batch", "production", "parallel"],
                parameters={
                    "config_path": config_path,
                    "subject_filter": default_subject_filter,
                    "session_filter": default_session_filter,
                    "max_parallel": default_max_parallel,
                    "skip_bpod": False,
                    "skip_pose": False,
                    "skip_nwb_validation": False,
                },
                version="0.0.10",
                entrypoint=f"{batch_process_flow.__module__}:{batch_process_flow.__name__}",
                path="/app/src",
            )

            logger.info(f"✅ Deployed: batch-processing (parallel mode)")
            logger.info(f"   Flow ID: {flow_id_batch}")
            logger.info(f"   Deployment ID: {deployment_id_batch}")
            logger.info(f"   Default config: {config_path}")
            logger.info(f"   Max parallel: {default_max_parallel}")
            logger.info(f"   Queue: default")

        return True

    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        logger.exception("Deployment error")
        return False


if __name__ == "__main__":
    success = asyncio.run(deploy_flows())
    sys.exit(0 if success else 1)
