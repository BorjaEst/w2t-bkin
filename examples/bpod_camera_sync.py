#!/usr/bin/env python3
"""Example 04: Bpod Camera Synchronization (simplified).

Goal
----
Show **how to align Bpod trial times to TTL absolute time** using per-trial
offsets, with a clear mental model of the three systems:

1. TTL system (absolute time, t = 0)
   - Records *all* hardware sync pulses
   - For cameras: logs one pulse per frame → frame index → absolute timestamp
   - For Bpod: logs a sync pulse per trial from a specific Bpod state/event
     (e.g., Bpod outputs a TTL pulse when entering a sync state)

2. Camera system (starts at camera_start_delay_s)
   - Frames are triggered by TTL pulses
   - TTL log gives absolute time for each frame index
   - Recorded in TTL channel defined in session config (one pulse per frame)

3. Bpod system (starts at bpod_start_delay_s)
   - Within each trial, Bpod times are **relative to trial start**
   - A chosen state/event (sync_signal) also triggers a TTL pulse
   - That TTL pulse is recorded in a SEPARATE TTL channel (one pulse per trial)
   - Both sync_signal and sync_ttl are defined per trial_type in session config

Core idea
---------
For each trial, we align the Bpod timeline to the TTL timeline:

    offset_trial = T_ttl_sync - (TrialStartTimestamp + sync_time_rel)

Where:
    - sync_time_rel: start time of the sync state within the trial (Bpod-relative)
    - TrialStartTimestamp: when Bpod says the trial started (its own clock)
    - T_ttl_sync: absolute time of the sync pulse recorded by TTL

Then for *any* Bpod time in that trial:
    t_abs = offset_trial + t_bpod

We use:
    - align_bpod_trials_to_ttl(...): compute per-trial offsets using TTL pulses
    - extract_trials(..., trial_offsets=offsets): return trials in **absolute time**

Example usage
-------------
    $ python examples/bpod_camera_sync.py

With different timing:
    $ CAMERA_START_DELAY_S=3.0 BPOD_START_DELAY_S=10.0 python examples/bpod_camera_sync.py
"""

import json
from pathlib import Path
import shutil

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from figures import plot_alignment_example, plot_alignment_grid, plot_trial_offsets, plot_ttl_timeline
from synthetic import build_raw_folder
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest
from w2t_bkin.events import extract_behavioral_events, extract_trials, parse_bpod, parse_bpod_mat
from w2t_bkin.events.bpod import discover_bpod_files_from_pattern
from w2t_bkin.events.summary import create_event_summary
from w2t_bkin.sync import align_bpod_trials_to_ttl, create_timebase_provider_from_config, get_ttl_pulses
from w2t_bkin.sync.behavior import get_sync_time_from_bpod_trial
from w2t_bkin.utils import convert_matlab_struct, to_scalar


