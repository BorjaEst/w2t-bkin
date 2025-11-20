#!/usr/bin/env python3
"""Example: Simple Pipeline Usage.

Demonstrates the high-level pipeline API for session processing.

This example shows the Phase 2 orchestration pattern:
- Load config and session via pipeline.run_session()
- Pipeline owns Config/Session and extracts primitives
- Low-level tools called with paths, dicts, lists (no Session objects)
- Structured results returned with full provenance

Goal
----
Show how to use the pipeline API to process a session end-to-end.

Usage
-----
    # With synthetic session
    $ python examples/pipeline_simple.py

    # With custom session
    $ python examples/pipeline_simple.py --config path/to/config.toml --session Session-XYZ
"""

import argparse
import json
from pathlib import Path
import sys

# Add project root to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.scenarios import happy_path
from w2t_bkin.pipeline import run_session


def main():
    """Run simple pipeline example."""
    parser = argparse.ArgumentParser(description="Simple pipeline usage example")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config.toml (default: generate synthetic session)",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID (default: use synthetic session ID)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pipeline_simple"),
        help="Output directory for results (default: output/pipeline_simple)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("W2T-BKIN Pipeline - Simple Example")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Step 1: Setup (generate synthetic session or use provided)
    # -------------------------------------------------------------------------
    if args.config and args.session:
        config_path = args.config
        session_id = args.session
        print(f"\nUsing provided session:")
        print(f"  Config:  {config_path}")
        print(f"  Session: {session_id}")
    else:
        print("\nGenerating synthetic session...")
        session = happy_path.make_session(
            out_root=args.output / "raw",
            project_name="Pipeline-Simple-Demo",
            session_id="Session-DEMO-001",
            n_frames=300,
            n_trials=5,
        )
        config_path = session.config_path
        session_id = session.id
        print(f"  ✓ Synthetic session created")
        print(f"  Config:  {config_path}")
        print(f"  Session: {session_id}")

    # -------------------------------------------------------------------------
    # Step 2: Run Pipeline
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("Running Pipeline")
    print("=" * 80)

    result = run_session(
        config_path=config_path,
        session_id=session_id,
        options={
            "skip_nwb": True,  # NWB assembly not yet implemented
            "skip_validation": True,
        },
    )

    # -------------------------------------------------------------------------
    # Step 3: Inspect Results
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("Pipeline Results")
    print("=" * 80)

    # Manifest
    manifest = result["manifest"]
    print(f"\n[Manifest]")
    print(f"  Cameras:     {len(manifest.cameras)}")
    for cam in manifest.cameras:
        print(f"    - {cam.camera_id}: {cam.frame_count} frames, TTL={cam.ttl_id}")
    print(f"  TTLs:        {len(manifest.ttls)}")
    for ttl in manifest.ttls:
        print(f"    - {ttl.ttl_id}: {ttl.pulse_count} pulses")
    print(f"  Bpod files:  {len(manifest.bpod_files)}")

    # Alignment stats (if computed)
    if result.get("alignment_stats"):
        stats = result["alignment_stats"]
        print(f"\n[Alignment Stats]")
        print(f"  Max jitter:  {stats.max_jitter_s:.6f} s")
        print(f"  P95 jitter:  {stats.p95_jitter_s:.6f} s")
        print(f"  Method:      {stats.alignment_method}")
        print(f"  Timebase:    {stats.timebase_source}")

    # Events summary (if Bpod data present)
    if result.get("events_summary"):
        summary = result["events_summary"]
        print(f"\n[Events Summary]")
        print(f"  Session ID:  {summary.get('session_id')}")
        print(f"  Trials:      {summary.get('total_trials')}")
        print(f"  Events:      {summary.get('total_events')}")
        if "mean_trial_duration" in summary:
            print(f"  Mean trial duration: {summary['mean_trial_duration']:.3f} s")

    # Provenance
    prov = result["provenance"]
    print(f"\n[Provenance]")
    print(f"  Pipeline:    {prov.get('pipeline_version', 'unknown')}")
    print(f"  Config hash: {prov.get('config_hash', 'N/A')[:16]}...")
    print(f"  Session hash:{prov.get('session_hash', 'N/A')[:16]}...")
    print(f"  Timestamp:   {prov.get('timestamp', 'N/A')}")

    # -------------------------------------------------------------------------
    # Step 4: Save Results
    # -------------------------------------------------------------------------
    output_dir = args.output / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "pipeline_results.json"
    results_json = {
        "manifest": {
            "cameras": len(manifest.cameras),
            "ttls": len(manifest.ttls),
            "bpod_files": len(manifest.bpod_files),
        },
        "alignment_stats": (
            {
                "max_jitter_s": result["alignment_stats"].max_jitter_s,
                "p95_jitter_s": result["alignment_stats"].p95_jitter_s,
                "timebase_source": result["alignment_stats"].timebase_source,
            }
            if result.get("alignment_stats")
            else None
        ),
        "events_summary": result.get("events_summary"),
        "provenance": prov,
    }

    with open(results_path, "w") as f:
        json.dump(results_json, f, indent=2)

    print(f"\n[Output]")
    print(f"  Results saved to: {results_path}")

    print("\n" + "=" * 80)
    print("Pipeline Execution Complete")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Step 5: Explain Phase 2 Architecture
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("Phase 2 Architecture Pattern")
    print("=" * 80)
    print(
        """
This example demonstrates the Phase 2 orchestration pattern:

1. High-level orchestration (pipeline.run_session):
   - ONLY layer that owns Config and Session
   - Loads config.toml and session.toml
   - Extracts primitives from Session: file patterns, order specs, trial configs
   
2. Low-level tools (parse_bpod, get_ttl_pulses, etc.):
   - Accept ONLY primitives: paths, dicts, lists, scalars
   - Zero Config/Session imports
   - Pure functions: inputs → outputs
   
3. Structured results:
   - RunResult with manifest, alignment_stats, events_summary, provenance
   - Module-local models (AlignmentStats, PoseBundle, etc.)
   - Full provenance tracking for reproducibility

Benefits:
- Clear separation of concerns
- Easy to test (low-level tools don't need Session fixtures)
- Composable (can call low-level tools directly if needed)
- Type-safe (Pydantic models throughout)
"""
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
