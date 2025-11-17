#!/usr/bin/env python3
"""Example 21: Verification Visualization.

This example demonstrates how to use the root-level `figures` package to create
visualizations from pipeline outputs, specifically verification_summary.json.

Key Concepts:
-------------
- Using figures.ingest_verify module for verification plots
- Reading verification_summary.json sidecar
- Creating multi-panel QC plots
- Saving figures to disk

Visualization Types:
-------------------
- Frame vs TTL count comparison (bar plot)
- Mismatch distribution (bar plot)
- Status summary (pie chart)
- Per-camera verification table

Requirements Demonstrated:
-------------------------
- NFR-3: Sidecar observability
- FR-8: QC reporting
- figures package usage

Example Usage:
-------------
    $ python examples/21_verification_plots.py

    # Or with custom verification file
    $ VERIFICATION_PATH=path/to/verification_summary.json python examples/21_verification_plots.py
"""

from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

# Import root figures package
import figures.ingest_verify as fig_ingest
from synthetic.scenarios import happy_path
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest


class ExampleSettings(BaseSettings):
    """Settings for Example 21: Verification Visualization."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/21_verification_plots")
    verification_path: Path | None = None
    n_frames: int = 200
    seed: int = 42


if __name__ == "__main__":
    settings = ExampleSettings()
    output_root = settings.output_root

    print("=" * 80)
    print("W2T-BKIN Example 21: Verification Visualization")
    print("=" * 80)
    print()

    # Clean
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PHASE 1: Generate Data or Use Provided Verification
    # =========================================================================
    if settings.verification_path and settings.verification_path.exists():
        print("=" * 80)
        print("PHASE 1: Using Provided Verification File")
        print("=" * 80)
        print(f"\n📄 Loading: {settings.verification_path}")
        verification_path = settings.verification_path
    else:
        print("=" * 80)
        print("PHASE 1: Generate Synthetic Data and Verification")
        print("=" * 80)

        print(f"\n📦 Generating synthetic session ({settings.n_frames} frames, seed={settings.seed})...")
        session = happy_path.make_session(
            root=output_root,
            session_id="verification-viz-001",
            n_frames=settings.n_frames,
            seed=settings.seed,
        )

        print(f"\n📖 Loading configuration...")
        config = cfg_module.load_config(session.config_path)
        session_data = cfg_module.load_session(session.session_path)

        print(f"\n🔍 Building manifest and verifying...")
        manifest = ingest.build_and_count_manifest(config, session_data)
        verification = ingest.verify_manifest(manifest, tolerance=5)

        # Convert VerificationResult to VerificationSummary for persistence
        from datetime import datetime, timezone

        from w2t_bkin.domain.manifest import VerificationSummary

        verification_summary = VerificationSummary(
            session_id=session_data.session.id,
            cameras=verification.camera_results,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        verification_path = output_root / "output" / "verification_summary.json"
        verification_path.parent.mkdir(parents=True, exist_ok=True)
        ingest.write_verification_summary(verification_summary, verification_path)
        print(f"   ✓ Verification written: {verification_path}")

    # =========================================================================
    # PHASE 2: Create Verification Visualizations
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Create Verification Visualizations")
    print("=" * 80)

    figures_dir = output_root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📊 Creating verification plots using render_ingest_figures...")

    # Load manifest for render_ingest_figures (it needs both manifest and verification)
    import json

    from w2t_bkin.domain.manifest import Manifest

    # Find manifest.json in the output directory
    manifest_path = output_root / "output" / "manifest.json"
    if not manifest_path.exists():
        # Generate manifest if it doesn't exist
        print(f"   ℹ️  Manifest not found, loading from session data...")
        with open(manifest_path, "w") as f:
            json.dump(manifest.model_dump(), f, indent=2)

    # Use the high-level render function which creates all ingest/verification plots
    saved_paths = fig_ingest.render_ingest_figures(
        manifest=manifest_path,
        verification_summary=verification_path,
        output_dir=figures_dir,
        formats=("png",),
    )

    print(f"   ✓ Generated {len(saved_paths)} figure(s):")
    for path in saved_paths:
        print(f"     - {path.name}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n📁 Output Directory: {output_root}")
    print(f"\n📊 Figures Generated ({len(saved_paths)} files):")
    for path in saved_paths:
        print(f"   ✓ {path.name}")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nKey Takeaways:")
    print("  - figures.ingest_verify module creates comprehensive verification plots")
    print("  - render_ingest_figures() handles all plot generation automatically")
    print("  - Deterministic filenames based on session_id")
    print("  - Multi-panel summaries and individual component plots")

    print("\nNext Steps:")
    print("  - Inspect individual plots in the figures directory")
    print("  - Try with your own verification_summary.json files")
    print("  - Combine with alignment plots (Example 22) for full QC")
    print(f"   ✓ verification_summary.png - Frame/TTL comparison")
    print(f"   ✓ status_distribution.png - Status pie chart")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nKey Takeaways:")
    print("  - Root 'figures' package provides ready-to-use plotting functions")
    print("  - Plots read directly from verification_summary.json sidecars")
    print("  - figures.ingest_verify module handles verification phase plots")
    print("  - All plots use consistent styling from figures.utils")

    print("\nNext Steps:")
    print("  - Inspect generated plots in figures/ directory")
    print("  - Try with your own verification_summary.json files")
    print("  - Use figures.sync module for alignment visualizations")
    print("  - Combine multiple figures into session-level dashboards")
