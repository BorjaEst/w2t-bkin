#!/usr/bin/env python3
"""Test pipeline implementation with synthetic data.

This script creates a synthetic session and runs the pipeline to verify
the implementation works correctly.
"""

import logging
from pathlib import Path
import shutil

from synthetic import build_raw_folder
from w2t_bkin.pipeline import RunOptions, run_session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main():
    """Run pipeline test."""
    output_root = Path("output/pipeline_test")

    # Clean up previous run
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Pipeline Implementation Test")
    print("=" * 80)

    # Generate synthetic session
    print("\nStep 1: Generating synthetic session...")
    session = build_raw_folder(
        out_root=output_root / "raw",
        project_name="pipeline_test",
        subject_id="subject-001",
        session_id="session-001",
        camera_ids=["cam0"],
        ttl_ids=["ttl_camera", "ttl_bpod"],
        n_frames=300,
        n_trials=5,
        fps=30.0,
        camera_start_delay_s=2.0,
        bpod_start_delay_s=6.0,
        bpod_sync_delay_s=1.0,
        seed=42,
    )
    print(f"  ✓ Config: {session.config_path}")
    print(f"  ✓ Session: {session.session_path}")

    # Run pipeline
    print("\nStep 2: Running pipeline...")
    result = run_session(
        config_path=str(session.config_path),
        subject_id="subject-001",
        session_id="session-001",
        options=RunOptions(skip_verification=False),
    )

    # Check result
    print("\n" + "=" * 80)
    print("Test Result")
    print("=" * 80)

    if result.success:
        print(f"\n✓ SUCCESS")
        print(f"  NWB file: {result.nwb_path}")
        print(f"  NWB size: {result.nwb_path.stat().st_size / 1024:.1f} KB")

        if result.alignment_stats:
            print(f"\n  Alignment stats:")
            stats = result.alignment_stats.get("statistics", {})
            if stats:
                print(f"    Trials aligned: {stats.get('n_trials_aligned', 0)}")
                print(f"    Mean offset:    {stats.get('mean_offset_s', 0):.4f} s")

        return 0
    else:
        print(f"\n✗ FAILED")
        print(f"  Error: {result.error}")
        return 1


if __name__ == "__main__":
    exit(main())
