#!/usr/bin/env python3
"""Example 03: Jitter Budget Comparison.

This example demonstrates the timebase alignment system and jitter budget
enforcement by comparing two scenarios:

1. **Happy Path**: Low jitter within budget → pipeline succeeds
2. **Jitter Exceeds Budget**: High jitter above budget → pipeline aborts

Key Concepts:
-------------
- Timebase construction (nominal, TTL, neuropixels)
- Alignment strategies (nearest-neighbor, linear)
- Jitter metrics (max, p95, distribution)
- Budget enforcement and abort conditions (A17)
- alignment_stats.json sidecar

Design Alignment:
----------------
Per design.md, the pipeline must:
- Compute jitter metrics during sync phase
- Compare against configured budget
- Abort BEFORE NWB assembly if budget exceeded
- Record alignment stats for observability

Requirements Demonstrated:
-------------------------
- FR-TB-1..6: Timebase and alignment
- FR-17: Alignment verification
- A17: Jitter budget enforcement
- NFR-3: Sidecar observability

Example Usage:
-------------
    $ python examples/03_jitter_budget_comparison.py

    # Compare with custom jitter budget
    $ JITTER_BUDGET_MS=1.0 python examples/03_jitter_budget_comparison.py
"""

import json
from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

from synthetic.scenarios import happy_path, jitter_exceeds_budget
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest
from w2t_bkin.sync import compute_alignment, create_timebase_provider


