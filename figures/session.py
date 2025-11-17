"""Session-level figure orchestration module.

Provides high-level API for rendering comprehensive session overviews
that combine all phase-specific visualizations into a unified report.

This module coordinates:
- Ingest/verification figures
- Sync/alignment figures
- Optional modality figures (pose, facemap, events)
- NWB final output figures
- Synthetic comparisons (if applicable)
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from figures.events import render_events_figures
from figures.facemap import render_facemap_figures
from figures.ingest_verify import render_ingest_figures
from figures.nwb import render_nwb_figures
from figures.pose import render_pose_figures
from figures.sync import render_sync_figures
from figures.utils import ensure_output_dir
from w2t_bkin.domain.alignment import AlignmentStats
from w2t_bkin.domain.config import Config
from w2t_bkin.domain.manifest import Manifest, VerificationSummary
from w2t_bkin.domain.session import Session

# ============================================================================
# High-Level Session Overview API
# ============================================================================


def render_session_overview(
    config: Config,
    session: Session,
    outputs_root: Union[str, Path],
    manifest: Optional[Union[Manifest, str, Path]] = None,
    verification_summary: Optional[Union[VerificationSummary, str, Path]] = None,
    alignment_stats: Optional[Union[AlignmentStats, str, Path]] = None,
    nwb_path: Optional[Union[str, Path]] = None,
    formats: tuple[str, ...] = ("png",),
) -> Dict[str, List[Path]]:
    """Render comprehensive session overview with all available figures.

    Orchestrates rendering of all phase-specific figures based on available
    data. Automatically discovers sidecars and data products from outputs_root
    if not explicitly provided.

    Args:
        config: Config domain object
        session: Session domain object
        outputs_root: Root directory containing pipeline outputs
        manifest: Optional Manifest object or path (auto-discovered if None)
        verification_summary: Optional VerificationSummary or path (auto-discovered if None)
        alignment_stats: Optional AlignmentStats or path (auto-discovered if None)
        nwb_path: Optional path to NWB file (auto-discovered if None)
        formats: Output formats for all figures (e.g., ('png', 'pdf'))

    Returns:
        Dictionary mapping phase names to lists of saved figure paths:
        {
            'ingest': [Path, ...],
            'sync': [Path, ...],
            'pose': [Path, ...],
            'facemap': [Path, ...],
            'events': [Path, ...],
            'nwb': [Path, ...]
        }

    Example:
        >>> from w2t_bkin.config import load_config, load_session
        >>> config = load_config('config.toml')
        >>> session = load_session('session.toml')
        >>> results = render_session_overview(
        ...     config=config,
        ...     session=session,
        ...     outputs_root='data/interim',
        ...     formats=('png', 'pdf')
        ... )
        >>> print(f"Generated {sum(len(v) for v in results.values())} figures")
    """
    outputs_root = Path(outputs_root)
    session_id = session.session.id
    results: Dict[str, List[Path]] = {}

    # Prepare output directories
    figures_root = outputs_root / "figures"
    ingest_dir = figures_root / "ingest"
    sync_dir = figures_root / "sync"
    pose_dir = figures_root / "pose"
    facemap_dir = figures_root / "facemap"
    events_dir = figures_root / "events"
    nwb_dir = figures_root / "nwb"

    # ========================================================================
    # Phase 1: Ingest + Verify
    # ========================================================================

    try:
        # Auto-discover manifest and verification_summary if not provided
        if manifest is None:
            manifest_path = outputs_root / f"{session_id}_manifest.json"
            if manifest_path.exists():
                manifest = manifest_path
            else:
                print(f"Warning: Manifest not found at {manifest_path}, skipping ingest figures")
                manifest = None

        if verification_summary is None:
            verification_path = outputs_root / f"{session_id}_verification_summary.json"
            if verification_path.exists():
                verification_summary = verification_path
            else:
                print(f"Warning: Verification summary not found at {verification_path}, skipping ingest figures")
                verification_summary = None

        if manifest is not None and verification_summary is not None:
            print(f"Rendering ingest figures for {session_id}...")
            ingest_paths = render_ingest_figures(
                manifest=manifest, verification_summary=verification_summary, output_dir=ingest_dir, tolerance=config.verification.tolerance, formats=formats
            )
            results["ingest"] = ingest_paths
            print(f"  → Generated {len(ingest_paths)} ingest figures")
        else:
            results["ingest"] = []

    except Exception as e:
        print(f"Error rendering ingest figures: {e}")
        results["ingest"] = []

    # ========================================================================
    # Phase 2: Sync
    # ========================================================================

    try:
        # Auto-discover alignment_stats if not provided
        if alignment_stats is None:
            alignment_path = outputs_root / f"{session_id}_alignment_stats.json"
            if alignment_path.exists():
                alignment_stats = alignment_path
            else:
                print(f"Warning: Alignment stats not found at {alignment_path}, skipping sync figures")
                alignment_stats = None

        if alignment_stats is not None:
            print(f"Rendering sync figures for {session_id}...")
            jitter_budget = getattr(config.timebase, "jitter_budget_s", None)
            sync_paths = render_sync_figures(alignment_stats=alignment_stats, output_dir=sync_dir, jitter_budget_s=jitter_budget, formats=formats)
            results["sync"] = sync_paths
            print(f"  → Generated {len(sync_paths)} sync figures")
        else:
            results["sync"] = []

    except Exception as e:
        print(f"Error rendering sync figures: {e}")
        results["sync"] = []

    # ========================================================================
    # Phase 3: Optional Modalities
    # ========================================================================

    # Pose
    try:
        pose_bundle_path = outputs_root / f"{session_id}_pose_bundle.json"
        if pose_bundle_path.exists():
            print(f"Rendering pose figures for {session_id}...")
            pose_paths = render_pose_figures(pose_bundle=pose_bundle_path, output_dir=pose_dir, session_id=session_id, formats=formats)
            results["pose"] = pose_paths
            print(f"  → Generated {len(pose_paths)} pose figures")
        else:
            results["pose"] = []
    except Exception as e:
        print(f"Error rendering pose figures: {e}")
        results["pose"] = []

    # Facemap
    try:
        facemap_bundle_path = outputs_root / f"{session_id}_facemap_bundle.json"
        if facemap_bundle_path.exists():
            print(f"Rendering facemap figures for {session_id}...")
            facemap_paths = render_facemap_figures(facemap_bundle=facemap_bundle_path, output_dir=facemap_dir, session_id=session_id, formats=formats)
            results["facemap"] = facemap_paths
            print(f"  → Generated {len(facemap_paths)} facemap figures")
        else:
            results["facemap"] = []
    except Exception as e:
        print(f"Error rendering facemap figures: {e}")
        results["facemap"] = []

    # Events
    try:
        trials_events_path = outputs_root / f"{session_id}_trials_events.json"
        if trials_events_path.exists():
            print(f"Rendering events figures for {session_id}...")
            events_paths = render_events_figures(trials_events=trials_events_path, output_dir=events_dir, session_id=session_id, formats=formats)
            results["events"] = events_paths
            print(f"  → Generated {len(events_paths)} events figures")
        else:
            results["events"] = []
    except Exception as e:
        print(f"Error rendering events figures: {e}")
        results["events"] = []

    # ========================================================================
    # Phase 4: NWB
    # ========================================================================

    try:
        # Auto-discover NWB file if not provided
        if nwb_path is None:
            nwb_search = list(outputs_root.glob(f"{session_id}*.nwb"))
            if nwb_search:
                nwb_path = nwb_search[0]
            else:
                print(f"Warning: NWB file not found for {session_id}, skipping NWB figures")
                nwb_path = None

        if nwb_path is not None:
            print(f"Rendering NWB figures for {session_id}...")
            nwb_paths = render_nwb_figures(nwb_path=nwb_path, output_dir=nwb_dir, session_id=session_id, formats=formats)
            results["nwb"] = nwb_paths
            print(f"  → Generated {len(nwb_paths)} NWB figures")
        else:
            results["nwb"] = []

    except Exception as e:
        print(f"Error rendering NWB figures: {e}")
        results["nwb"] = []

    # ========================================================================
    # Summary
    # ========================================================================

    total_figures = sum(len(paths) for paths in results.values())
    print(f"\nSession overview complete: {total_figures} total figures generated")
    print(f"Figures saved to: {figures_root}")

    return results


def render_phase_figures(
    phase: str,
    session_id: str,
    outputs_root: Union[str, Path],
    output_dir: Union[str, Path],
    formats: tuple[str, ...] = ("png",),
    **kwargs,
) -> List[Path]:
    """Render figures for a specific pipeline phase.

    Convenience function for rendering a single phase's figures without
    full session orchestration.

    Args:
        phase: Phase name ('ingest', 'sync', 'pose', 'facemap', 'events', 'nwb')
        session_id: Session identifier
        outputs_root: Root directory containing pipeline outputs
        output_dir: Output directory for figures
        formats: Output formats
        **kwargs: Additional phase-specific arguments

    Returns:
        List of saved figure paths

    Raises:
        ValueError: If phase is not recognized

    Example:
        >>> paths = render_phase_figures(
        ...     phase='ingest',
        ...     session_id='SNA-145518',
        ...     outputs_root='data/interim',
        ...     output_dir='reports/figures/ingest'
        ... )
    """
    outputs_root = Path(outputs_root)
    output_dir = ensure_output_dir(output_dir)

    phase_renderers = {
        "ingest": lambda: render_ingest_figures(
            manifest=outputs_root / f"{session_id}_manifest.json",
            verification_summary=outputs_root / f"{session_id}_verification_summary.json",
            output_dir=output_dir,
            formats=formats,
            **kwargs,
        ),
        "sync": lambda: render_sync_figures(alignment_stats=outputs_root / f"{session_id}_alignment_stats.json", output_dir=output_dir, formats=formats, **kwargs),
        "pose": lambda: render_pose_figures(pose_bundle=outputs_root / f"{session_id}_pose_bundle.json", output_dir=output_dir, session_id=session_id, formats=formats),
        "facemap": lambda: render_facemap_figures(facemap_bundle=outputs_root / f"{session_id}_facemap_bundle.json", output_dir=output_dir, session_id=session_id, formats=formats),
        "events": lambda: render_events_figures(trials_events=outputs_root / f"{session_id}_trials_events.json", output_dir=output_dir, session_id=session_id, formats=formats),
        "nwb": lambda: render_nwb_figures(nwb_path=list(outputs_root.glob(f"{session_id}*.nwb"))[0], output_dir=output_dir, session_id=session_id, formats=formats),
    }

    if phase not in phase_renderers:
        raise ValueError(f"Unknown phase: {phase}. Choose from {list(phase_renderers.keys())}")

    return phase_renderers[phase]()
