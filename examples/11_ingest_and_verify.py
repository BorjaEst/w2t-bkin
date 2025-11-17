#!/usr/bin/env python3
"""Example 11: Ingest and Verify Focus.

This example demonstrates the ingest and verification phase in detail,
showing the two-step workflow:

1. **Fast Discovery**: Enumerate files without counting (O(n) in file count)
2. **Slow Counting**: Count frames and TTL pulses (O(n*m) in data size)
3. **Verification**: Validate frame/TTL alignment

Key Concepts:
-------------
- Manifest data structure
- Fast vs slow discovery modes
- Frame counting with ffprobe
- TTL pulse counting
- Per-camera verification logic
- Tolerance-based pass/warn/fail
- verification_summary.json sidecar

Use Cases:
----------
- Quick sanity check before heavy processing
- Debugging file discovery issues
- Tuning tolerance thresholds
- Understanding verification logic

Requirements Demonstrated:
-------------------------
- FR-1, FR-2, FR-3: Config, session, file discovery
- FR-13: Video frame counting
- FR-15: TTL pulse counting
- FR-16: Verification with tolerance
- A6, A7: Manifest and verification

Example Usage:
-------------
    $ python examples/11_ingest_and_verify.py

    # Test with different tolerances
    $ TOLERANCE=10 python examples/11_ingest_and_verify.py
    $ TOLERANCE=0 python examples/11_ingest_and_verify.py
"""

import json
from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

from synthetic.scenarios import happy_path
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest


