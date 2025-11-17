"""Example usage of the figures package.

This script demonstrates how to use the figures package to visualize
pipeline data at different stages.
"""

from pathlib import Path

# Example 1: High-level session overview
print("Example 1: Render complete session overview")
print("=" * 60)

# Assuming you have config and session loaded
try:
    from figures import render_session_overview
    from w2t_bkin.config import load_config, load_session

    config = load_config("configs/config.toml")
    session = load_session("tests/fixtures/sessions/session_example.toml")

    results = render_session_overview(
        config=config,
        session=session,
        outputs_root="data/interim",
        formats=("png",),  # Can use ('png', 'pdf') for multiple formats
    )

    print(f"\nGenerated figures by phase:")
    for phase, paths in results.items():
        print(f"  {phase}: {len(paths)} figures")

except Exception as e:
    print(f"Could not run example 1: {e}")

print("\n")

# Example 2: Phase-specific rendering
print("Example 2: Render ingest phase only")
print("=" * 60)

try:
    from figures import render_ingest_figures

    paths = render_ingest_figures(
        manifest="data/interim/SNA-145518_manifest.json",
        verification_summary="data/interim/SNA-145518_verification_summary.json",
        output_dir="reports/figures/ingest",
        tolerance=1,
        formats=("png",),
    )

    print(f"\nGenerated {len(paths)} ingest figures:")
    for path in paths:
        print(f"  - {path}")

except Exception as e:
    print(f"Could not run example 2: {e}")

print("\n")

# Example 3: Low-level plotting for custom figures
print("Example 3: Custom figure with low-level API")
print("=" * 60)

try:
    import json

    import matplotlib.pyplot as plt

    from figures.ingest_verify import plot_frame_vs_ttl_counts
    from figures.utils import save_figure
    from w2t_bkin.domain.manifest import Manifest, VerificationSummary

    # Load data
    with open("data/interim/SNA-145518_manifest.json") as f:
        manifest = Manifest(**json.load(f))

    with open("data/interim/SNA-145518_verification_summary.json") as f:
        verification_summary = VerificationSummary(**json.load(f))

    # Create custom figure
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_frame_vs_ttl_counts(manifest, verification_summary, tolerance=1, ax=ax)

    # Save with custom settings
    paths = save_figure(fig, "reports/figures/custom", "my_custom_plot", formats=("png", "pdf"), dpi=300)

    print(f"\nSaved custom figure to:")
    for path in paths:
        print(f"  - {path}")

except Exception as e:
    print(f"Could not run example 3: {e}")

print("\n")

# Example 4: Sync figures with jitter analysis
print("Example 4: Sync/alignment diagnostics")
print("=" * 60)

try:
    from figures import render_sync_figures

    paths = render_sync_figures(
        alignment_stats="data/interim/session_ttl_alignment_stats.json",
        output_dir="reports/figures/sync",
        jitter_budget_s=0.001,  # 1ms budget
        formats=("png",),
    )

    print(f"\nGenerated {len(paths)} sync figures:")
    for path in paths:
        print(f"  - {path}")

except Exception as e:
    print(f"Could not run example 4: {e}")

print("\n")

# Example 5: Using phase-specific convenience function
print("Example 5: Phase-specific convenience function")
print("=" * 60)

try:
    from figures import render_phase_figures

    paths = render_phase_figures(
        phase="ingest",
        session_id="SNA-145518",
        outputs_root="data/interim",
        output_dir="reports/figures/ingest_v2",
        tolerance=1,
    )

    print(f"\nGenerated {len(paths)} figures for ingest phase")

except Exception as e:
    print(f"Could not run example 5: {e}")

print("\n" + "=" * 60)
print("Examples complete!")
print("\nNote: Most examples will fail if you don't have the required")
print("data files. This script demonstrates the API patterns.")