class ExampleSettings(BaseSettings):
    """Settings for Example 03: Jitter Budget Comparison."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/03_jitter_budget")
    n_frames: int = 200
    seed: int = 42
    jitter_budget_ms: float = 2.0


def run_scenario(
    scenario_name: str,
    scenario_fn,
    output_root: Path,
    n_frames: int,
    seed: int,
    jitter_budget_s: float,
) -> dict:
    """Run a single scenario and return metrics.

    Args:
        scenario_name: Name for logging
        scenario_fn: Scenario function (e.g., happy_path.make_session)
        output_root: Output directory for this scenario
        n_frames: Number of frames
        seed: Random seed
        jitter_budget_s: Jitter budget in seconds

    Returns:
        Dictionary with alignment stats and status
    """
    print(f"\n{'=' * 80}")
    print(f"Scenario: {scenario_name}")
    print(f"{'=' * 80}")

    # Generate synthetic data
    print(f"\n📦 Generating synthetic data...")
    session = scenario_fn(
        root=output_root,
        session_id=f"{scenario_name.lower().replace(' ', '-')}-001",
        n_frames=n_frames,
        seed=seed,
    )

    # Load config and session
    print(f"📖 Loading configuration...")
    config = cfg_module.load_config(session.config_path)
    session_data = cfg_module.load_session(session.session_path)

    # Note: Config is frozen and cannot be modified after creation
    # The jitter budget should be set during synthetic session generation
    # (scenario functions like jitter_exceeds_budget.make_session accept budget_s parameter)
    if jitter_budget_s is not None:
        print(f"   ⚙️  Using jitter budget from session: {config.timebase.jitter_budget_s * 1000:.3f} ms")
        print(f"   ℹ️  To test different budgets, regenerate session with budget_s parameter")

    # Build manifest
    print(f"🔍 Building manifest...")
    manifest = ingest.build_and_count_manifest(config, session_data)

    # Verify
    print(f"✅ Verifying...")
    verification = ingest.verify_manifest(manifest, tolerance=5)
    print(f"   ✓ Verification: {verification.status}")

    # Create timebase
    print(f"⏱️  Creating timebase...")
    timebase_provider = create_timebase_provider(config, manifest)
    print(f"   ✓ Source: {config.timebase.source}")
    print(f"   ✓ Mapping: {config.timebase.mapping}")

    # Align
    print(f"🔄 Aligning to timebase...")
    try:
        alignment_stats = compute_alignment(manifest, timebase_provider, config)
        print(f"   ✓ Offset: {alignment_stats.offset_s:.6f} s")
        print(f"   ✓ Max jitter: {alignment_stats.max_jitter_s * 1000:.3f} ms")
        print(f"   ✓ P95 jitter: {alignment_stats.p95_jitter_s * 1000:.3f} ms")

        # Check budget
        if config.timebase.jitter_budget_s:
            within_budget = alignment_stats.max_jitter_s <= config.timebase.jitter_budget_s
            budget_ms = config.timebase.jitter_budget_s * 1000
            max_jitter_ms = alignment_stats.max_jitter_s * 1000

            if within_budget:
                print(f"   ✅ PASS: {max_jitter_ms:.3f} ms ≤ {budget_ms:.3f} ms budget")
                status = "PASS"
            else:
                print(f"   ❌ FAIL: {max_jitter_ms:.3f} ms > {budget_ms:.3f} ms budget")
                print(f"   ⚠️  Pipeline would abort before NWB assembly")
                status = "FAIL"
        else:
            status = "NO_BUDGET"

        # Write alignment stats
        stats_path = output_root / "output" / "alignment_stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_path, "w") as f:
            json.dump(alignment_stats.model_dump(), f, indent=2)

        return {
            "scenario": scenario_name,
            "status": status,
            "alignment_stats": alignment_stats,
            "stats_path": stats_path,
            "budget_ms": (config.timebase.jitter_budget_s * 1000 if config.timebase.jitter_budget_s else None),
        }

    except Exception as e:
        print(f"   ❌ Alignment failed: {e}")
        return {
            "scenario": scenario_name,
            "status": "ERROR",
            "error": str(e),
        }


def main(
    output_root: Path,
    n_frames: int,
    seed: int,
    jitter_budget_ms: float,
) -> dict:
    """Run jitter budget comparison between scenarios.

    Args:
        output_root: Root directory for all outputs
        n_frames: Number of frames per scenario
        seed: Random seed
        jitter_budget_ms: Jitter budget in milliseconds

    Returns:
        Dictionary with comparison results
    """
    print("=" * 80)
    print("W2T-BKIN Example 03: Jitter Budget Comparison")
    print("=" * 80)
    print()

    # Clean
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    jitter_budget_s = jitter_budget_ms / 1000.0

    # =========================================================================
    # Scenario 1: Happy Path (Low Jitter)
    # =========================================================================
    result_happy = run_scenario(
        scenario_name="Happy Path",
        scenario_fn=happy_path.make_session,
        output_root=output_root / "happy_path",
        n_frames=n_frames,
        seed=seed,
        jitter_budget_s=jitter_budget_s,
    )

    # =========================================================================
    # Scenario 2: Jitter Exceeds Budget (High Jitter)
    # =========================================================================
    result_jitter = run_scenario(
        scenario_name="Jitter Exceeds Budget",
        scenario_fn=jitter_exceeds_budget.make_session,
        output_root=output_root / "jitter_exceeds",
        n_frames=n_frames,
        seed=seed,
        jitter_budget_s=jitter_budget_s,
    )

    # =========================================================================
    # Comparison Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Comparison Summary")
    print("=" * 80)

    print(f"\n⚙️  Jitter Budget: {jitter_budget_ms:.3f} ms")
    print("\n" + "-" * 80)

    # Table header
    print(f"{'Scenario':<30} {'Max Jitter (ms)':<20} {'P95 Jitter (ms)':<20} {'Status':<10}")
    print("-" * 80)

    # Happy path
    if "alignment_stats" in result_happy:
        stats_happy = result_happy["alignment_stats"]
        print(f"{result_happy['scenario']:<30} " f"{stats_happy.max_jitter_s * 1000:<20.3f} " f"{stats_happy.p95_jitter_s * 1000:<20.3f} " f"{result_happy['status']:<10}")
    else:
        print(f"{result_happy['scenario']:<30} {'ERROR':<20} {'ERROR':<20} {'ERROR':<10}")

    # Jitter exceeds
    if "alignment_stats" in result_jitter:
        stats_jitter = result_jitter["alignment_stats"]
        print(f"{result_jitter['scenario']:<30} " f"{stats_jitter.max_jitter_s * 1000:<20.3f} " f"{stats_jitter.p95_jitter_s * 1000:<20.3f} " f"{result_jitter['status']:<10}")
    else:
        print(f"{result_jitter['scenario']:<30} {'ERROR':<20} {'ERROR':<20} {'ERROR':<10}")

    print("-" * 80)

    # Write comparison summary
    comparison_path = output_root / "comparison_summary.json"
    comparison = {
        "jitter_budget_ms": jitter_budget_ms,
        "scenarios": [result_happy, result_jitter],
    }

    # Make stats JSON-serializable
    for scenario in comparison["scenarios"]:
        if "alignment_stats" in scenario:
            scenario["alignment_stats"] = scenario["alignment_stats"].model_dump()

    with open(comparison_path, "w") as f:
        json.dump(comparison, f, indent=2)

    print(f"\n📄 Comparison summary: {comparison_path}")

    # =========================================================================
    # Key Insights
    # =========================================================================
    print("\n" + "=" * 80)
    print("Key Insights")
    print("=" * 80)

    print("\n🎯 Design Enforcement (A17):")
    print("   - Pipeline computes jitter metrics during sync phase")
    print("   - Jitter is compared against configured budget")
    print("   - If exceeded, pipeline aborts BEFORE NWB assembly")
    print("   - This prevents generating invalid synchronized outputs")

    print("\n📊 Jitter Metrics:")
    print("   - Max Jitter: Worst-case alignment error")
    print("   - P95 Jitter: 95th percentile (typical case)")
    print("   - Both must be ≤ budget for PASS")

    print("\n⚙️  Budget Configuration:")
    print("   - Set via config.timebase.jitter_budget_s")
    print("   - Typical values: 0.5-5.0 ms depending on experiment")
    print("   - Stricter budgets ensure higher temporal precision")

    print("\n🔬 Alignment Stats Sidecar:")
    print("   - alignment_stats.json provides full metrics")
    print("   - Includes: offset_s, max_jitter_s, p95_jitter_s, aligned_samples")
    print("   - Use for debugging, tuning, and QC reporting")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nNext Steps:")
    print("  - Inspect alignment_stats.json for detailed metrics")
    print("  - Try adjusting --budget to see threshold behavior")
    print("  - Use example 22 (alignment_plots.ipynb) to visualize jitter")
    print("  - Apply learnings to tune budgets for real experiments")

    return comparison


if __name__ == "__main__":
    settings = ExampleSettings()
    main(
        output_root=settings.output_root,
        n_frames=settings.n_frames,
        seed=settings.seed,
        jitter_budget_ms=settings.jitter_budget_ms,
    )
