#!/usr/bin/env python3
"""Deploy W2T-BKIN pipelines to Prefect server.

This script creates Prefect deployments for the batch processing flow,
allowing you to trigger and monitor pipeline runs from the Prefect UI.

Usage:
    python scripts/deploy_prefect.py
    python scripts/deploy_prefect.py --work-pool my-pool
"""

from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prefect import serve

from w2t_bkin.prefect.flows import batch_process_sessions_prefect


def deploy_flows(work_pool: str = "docker-pool"):
    """Deploy W2T-BKIN flows to Prefect server.

    Args:
        work_pool: Name of the work pool to use (default: docker-pool)
    """
    print(f"🚀 Deploying W2T-BKIN flows to Prefect server...")
    print(f"   Work pool: {work_pool}")

    # Create deployment for the batch processing flow
    deployment = batch_process_sessions_prefect.to_deployment(
        name="batch-processing",
        work_pool_name=work_pool,
        description="Process multiple subjects/sessions in parallel",
        tags=["w2t-bkin", "batch", "pipeline"],
        parameters={
            "config_path": "/app/config.toml",  # Default, can be overridden in UI
            "subject_filter": None,
            "session_filter": None,
            "max_workers": 4,
        },
    )

    print(f"✅ Created deployment: batch-processing")
    print(f"   Flow: {batch_process_sessions_prefect.name}")
    print(f"   Work Pool: {work_pool}")

    # Serve the deployment (keeps running)
    print("\n📡 Starting deployment server...")
    print("   Press Ctrl+C to stop")

    serve(deployment)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy W2T-BKIN flows to Prefect")
    parser.add_argument(
        "--work-pool",
        default="docker-pool",
        help="Work pool name (default: docker-pool)",
    )

    args = parser.parse_args()

    try:
        deploy_flows(work_pool=args.work_pool)
    except KeyboardInterrupt:
        print("\n\n👋 Deployment server stopped")
        sys.exit(0)
