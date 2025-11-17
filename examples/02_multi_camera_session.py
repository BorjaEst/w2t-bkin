#!/usr/bin/env python3
"""Example 02: Multi-Camera Session.

This example demonstrates manifest creation and verification for a session with
multiple cameras and TTL channels. It shows how the pipeline handles complex
camera/TTL topologies and validates cross-references.

Key Concepts:
-------------
- Multi-camera manifest generation
- Multiple TTL channels
- Per-camera verification
- Camera-to-TTL mapping validation
- Detailed verification reporting

Differences from Single Camera:
-------------------------------
- Multiple ManifestCamera entries in manifest
- Multiple ManifestTTL entries with distinct IDs
- Per-camera frame/TTL verification
- Validation of camera.ttl_id references

Use Cases:
----------
- Body camera + face camera setups
- Multi-view triangulation
- Simultaneous behavior + neural recordings
- Complex experimental rigs

Requirements Demonstrated:
-------------------------
- FR-3: Multi-file discovery
- FR-13: Multi-camera frame counting
- FR-15: Multi-channel TTL counting
- FR-16: Per-camera verification
- A6, A7: Manifest and verification

Example Usage:
-------------
    $ python examples/02_multi_camera_session.py

    # Or with custom cameras
    $ N_CAMERAS=4 N_FRAMES=300 python examples/02_multi_camera_session.py
"""

import json
from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

from synthetic.scenarios import multi_camera
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest


