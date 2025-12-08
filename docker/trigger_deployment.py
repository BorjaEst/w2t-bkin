#!/usr/bin/env python3
"""Test script to trigger Prefect deployment from command line.

This script demonstrates how to trigger a deployment programmatically
without using the Prefect UI.
"""

import asyncio
import sys

from prefect.client.orchestration import get_client


async def trigger_deployment(
    deployment_name: str = "batch-process-flow/batch-processing",
    config_path: str = "/configs/container.toml",
    subject_filter: str = None,
    session_filter: str = None,
    max_parallel: int = 4,
    skip_bpod: bool = False,
    skip_pose: bool = False,
    skip_nwb_validation: bool = False,
):
    """Trigger a Prefect deployment with custom parameters.

    Args:
        deployment_name: Full deployment name (flow/deployment)
        config_path: Path to config file in container
        subject_filter: Optional subject filter
        session_filter: Optional session filter
        max_parallel: Number of parallel sessions to process
        skip_bpod: Skip Bpod processing
        skip_pose: Skip pose processing
        skip_nwb_validation: Skip NWB validation
    """
    async with get_client() as client:
        try:
            # Get deployment
            deployment = await client.read_deployment_by_name(deployment_name)
            print(f"✅ Found deployment: {deployment.name}")
            print(f"   ID: {deployment.id}")

            # Create flow run
            parameters = {
                "config_path": config_path,
                "subject_filter": subject_filter,
                "session_filter": session_filter,
                "max_parallel": max_parallel,
                "skip_bpod": skip_bpod,
                "skip_pose": skip_pose,
                "skip_nwb_validation": skip_nwb_validation,
            }

            print(f"\n📦 Creating flow run with parameters:")
            for key, value in parameters.items():
                print(f"   {key}: {value}")

            flow_run = await client.create_flow_run_from_deployment(
                deployment.id,
                parameters=parameters,
            )

            print(f"\n✅ Flow run created: {flow_run.id}")
            print(f"   Name: {flow_run.name}")
            print(f"   State: {flow_run.state.type if flow_run.state else 'Unknown'}")
            print(f"\n🔗 View in UI: http://localhost:4200/flow-runs/flow-run/{flow_run.id}")

            return flow_run.id

        except Exception as e:
            print(f"❌ Error: {e}")
            return None


if __name__ == "__main__":
    # Parse command line arguments
    subject = sys.argv[1] if len(sys.argv) > 1 else None
    session = sys.argv[2] if len(sys.argv) > 2 else None

    print("🚀 Triggering Prefect deployment...")
    print(f"   Subject filter: {subject or 'None'}")
    print(f"   Session filter: {session or 'None'}")
    print()

    # Run async function
    flow_run_id = asyncio.run(
        trigger_deployment(
            subject_filter=subject,
            session_filter=session,
        )
    )

    sys.exit(0 if flow_run_id else 1)
