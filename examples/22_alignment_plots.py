#!/usr/bin/env python3
"""Example 22: Alignment and Jitter Visualization.

This example demonstrates how to use the root-level `figures` package to create
alignment and jitter visualizations from alignment_stats.json sidecars.

Key Concepts:
-------------
- Using figures.sync module for alignment plots
- Reading alignment_stats.json sidecar
- Visualizing jitter distributions and metrics
- Comparing against jitter budgets

Visualization Types:
-------------------
- Jitter histogram with budget threshold
- Jitter cumulative distribution function (CDF)
- Alignment summary panel
- Jitter vs time series (if available)

Requirements Demonstrated:
-------------------------
- FR-TB-1..6: Timebase and alignment
- A17: Jitter budget enforcement
- NFR-3: Sidecar observability
- figures package usage

Example Usage:
-------------
    $ python examples/22_alignment_plots.py

    # Or with custom alignment file
    $ ALIGNMENT_PATH=path/to/alignment_stats.json python examples/22_alignment_plots.py
"""

import json
from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

# Import root figures package
import figures.sync as fig_sync
from synthetic.scenarios import happy_path, jitter_exceeds_budget
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest
from w2t_bkin.domain.alignment import AlignmentStats
from w2t_bkin.sync import compute_alignment, create_timebase_provider


class ExampleSettings(BaseSettings):
    """Settings for Example 22: Alignment and Jitter Visualization."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/22_alignment_plots")
    alignment_path: Path | None = None
    n_frames: int = 200
    seed: int = 42
    jitter_budget_ms: float = 2.0
    scenario: str = "happy_path"  # or "jitter_exceeds"


if __name__ == "__main__":
    settings = ExampleSettings()
    output_root = settings.output_root

    print("=" * 80)
    print("W2T-BKIN Example 22: Alignment and Jitter Visualization")
    print("=" * 80)
    print()

    # Clean
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PHASE 1: Generate Data or Use Provided Alignment Stats
    # =========================================================================
    if settings.alignment_path and settings.alignment_path.exists():
        print("=" * 80)
        print("PHASE 1: Using Provided Alignment File")
        print("=" * 80)
        print(f"\n📄 Loading: {settings.alignment_path}")
        alignment_path = settings.alignment_path

        # Load alignment stats
        with open(alignment_path) as f:
            alignment_data = json.load(f)
        alignment_stats = AlignmentStats(**alignment_data)

    else:
        print("=" * 80)
        print(f"PHASE 1: Generate Synthetic Data ({settings.scenario})")
        print("=" * 80)

        # Select scenario
        if settings.scenario == "jitter_exceeds":
            scenario_fn = jitter_exceeds_budget.make_session
            print(f"\n📦 Using jitter_exceeds_budget scenario...")
        else:
            scenario_fn = happy_path.make_session
            print(f"\n📦 Using happy_path scenario...")

        session = scenario_fn(
            root=output_root,
            session_id=f"alignment-viz-{settings.scenario}",
            n_frames=settings.n_frames,
            seed=settings.seed,
        )

        print(f"\n📖 Loading configuration...")
        config = cfg_module.load_config(session.config_path)
        session_data = cfg_module.load_session(session.session_path)

        # Override jitter budget
        jitter_budget_s = settings.jitter_budget_ms / 1000.0
        config.timebase.jitter_budget_s = jitter_budget_s
        print(f"   ⚙️  Jitter budget: {settings.jitter_budget_ms:.3f} ms")

        print(f"\n🔍 Building manifest...")
        manifest = ingest.build_and_count_manifest(config, session_data)

        print(f"\n⏱️  Creating timebase and aligning...")
        timebase_provider = create_timebase_provider(config, manifest)
        alignment_stats = compute_alignment(manifest, timebase_provider, config)

        print(f"   ✓ Max jitter: {alignment_stats.max_jitter_s * 1000:.3f} ms")
        print(f"   ✓ P95 jitter: {alignment_stats.p95_jitter_s * 1000:.3f} ms")

        # Check budget
        if alignment_stats.max_jitter_s > jitter_budget_s:
            print(f"   ❌ Budget exceeded!")
        else:
            print(f"   ✅ Within budget")

        # Write alignment stats
        alignment_path = output_root / "output" / "alignment_stats.json"
        alignment_path.parent.mkdir(parents=True, exist_ok=True)
        with open(alignment_path, "w") as f:
            json.dump(alignment_stats.model_dump(), f, indent=2)
        print(f"\n   ✓ Alignment stats written: {alignment_path}")

    # =========================================================================
    # PHASE 2: Create Alignment Visualizations
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Create Alignment Visualizations")
    print("=" * 80)

    figures_dir = output_root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📊 Creating alignment plots...")

    # Plot 1: Jitter histogram
    print(f"   Creating: jitter_histogram.png")
    import matplotlib.pyplot as plt

    fig1, ax1 = plt.subplots(figsize=(10, 6))
    fig_sync.plot_jitter_histogram(
        alignment_stats=alignment_stats,
        jitter_budget_s=settings.jitter_budget_ms / 1000.0,
        ax=ax1,
    )
    fig1_path = figures_dir / "jitter_histogram.png"
    fig1.savefig(fig1_path, dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print(f"   ✓ Saved: {fig1_path}")

    # Plot 2: Jitter CDF
    print(f"   Creating: jitter_cdf.png")
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    fig_sync.plot_jitter_cdf(
        alignment_stats=alignment_stats,
        jitter_budget_s=settings.jitter_budget_ms / 1000.0,
        ax=ax2,
    )
    fig2_path = figures_dir / "jitter_cdf.png"
    fig2.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"   ✓ Saved: {fig2_path}")

    # Plot 3: Alignment summary panel
    print(f"   Creating: alignment_summary.png")
    fig3 = fig_sync.plot_alignment_summary_panel(
        alignment_stats=alignment_stats,
        jitter_budget_s=settings.jitter_budget_ms / 1000.0,
    )
    fig3_path = figures_dir / "alignment_summary.png"
    fig3.savefig(fig3_path, dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print(f"   ✓ Saved: {fig3_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n📁 Output Directory: {output_root}")
    print(f"\n📊 Alignment Stats:")
    print(f"   ✓ Timebase source: {alignment_stats.timebase_source}")
    print(f"   ✓ Mapping strategy: {alignment_stats.mapping}")
    print(f"   ✓ Offset: {alignment_stats.offset_s:.6f} s")
    print(f"   ✓ Max jitter: {alignment_stats.max_jitter_s * 1000:.3f} ms")
    print(f"   ✓ P95 jitter: {alignment_stats.p95_jitter_s * 1000:.3f} ms")
    print(f"   ✓ Aligned samples: {alignment_stats.aligned_samples}")

    print(f"\n📊 Figures Generated:")
    print(f"   ✓ jitter_histogram.png - Jitter distribution with budget")
    print(f"   ✓ jitter_cdf.png - Cumulative distribution")
    print(f"   ✓ alignment_summary.png - Multi-panel summary")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nKey Takeaways:")
    print("  - figures.sync module handles alignment and jitter plots")
    print("  - Jitter budget visualization shows pass/fail clearly")
    print("  - CDF plots help understand jitter distribution shape")
    print("  - Summary panels combine multiple metrics in one view")

    print("\nNext Steps:")
    print("  - Try SCENARIO=jitter_exceeds to see budget violations")
    print("  - Adjust JITTER_BUDGET_MS to see threshold effects")
    print("  - Use with your own alignment_stats.json files")
    print("  - Combine with verification plots for complete QC")
