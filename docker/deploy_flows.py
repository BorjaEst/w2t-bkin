#!/usr/bin/env python3
"""Deploy W2T-BKIN flows to Prefect server during container startup.

This script creates Prefect deployments without needing a long-running serve process.
It's designed to be run once during server initialization.
"""

import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


async def deploy_flows_async():
    """Deploy W2T-BKIN flows to Prefect server using async API.

    IMPORTANT: Config files used in containers MUST use absolute paths
    that reference mounted volumes:
    - /data/raw (not ./data/raw or data/raw)
    - /data/interim
    - /data/processed
    - /models
    """
    try:
        import os

        from prefect.client.orchestration import get_client

        # Import the flow
        from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

        logger.info("📦 Deploying W2T-BKIN flows...")

        # Get default parameters from environment
        default_config = os.getenv("DEFAULT_CONFIG_FILE", "standard.toml")
        default_max_workers = int(os.getenv("DEFAULT_MAX_WORKERS", "4"))
        default_subject_filter = os.getenv("DEFAULT_SUBJECT_FILTER") or None
        default_session_filter = os.getenv("DEFAULT_SESSION_FILTER") or None

        # Config path in container (mounted from CONFIG_ROOT)
        config_path = f"/configs/{default_config}"

        async with get_client() as client:
            # Register the flow first
            flow_id = await client.create_flow_from_name(batch_process_sessions_prefect.name)

            # Create deployment
            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name="batch-processing",
                work_pool_name="docker-pool",
                work_queue_name="default",
                description="Process multiple subjects/sessions in parallel",
                tags=["w2t-bkin", "batch", "pipeline"],
                parameters={
                    "config_path": config_path,
                    "subject_filter": default_subject_filter,
                    "session_filter": default_session_filter,
                    "max_workers": default_max_workers,
                },
                version="1.0.0",
                entrypoint=f"{batch_process_sessions_prefect.__module__}:{batch_process_sessions_prefect.__name__}",
                path="/app/src",
            )

            logger.info(f"✅ Deployed: batch-processing")
            logger.info(f"   Flow ID: {flow_id}")
            logger.info(f"   Deployment ID: {deployment_id}")
            logger.info(f"   Default config: {config_path}")
            logger.info(f"   Max workers: {default_max_workers}")
            logger.info(f"   Queue: default")

        return True

    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        logger.exception("Deployment error")
        return False


def deploy_flows():
    """Sync wrapper for async deployment."""
    return asyncio.run(deploy_flows_async())


if __name__ == "__main__":
    success = deploy_flows()
    sys.exit(0 if success else 1)