class ExampleSettings(BaseSettings):
    """Settings for Example 04: Bpod Camera Synchronization."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(default=Path("output/bpod_camera_sync"), description="Root directory for generated synthetic session and output files")
    n_frames: int = Field(default=600, description="Number of camera frames to generate (one TTL pulse per frame)")
    n_trials: int = Field(default=8, description="Number of Bpod trials to generate (one sync TTL pulse per trial)")
    seed: int = Field(default=42, description="Random seed for reproducible synthetic data generation")
    cleanup: bool = Field(default=False, description="Whether to remove existing output directory before running")

    # Timing offsets (in seconds)
    camera_start_delay_s: float = Field(default=2.0, description="Delay before camera starts recording (relative to TTL system start)")
    bpod_start_delay_s: float = Field(default=6.0, description="Delay before Bpod starts first trial (relative to TTL system start)")
    bpod_clock_jitter_s: float = Field(default=1e-3, description="Simulated jitter in Bpod clock (seconds)")
    bpod_sync_delay_s: float = Field(default=1.0, description="Delay of sync signal within each Bpod trial (relative to trial start)")


if __name__ == "__main__":
    """Run the Bpod–camera synchronization demo."""
    settings = ExampleSettings()

    print("=" * 80)
    print("Example 04: Bpod Camera Synchronization (simplified)")
    print("=" * 80)

    # Clean output directory if requested
    if settings.output_root.exists() and settings.cleanup:
        shutil.rmtree(settings.output_root)
    settings.output_root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate synthetic session with known delays
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 0: Synthetic Session with Known Delays")
    print("=" * 80)

    print(f"\nGenerating synthetic session:")
    print(f"  - Camera frames:        {settings.n_frames}")
    print(f"  - Bpod trials:          {settings.n_trials}")
    print(f"  - Seed:                 {settings.seed}")
    print("\nSystem start times (TTL timeline):")
    print(f"  - TTL system:           t = 0.0 s")
    print(f"  - Camera system:        t = {settings.camera_start_delay_s:.3f} s")
    print(f"  - Bpod system:          t = {settings.bpod_start_delay_s:.3f} s")
    print(f"  - Bpod sync delay:      {settings.bpod_sync_delay_s:.3f} s within each trial")

    session = build_raw_folder(
        out_root=settings.output_root / "raw",
        project_name="Bpod-Camera-Sync-Demo",
        session_id="Session-000001",
        camera_ids=["cam0", "cam1"],
        ttl_ids=["ttl_camera", "ttl_bpod"],
        n_frames=settings.n_frames,
        n_trials=settings.n_trials,
        fps=30.0,
        camera_start_delay_s=settings.camera_start_delay_s,
        bpod_start_delay_s=settings.bpod_start_delay_s,
        bpod_sync_delay_s=settings.bpod_sync_delay_s,
        bpod_clock_jitter_ppm=settings.bpod_clock_jitter_s * 1_000_000.0,  # Convert to ppm
        seed=settings.seed,
    )

    print("\nSynthetic artifacts:")
    print(f"  - Config:               {session.config_path}")
    print(f"  - Session:              {session.session_path}")
    print(f"  - Video files:          {len(session.video_paths)}")
    print(f"  - TTL files:            {len(session.ttl_paths)}")
    print(f"  - Bpod .mat files:      {len(session.bpod_paths)}")

    # ---------------------------------------------------------------------
    # PHASE 1: Load config + build manifest
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 1: Ingest (config + manifest)")
    print("=" * 80)

    config = cfg_module.load_config(session.config_path)
    session_cfg = cfg_module.load_session(session.session_path)

    print("\nSession config:")
    print(f"  - Project:              {config.project.name}")
    print(f"  - Session ID:           {session_cfg.session.id}")
    print(f"  - Subject:              {session_cfg.session.subject_id}")
    print(f"  - Cameras:              {len(session_cfg.cameras)}")
    print(f"  - Bpod path pattern:    {session_cfg.bpod.path}")

    manifest = ingest.build_and_count_manifest(config, session_cfg)

    print("\nCamera + TTL overview (from manifest):")
    for cam in manifest.cameras:
        print(f"  - Camera {cam.camera_id}:")
        print(f"      frames:             {cam.frame_count}")
        print(f"      ttl pulses:         {cam.ttl_pulse_count}")
        print(f"      ttl channel:        {cam.ttl_id}")

    print("\nTTL channels discovered:")
    for ttl in manifest.ttls:
        print(f"  - TTL {ttl.ttl_id}: {len(ttl.files)} file(s)")

    # ---------------------------------------------------------------------
    # PHASE 2: Quick verification (frame vs TTL counts)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 2: Quick Verification (frame vs TTL counts)")
    print("=" * 80)

    verification = ingest.verify_manifest(manifest, tolerance=5)
    print("\nVerification per camera:")
    for cam in verification.camera_results:
        status_symbol = "✓" if cam.status == "pass" else "✗"
        print(f"  {status_symbol} {cam.camera_id}: status={cam.status}, mismatch={cam.mismatch}")

    # ---------------------------------------------------------------------
    # PHASE 3: Parse Bpod data (but don't extract trials yet)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 3: Parse Bpod Data")
    print("=" * 80)

    session_dir = Path(session_cfg.session_dir)
    # Use parse_bpod directly instead of discover_bpod_files
    print(f"\nParsing Bpod files from pattern: {session_cfg.bpod.path}")

    # Peek into first Bpod file to show structure (if exists)
    bpod_files = discover_bpod_files_from_pattern(session_dir=session_dir, pattern=session_cfg.bpod.path, order=session_cfg.bpod.order)
    print(f"Found {len(bpod_files)} Bpod file(s):")
    for bf in bpod_files:
        print(f"  - {bf.name}")

    # Peek into first file
    bpod_raw_example = parse_bpod_mat(bpod_files[0])
    if "SessionData" in bpod_raw_example:
        session_data_raw = bpod_raw_example["SessionData"]
        if hasattr(session_data_raw, "nTrials"):
            print(f"\nExample Bpod file:")
            print(f"  - nTrials:   {session_data_raw.nTrials}")
        elif isinstance(session_data_raw, dict) and "nTrials" in session_data_raw:
            print(f"\nExample Bpod file:")
            print(f"  - nTrials:   {session_data_raw['nTrials']}")

    # Parse complete Bpod session using low-level API
    print("\nParsing complete Bpod session (all Bpod files)...")
    bpod_data_raw = parse_bpod(session_dir=session_dir, pattern=session_cfg.bpod.path, order=session_cfg.bpod.order, continuous_time=session_cfg.bpod.continuous_time)

    # ---------------------------------------------------------------------
    # PHASE 4: Load TTL pulses and compute per-trial offsets
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 4: TTL Pulses + Per-Trial Offsets")
    print("=" * 80)

    print("\nStep 4.1: Load TTL pulses from disk (Phase 2 pattern)")
    # Extract primitives from session
    ttl_patterns = {ttl.id: ttl.paths for ttl in session_cfg.TTLs}
    ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

    print("\nTTL channels (absolute times):")
    for ttl_id, timestamps in ttl_pulses.items():
        if timestamps:
            print(f"  - {ttl_id}: {len(timestamps)} pulses, " f"range [{timestamps[0]:.3f} s .. {timestamps[-1]:.3f} s]")
        else:
            print(f"  - {ttl_id}: (no pulses)")

    print("\nStep 4.2: Compute per-trial offsets (Bpod → TTL) [Phase 2 pattern]")
    print("  For each trial, align Bpod sync state to next TTL pulse.")
    # Get sync signal and TTL from session config (first trial type as example)
    print(f"  - sync_signal '{session_cfg.bpod.trial_types[0].sync_signal}' is a Bpod state that triggers a TTL output")
    print(f"  - sync_ttl '{session_cfg.bpod.trial_types[0].sync_ttl}' is the TTL channel that records those pulses")
    print("  offset_trial = T_ttl_sync - (TrialStartTimestamp + sync_time_rel)")

    # Extract trial type configs from session (Phase 2 pattern)
    trial_type_configs = session_cfg.bpod.trial_types
    trial_offsets, warnings = align_bpod_trials_to_ttl(
        trial_type_configs=trial_type_configs,
        bpod_data=bpod_data_raw,
        ttl_pulses=ttl_pulses,  # Pass full dict - function matches channels per trial_type
    )

    if warnings:
        print(f"\nAlignment warnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"  - {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")

    print(f"\nComputed offsets for {len(trial_offsets)} trial(s).")

    offsets_array = np.array(list(trial_offsets.values()))
    print("\nOffset statistics:")
    print(f"  - Mean: {np.mean(offsets_array):.4f} s")
    print(f"  - Std:  {np.std(offsets_array):.4f} s")
    print(f"  - Min:  {np.min(offsets_array):.4f} s")
    print(f"  - Max:  {np.max(offsets_array):.4f} s")

    print("\nFirst 10 per-trial offsets:")
    for trial_num in sorted(trial_offsets.keys())[:10]:
        print(f"  - Trial {trial_num:2d}: offset = {trial_offsets[trial_num]:.4f} s")

    # Demonstrate the math explicitly for trial 1
    example_trial = sorted(trial_offsets.keys())[0]
    offset = trial_offsets[example_trial]

    print(f"\nExample alignment math for Trial {example_trial}:")
    session_data_struct = bpod_data_raw["SessionData"]
    session_data_struct = convert_matlab_struct(session_data_struct)
    raw_events = convert_matlab_struct(session_data_struct["RawEvents"])
    trial_raw = convert_matlab_struct(raw_events["Trial"][example_trial - 1])
    trial_start_ts = float(to_scalar(session_data_struct["TrialStartTimestamp"], example_trial - 1))
    trial_end_ts = float(to_scalar(session_data_struct["TrialEndTimestamp"], example_trial - 1))

    # Look up sync signal from session config (first trial_type as example)
    # In a real session, this can differ per trial_type.
    sync_signal = session_cfg.bpod.trial_types[0].sync_signal
    sync_time_rel = get_sync_time_from_bpod_trial(trial_raw, sync_signal)
    bpod_sync_time = trial_start_ts + sync_time_rel
    ttl_sync_time = bpod_sync_time + offset

    print(f"  - TrialStartTimestamp (Bpod): {trial_start_ts:.3f} s")
    print(f"  - Sync time (relative):       {sync_time_rel:.3f} s")
    print(f"  - Bpod sync time:             {bpod_sync_time:.3f} s")
    print(f"  - Offset (trial):             {offset:.3f} s")
    print(f"  - TTL sync time:              {ttl_sync_time:.3f} s")
    print("  => absolute_time = offset + bpod_time")

    # -----------------------------------------------------------------
    # PHASE 4b: Visualizations to aid understanding
    # -----------------------------------------------------------------
    figs_dir = settings.output_root / "output" / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    # TTL timeline for key channels (camera TTL and Bpod sync TTL)
    example_cam_ttl = session_cfg.cameras[0].ttl_id if session_cfg.cameras else None
    example_sync_ttl = session_cfg.bpod.trial_types[0].sync_ttl if session_cfg.bpod.trial_types else None
    ttl_order = [ch for ch in [example_cam_ttl, example_sync_ttl] if ch]
    plot_ttl_timeline(ttl_pulses, channel_order=ttl_order, out_path=figs_dir / "ttl_timeline.png")

    # Offsets trend across trials
    plot_trial_offsets(trial_offsets, out_path=figs_dir / "trial_offsets.png")

    # Alignment example illustration for the first trial, with more context.
    # Extra Bpod-relative signals: trial start/end, sync start/end (if available)
    extra_bpod_rel = [("trial start", 0.0), ("trial end", max(0.0, trial_end_ts - trial_start_ts)), ("sync start", sync_time_rel)]
    # Optionally include sync end from Bpod states (if present)
    try:
        states = convert_matlab_struct(trial_raw.get("States", {}))
        if isinstance(states, dict) and sync_signal in states:
            sync_arr = states[sync_signal]
            if isinstance(sync_arr, (list, tuple, np.ndarray)) and len(sync_arr) == 2:
                extra_bpod_rel.append(("sync end", float(sync_arr[1])))
    except Exception:
        pass

    # Extra TTL series: camera TTL pulses near the trial window
    example_cam_ttl = session_cfg.cameras[0].ttl_id if session_cfg.cameras else None
    extra_ttl_series = {}
    if example_cam_ttl and example_cam_ttl in ttl_pulses:
        window_start = trial_start_ts - 0.25
        window_end = trial_end_ts + 0.25
        cam_pulses_near = [t for t in ttl_pulses[example_cam_ttl] if window_start <= t <= window_end]
        # Limit to avoid clutter if necessary
        extra_ttl_series[example_cam_ttl] = cam_pulses_near[:120]

    plot_alignment_example(
        trial_number=example_trial,
        trial_start_ts=trial_start_ts,
        trial_end_ts=trial_end_ts,
        sync_time_rel=sync_time_rel,
        ttl_sync_time=ttl_sync_time,
        out_path=figs_dir / "alignment_example.png",
        extra_bpod_rel=extra_bpod_rel,
        extra_ttl_series=extra_ttl_series,
    )

    # ---------------------------------------------------------------------
    # PHASE 5: Extract trials with offsets + behavioral events
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 5: Extract Trials (in absolute time) + Events")
    print("=" * 80)

    print("\nExtracting trials with trial_offsets applied...")
    trials = extract_trials(bpod_data_raw, trial_offsets=trial_offsets)

    print(f"  - Extracted {len(trials)} trials")
    if trials:
        t0 = trials[0]
        print("\nExample Trial 1 after alignment:")
        print(f"  - Trial type: {t0.trial_type}")
        print(f"  - Start time (abs): {t0.start_time:.3f} s")
        print(f"  - Stop time  (abs): {t0.stop_time:.3f} s")
        print(f"  - Duration:        {t0.stop_time - t0.start_time:.3f} s")

    print("\nExtracting behavioral events (still Bpod-centric)...")
    events = extract_behavioral_events(bpod_data_raw)
    print(f"  - Extracted {len(events)} events")

    # Simple QC summary
    event_categories = {}
    for e in events:
        event_categories.setdefault(e.event_type, 0)
        event_categories[e.event_type] += 1

    print("\nEvent counts by type:")
    for etype, count in sorted(event_categories.items()):
        print(f"  - {etype}: {count}")

    # ---------------------------------------------------------------------
    # PHASE 6: Trial summary + small report
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 6: Trial Summary + Report")
    print("=" * 80)

    output_dir = settings.output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_summary = create_event_summary(
        session_id=session_cfg.session.id,
        trials=trials,
        events=events,
    )

    trial_summary_path = output_dir / "trial_summary.json"
    with open(trial_summary_path, "w") as f:
        json.dump(trial_summary.model_dump(), f, indent=2)

    print("\nTrial summary:")
    print(f"  - Session ID:            {trial_summary.session_id}")
    print(f"  - Total trials:          {trial_summary.total_trials}")
    print(f"  - Mean trial duration:   {trial_summary.mean_trial_duration:.3f} s")
    if trial_summary.mean_response_latency is not None:
        print(f"  - Mean response latency: {trial_summary.mean_response_latency:.3f} s")

    print("\nArtifacts written:")
    print(f"  - Trial summary JSON:    {trial_summary_path}")
    alignment_stats_path = output_dir / "alignment_stats.json"
    if trial_offsets:
        alignment_results = {
            "trial_offsets": {str(k): v for k, v in trial_offsets.items()},
            "statistics": {"n_trials_total": len(trials), "n_trials_aligned": len(trial_offsets)},
            "warnings": warnings,
        }
        with open(alignment_stats_path, "w") as f:
            json.dump(alignment_results, f, indent=2)
        print(f"  - Alignment results:     {alignment_stats_path}")
    # Figures (if matplotlib available)
    figures_written = [
        output_dir / "figures" / "ttl_timeline.png",
        output_dir / "figures" / "trial_offsets.png",
        output_dir / "figures" / "alignment_example.png",
    ]
    # Add a small-multiples alignment panel across the first few trials
    try:
        grid_infos = []
        max_trials_grid = 6
        for tn in sorted(trial_offsets.keys())[:max_trials_grid]:
            ts = float(to_scalar(session_data_struct["TrialStartTimestamp"], tn - 1))
            te = float(to_scalar(session_data_struct["TrialEndTimestamp"], tn - 1))
            trial_raw_n = convert_matlab_struct(raw_events["Trial"][tn - 1])
            sync_rel_n = get_sync_time_from_bpod_trial(trial_raw_n, sync_signal)
            ttl_sync_n = ts + sync_rel_n + trial_offsets[tn]
            grid_infos.append(
                {
                    "trial_number": tn,
                    "trial_start_ts": ts,
                    "trial_end_ts": te,
                    "sync_time_rel": float(sync_rel_n),
                    "ttl_sync_time": float(ttl_sync_n),
                }
            )
        grid_path = output_dir / "figures" / "alignment_grid.png"
        if grid_infos:
            plot_alignment_grid(grid_infos, out_path=grid_path, cols=3)
            figures_written.append(grid_path)
    except Exception:
        pass
    for p in figures_written:
        if p.exists():
            print(f"  - Figure:                {p}")

    print("\nSummary:")
    print("  - TTL system defines absolute time (t = 0)")
    # Get camera TTL from session config (first camera as example)
    example_cam_ttl = session_cfg.cameras[0].ttl_id if session_cfg.cameras else "cam_ttl"
    print(f"  - Camera frames start at {settings.camera_start_delay_s:.3f} s " f"and are aligned via {example_cam_ttl} (one pulse per frame)")
    print(f"  - Bpod trials start at {settings.bpod_start_delay_s:.3f} s")
    # Get sync signal and TTL from session config (first trial type as example)
    example_sync_signal = session_cfg.bpod.trial_types[0].sync_signal if session_cfg.bpod.trial_types else "sync_signal"
    example_sync_ttl = session_cfg.bpod.trial_types[0].sync_ttl if session_cfg.bpod.trial_types else "sync_ttl"
    print(f"  - Bpod sync state '{example_sync_signal}' triggers TTL pulses on {example_sync_ttl} (one per trial)")
    print(f"  - align_bpod_trials_to_ttl() uses {example_sync_ttl} to compute per-trial offsets")
    print("  - extract_trials(..., trial_offsets=...) yields trials in TTL absolute time")

    print("\nDone.")