class ExampleSettings(BaseSettings):
    """Settings for Example 11: Ingest and Verify Focus."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/11_ingest_verify")
    n_frames: int = 200
    seed: int = 42
    tolerance: int = 5


def run_pipeline(settings: ExampleSettings) -> dict:
    """Run focused ingest and verification example.

    Args:
        settings: Example settings with output paths and parameters

    Returns:
        Dictionary with artifacts
    """
    output_root = settings.output_root
    n_frames = settings.n_frames
    seed = settings.seed
    tolerance = settings.tolerance

    print("=" * 80)
    print("W2T-BKIN Example 11: Ingest and Verify Focus")
    print("=" * 80)
    print()

    # Clean
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PHASE 0: Generate Synthetic Data
    # =========================================================================
    print("=" * 80)
    print("PHASE 0: Generate Synthetic Data")
    print("=" * 80)

    print(f"\n📦 Generating synthetic session ({n_frames} frames, seed={seed})...")
    session = happy_path.make_session(
        root=output_root,
        session_id="ingest-verify-001",
        n_frames=n_frames,
        seed=seed,
    )
    print(f"   ✓ Data generated in: {session.raw_dir}")

    # =========================================================================
    # PHASE 1: Load Configuration
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: Load Configuration")
    print("=" * 80)

    print(f"\n📖 Loading config and session...")
    config = cfg_module.load_config(session.config_path)
    session_data = cfg_module.load_session(session.session_path)

    print(f"   ✓ Config:")
    print(f"      - Project: {config.project.name}")
    print(f"      - Raw root: {config.paths.raw_root}")
    print(f"   ✓ Session:")
    print(f"      - ID: {session_data.session.id}")
    print(f"      - Subject: {session_data.session.subject_id}")
    print(f"      - Cameras: {len(session_data.cameras)}")
    print(f"      - TTLs: {len(session_data.TTLs)}")

    # =========================================================================
    # PHASE 2: Fast Discovery (No Counting)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Fast Discovery (No Counting)")
    print("=" * 80)

    print(f"\n🚀 Running fast discovery (files only, no counting)...")
    import time

    start = time.time()
    manifest_fast = ingest.discover_files(config, session_data)
    elapsed_fast = time.time() - start

    print(f"   ✓ Discovery completed in {elapsed_fast * 1000:.1f} ms")
    print(f"\n   Discovered Files:")
    print(f"      Cameras: {len(manifest_fast.cameras)}")
    for cam in manifest_fast.cameras:
        video_count = len(cam.video_files) if cam.video_files else 0
        print(f"         - {cam.camera_id}: {video_count} video(s), " f"frame_count={cam.frame_count or 'None'}")

    print(f"      TTLs: {len(manifest_fast.ttls)}")
    for ttl in manifest_fast.ttls:
        file_count = len(ttl.files) if ttl.files else 0
        print(f"         - {ttl.ttl_id}: {file_count} file(s)")

    print(f"\n   💡 Use fast mode for:")
    print(f"      - Quick sanity checks")
    print(f"      - File existence validation")
    print(f"      - Pre-flight checks before heavy processing")

    # =========================================================================
    # PHASE 3: Slow Counting
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: Slow Counting")
    print("=" * 80)

    print(f"\n⏱️  Running slow counting (ffprobe + TTL read)...")
    start = time.time()
    manifest = ingest.populate_manifest_counts(manifest_fast)
    elapsed_slow = time.time() - start

    print(f"   ✓ Counting completed in {elapsed_slow * 1000:.1f} ms")
    print(f"   ⚡ Speedup: {elapsed_slow / elapsed_fast:.1f}x slower than fast mode")

    print(f"\n   Frame Counts:")
    for cam in manifest.cameras:
        print(f"      - {cam.camera_id}: {cam.frame_count} frames")

    print(f"\n   TTL Pulse Counts:")
    for cam in manifest.cameras:
        if cam.ttl_id and cam.ttl_pulse_count is not None:
            print(f"      - {cam.ttl_id} (for {cam.camera_id}): {cam.ttl_pulse_count} pulses")

    # =========================================================================
    # PHASE 4: Verification
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: Verification")
    print("=" * 80)

    print(f"\n✅ Verifying frame/TTL alignment (tolerance={tolerance})...")
    verification = ingest.verify_manifest(manifest, tolerance=tolerance)

    print(f"\n   Overall Status: {verification.status}")

    print(f"\n   Per-Camera Results:")
    for cam in verification.camera_results:
        # Compute mismatch string
        if cam.mismatch > 0:
            mismatch_str = f"+{cam.mismatch}"
        elif cam.mismatch < 0:
            mismatch_str = f"{cam.mismatch}"
        else:
            mismatch_str = "0"

        # Status icon
        if cam.status == "OK":
            icon = "✅"
        elif cam.status == "WARN":
            icon = "⚠️ "
        else:
            icon = "❌"

        print(f"      {icon} {cam.camera_id}:")
        print(f"         Frames: {cam.frame_count}")
        print(f"         TTL Pulses: {cam.ttl_pulse_count}")
        print(f"         Mismatch: {mismatch_str}")
        print(f"         Status: {cam.status}")
        print(f"         Verifiable: {cam.verifiable}")

    # =========================================================================
    # PHASE 5: Verification Logic Explanation
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 5: Verification Logic")
    print("=" * 80)

    print(f"\n📚 How Verification Works:")
    print(f"\n   1. For each camera:")
    print(f"      - Compute mismatch = frame_count - ttl_pulse_count")
    print(f"      - Check if abs(mismatch) <= tolerance")
    print(f"\n   2. Status assignment:")
    print(f"      - OK: abs(mismatch) <= tolerance")
    print(f"      - WARN: mismatch != 0 but within tolerance")
    print(f"      - FAIL: abs(mismatch) > tolerance")
    print(f"\n   3. Overall status:")
    print(f"      - success: All cameras OK or WARN")
    print(f"      - failure: Any camera FAIL")
    print(f"\n   4. Verifiable flag:")
    print(f"      - True: Camera has both frames and TTL")
    print(f"      - False: Missing frames or TTL (e.g., nominal rate only)")

    print(f"\n   Current Tolerance: {tolerance}")
    print(f"   Recommendation: Set based on expected recording precision")
    print(f"      - Strict (0-2): High-precision experiments")
    print(f"      - Moderate (3-10): Typical behavioral recordings")
    print(f"      - Loose (>10): Exploratory or noisy data")

    # =========================================================================
    # PHASE 6: Write Outputs
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 6: Write Outputs")
    print("=" * 80)

    output_dir = output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write verification summary
    verification_path = output_dir / "verification_summary.json"
    ingest.write_verification_summary(verification, verification_path)
    print(f"\n   ✓ verification_summary.json: {verification_path}")

    # Write full manifest for inspection
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest.model_dump(), f, indent=2)
    print(f"   ✓ manifest.json: {manifest_path}")

    # Write timing stats
    timing_path = output_dir / "timing_stats.json"
    timing_stats = {
        "fast_discovery_ms": elapsed_fast * 1000,
        "slow_counting_ms": elapsed_slow * 1000,
        "speedup_factor": elapsed_slow / elapsed_fast if elapsed_fast > 0 else None,
    }
    with open(timing_path, "w") as f:
        json.dump(timing_stats, f, indent=2)
    print(f"   ✓ timing_stats.json: {timing_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n📊 Ingest Stats:")
    print(f"   ✓ Session: {session_data.session.id}")
    print(f"   ✓ Cameras: {len(manifest.cameras)}")
    print(f"   ✓ Total Frames: {sum(c.frame_count for c in manifest.cameras if c.frame_count)}")
    print(f"   ✓ Total Pulses: {sum(c.ttl_pulse_count for c in manifest.cameras if c.ttl_pulse_count)}")
    print(f"   ✓ Verification: {verification.status}")

    print(f"\n⏱️  Performance:")
    print(f"   ✓ Fast discovery: {elapsed_fast * 1000:.1f} ms")
    print(f"   ✓ Slow counting: {elapsed_slow * 1000:.1f} ms")
    print(f"   ✓ Slowdown: {elapsed_slow / elapsed_fast:.1f}x")

    artifacts = {
        "config": session.config_path,
        "session": session.session_path,
        "manifest": manifest_path,
        "verification_summary": verification_path,
        "timing_stats": timing_path,
    }

    print(f"\n📁 Artifacts:")
    for name, path in artifacts.items():
        print(f"   ✓ {name}: {path}")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nKey Takeaways:")
    print("  - Fast discovery is ~100x faster than counting")
    print("  - Use fast mode for pre-flight checks")
    print("  - Verification tolerance depends on experiment requirements")
    print("  - Sidecars provide full observability")

    print("\nNext Steps:")
    print("  - Try different --tolerance values (0, 5, 10, 100)")
    print("  - Inspect manifest.json to understand data structure")
    print("  - Use this pattern for real data quality checks")

    return artifacts


if __name__ == "__main__":
    settings = ExampleSettings()
    run_pipeline(settings)