class ExampleSettings(BaseSettings):
    """Settings for Example 02: Multi-Camera Session."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/02_multi_camera")
    n_cameras: int = 2
    n_frames: int = 200
    seed: int = 42


def run_pipeline(settings: ExampleSettings) -> dict:
    """Run multi-camera manifest and verification example.

    Args:
        settings: Example settings with output paths and parameters

    Returns:
        Dictionary with paths to generated artifacts
    """
    output_root = settings.output_root
    n_cameras = settings.n_cameras
    n_frames = settings.n_frames
    seed = settings.seed

    print("=" * 80)
    print("W2T-BKIN Example 02: Multi-Camera Session")
    print("=" * 80)
    print()

    # Clean and setup
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PHASE 0: Generate Multi-Camera Synthetic Data
    # =========================================================================
    print("=" * 80)
    print("PHASE 0: Generate Multi-Camera Synthetic Data")
    print("=" * 80)

    print(f"\n📦 Generating {n_cameras}-camera session with {n_frames} frames each...")

    session = multi_camera.make_session(
        root=output_root,
        session_id="multi-cam-001",
        n_cameras=n_cameras,
        n_frames=n_frames,
        seed=seed,
    )

    print(f"   ✓ Config: {session.config_path}")
    print(f"   ✓ Session: {session.session_path}")
    print(f"   ✓ Cameras: {len(session.videos)}")
    for i, video in enumerate(session.videos):
        print(f"     - Camera {i}: {video.name}")
    print(f"   ✓ TTL channels: {len(session.ttls)}")
    for i, ttl in enumerate(session.ttls):
        print(f"     - TTL {i}: {ttl.name}")

    # =========================================================================
    # PHASE 1: Load Config and Session
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: Load Config and Session")
    print("=" * 80)

    print("\n📖 Loading configuration and session metadata...")
    config = cfg_module.load_config(session.config_path)
    session_data = cfg_module.load_session(session.session_path)

    print(f"   ✓ Project: {config.project.name}")
    print(f"   ✓ Session: {session_data.session.id}")
    print(f"   ✓ Cameras in session.toml: {len(session_data.cameras)}")
    for cam in session_data.cameras:
        ttl_ref = f" → {cam.ttl_id}" if cam.ttl_id else " (no TTL)"
        print(f"     - {cam.camera_id}{ttl_ref}")
    print(f"   ✓ TTLs in session.toml: {len(session_data.ttls)}")
    for ttl in session_data.ttls:
        print(f"     - {ttl.ttl_id}")

    # =========================================================================
    # PHASE 2: Fast Discovery (No Counting)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Fast Discovery (No Counting)")
    print("=" * 80)

    print("\n🔍 Discovering files without counting (fast mode)...")
    manifest_fast = ingest.discover_files(config, session_data)

    print(f"   ✓ Cameras discovered: {len(manifest_fast.cameras)}")
    for cam in manifest_fast.cameras:
        video_count = len(cam.video_files) if cam.video_files else 0
        print(f"     - {cam.camera_id}: {video_count} video file(s), frame_count=None")

    print(f"   ✓ TTLs discovered: {len(manifest_fast.ttls)}")
    for ttl in manifest_fast.ttls:
        file_count = len(ttl.files) if ttl.files else 0
        print(f"     - {ttl.ttl_id}: {file_count} TTL file(s), ttl_pulse_count=None")

    print("\n   💡 Note: Fast mode skips frame/TTL counting for speed.")
    print("      Use this for quick validation before heavy processing.")

    # =========================================================================
    # PHASE 3: Slow Counting
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: Slow Counting")
    print("=" * 80)

    print("\n⏱️  Counting frames and TTL pulses (slow mode)...")
    manifest = ingest.populate_manifest_counts(manifest_fast)

    print(f"   ✓ Frame counts populated:")
    for cam in manifest.cameras:
        print(f"     - {cam.camera_id}: {cam.frame_count} frames")

    print(f"   ✓ TTL pulse counts populated:")
    for ttl in manifest.ttls:
        print(f"     - {ttl.ttl_id}: {ttl.ttl_pulse_count} pulses")

    # =========================================================================
    # PHASE 4: Cross-Reference Validation
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: Cross-Reference Validation")
    print("=" * 80)

    print("\n🔗 Validating camera → TTL references...")
    try:
        ingest.validate_ttl_references(manifest)
        print("   ✓ All camera TTL references are valid")
    except ValueError as e:
        print(f"   ✗ Validation failed: {e}")
        return {}

    # Show mapping
    print("\n   Camera → TTL Mapping:")
    for cam in manifest.cameras:
        if cam.ttl_id:
            ttl = next((t for t in manifest.ttls if t.ttl_id == cam.ttl_id), None)
            if ttl:
                print(f"     {cam.camera_id} → {cam.ttl_id} " f"({cam.frame_count} frames vs {ttl.ttl_pulse_count} pulses)")
        else:
            print(f"     {cam.camera_id} → (no TTL)")

    # =========================================================================
    # PHASE 5: Per-Camera Verification
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 5: Per-Camera Verification")
    print("=" * 80)

    print("\n✅ Verifying frame/TTL alignment per camera...")
    verification = ingest.verify_manifest(manifest, tolerance=5)

    print(f"   ✓ Overall status: {verification.status}")
    print(f"   ✓ Generated at: {verification.generated_at}")

    print("\n   Per-Camera Results:")
    for cam_result in verification.cameras:
        mismatch_str = f"{cam_result.mismatch:+d}" if cam_result.mismatch != 0 else "0"

        # Status icon
        if cam_result.status == "OK":
            icon = "✅"
        elif cam_result.status == "WARN":
            icon = "⚠️ "
        else:
            icon = "❌"

        # Verifiable flag
        verifiable_str = "verifiable" if cam_result.verifiable else "not verifiable"

        print(
            f"     {icon} {cam_result.camera_id}:"
            f"\n        Frames: {cam_result.frame_count}"
            f"\n        TTL Pulses: {cam_result.ttl_pulse_count}"
            f"\n        Mismatch: {mismatch_str}"
            f"\n        Status: {cam_result.status} ({verifiable_str})"
        )

    # =========================================================================
    # PHASE 6: Write Verification Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 6: Write Verification Summary")
    print("=" * 80)

    verification_path = output_root / "output" / "verification_summary.json"
    verification_path.parent.mkdir(parents=True, exist_ok=True)
    ingest.write_verification_summary(verification, verification_path)

    print(f"\n📄 Verification summary written: {verification_path}")

    # Also write the manifest for inspection
    manifest_path = output_root / "output" / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest.model_dump(), f, indent=2)
    print(f"📄 Manifest written: {manifest_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n📊 Multi-Camera Session Stats:")
    print(f"   ✓ Cameras: {len(manifest.cameras)}")
    print(f"   ✓ TTL Channels: {len(manifest.ttls)}")
    print(f"   ✓ Total Frames: {sum(c.frame_count for c in manifest.cameras if c.frame_count)}")
    print(f"   ✓ Total Pulses: {sum(t.ttl_pulse_count for t in manifest.ttls if t.ttl_pulse_count)}")
    print(f"   ✓ Verification: {verification.status}")

    ok_count = sum(1 for c in verification.cameras if c.status == "OK")
    warn_count = sum(1 for c in verification.cameras if c.status == "WARN")
    fail_count = sum(1 for c in verification.cameras if c.status == "FAIL")

    print(f"\n   Camera Status Breakdown:")
    print(f"     - OK: {ok_count}")
    print(f"     - WARN: {warn_count}")
    print(f"     - FAIL: {fail_count}")

    artifacts = {
        "config": session.config_path,
        "session": session.session_path,
        "manifest": manifest_path,
        "verification_summary": verification_path,
    }

    print("\n📁 Artifacts:")
    for name, path in artifacts.items():
        print(f"   ✓ {name}: {path}")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("  - Fast discovery (no counting) is O(n) in file count")
    print("  - Slow counting (ffprobe + TTL read) is O(n*m) in data size")
    print("  - Per-camera verification allows mixed success/failure")
    print("  - TTL references are validated before processing")
    print("\nNext steps:")
    print("  - Try running with --cameras 4 for more complex topology")
    print("  - Inspect verification_summary.json for detailed metrics")
    print("  - Use this pattern for real multi-camera rigs")

    return artifacts


if __name__ == "__main__":
    settings = ExampleSettings()
    run_pipeline(settings)
