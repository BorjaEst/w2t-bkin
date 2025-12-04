#!/usr/bin/env python3
"""Example 04: Bpod Camera Synchronization.

**Updated (2025-11-25)**: Uses config.bpod.sync for trial synchronization configuration.

Goal
----
Show **how to align Bpod trial times to TTL absolute time** using per-trial
offsets, with a clear mental model of the three systems:

1. TTL system (absolute time, t = 0)
2. Camera system (starts at camera_start_delay_s)
3. Bpod system (starts at bpod_start_delay_s)

Core idea
---------
For each trial, we align the Bpod timeline to the TTL timeline:
    offset_trial = T_ttl_sync - (TrialStartTimestamp + sync_time_rel)

We use:
    - config.bpod.sync.trial_types: Trial synchronization configuration
    - align_bpod_trials_to_ttl(...): compute per-trial offsets using TTL pulses
    - behavior.extract_*(..., trial_offsets=...): build NWB tables in **absolute time**

Example usage
-------------
    $ python examples/bpod_camera_sync.py
"""

import json
from pathlib import Path
import shutil
import warnings

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Suppress expected HDMF warnings about DynamicTableRegion parent relationships
# These are expected when tables haven't been added to NWBFile yet
warnings.filterwarnings("ignore", category=UserWarning, module="hdmf.container")

from synthetic import build_raw_folder
from w2t_bkin.config import load_config
from w2t_bkin.figures import plot_alignment_example, plot_alignment_grid, plot_trial_offsets, plot_ttl_timeline
from w2t_bkin.ingest.behavior import (
    build_task,
    build_task_recording,
    build_trials_table,
    extract_action_types,
    extract_actions,
    extract_event_types,
    extract_events,
    extract_state_types,
    extract_states,
    extract_task_arguments,
)
from w2t_bkin.ingest.bpod import parse_bpod
from w2t_bkin.ingest.ttl import get_ttl_pulses
from w2t_bkin.sync import align_bpod_trials_to_ttl, get_sync_time_from_bpod_trial
from w2t_bkin.utils import convert_matlab_struct, count_ttl_pulses, count_video_frames, discover_files, load_session_metadata_and_nwb, to_scalar


class ExampleSettings(BaseSettings):
    """Settings for Example 04: Bpod Camera Synchronization."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(default=Path("output/bpod_camera_sync"), description="Root directory for generated synthetic session and output files")
    subject_id: str = Field(default="subject-001", description="Subject identifier")
    session_id: str = Field(default="session-001", description="Session identifier")
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
        subject_id=settings.subject_id,
        session_id=settings.session_id,
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
    # PHASE 1: Load config and session metadata
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 1: Load Config and Session Metadata")
    print("=" * 80)

    config = load_config(session.config_path)

    # Get session directory
    session_dir = session.session_dir

    print("\nSession config:")
    print(f"  - Project:              {config.project.name}")
    print(f"  - Subject ID:           {settings.subject_id}")
    print(f"  - Session ID:           {settings.session_id}")
    print(f"  - Session dir:          {session_dir}")

    print("\nCamera + TTL overview:")
    # Get session model from the synthetic result
    from synthetic.session_synth import SessionSynthOptions, build_session

    session_opts = SessionSynthOptions(
        session_id=settings.session_id,
        subject_id=settings.subject_id,
        camera_ids=["cam0", "cam1"],
        ttl_ids=["ttl_camera", "ttl_bpod"],
    )
    session_model = build_session(options=session_opts)

    for cam in session_model.get("cameras", []):
        cam_videos = discover_files(session_dir, cam["paths"], sort=True)
        frame_count = sum(count_video_frames(Path(v)) for v in cam_videos)
        ttl_config = next((ttl for ttl in session_model.get("TTLs", []) if ttl["id"] == cam["ttl_id"]), None)
        if ttl_config:
            ttl_files = discover_files(session_dir, ttl_config["paths"], sort=True)
            ttl_pulse_count = sum(count_ttl_pulses(Path(t)) for t in ttl_files)
            mismatch = abs(frame_count - ttl_pulse_count)
            status = "✓" if mismatch <= 5 else "✗"
            print(f"  {status} Camera {cam['id']}:")
            print(f"      frames:             {frame_count}")
            print(f"      ttl pulses:         {ttl_pulse_count}")
            print(f"      ttl channel:        {cam['ttl_id']}")
            print(f"      mismatch:           {mismatch}")
        else:
            print(f"  - Camera {cam['id']}: (no TTL reference)")

    # ---------------------------------------------------------------------
    # PHASE 2: Parse Bpod data
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 2: Parse Bpod Data")
    print("=" * 80)

    print(f"\nParsing Bpod files from pattern: {session_model['bpod']['path']}")
    bpod_data_raw = parse_bpod(
        session_dir=session_dir,
        pattern=session_model["bpod"]["path"],
        order=session_model["bpod"]["order"],
        continuous_time=session_model["bpod"]["continuous_time"],
    )

    # Show trial count
    session_data_struct = convert_matlab_struct(bpod_data_raw["SessionData"])
    raw_events = convert_matlab_struct(session_data_struct.get("RawEvents") if isinstance(session_data_struct, dict) else session_data_struct.RawEvents)
    trials = raw_events.get("Trial") if isinstance(raw_events, dict) else raw_events.Trial
    n_trials = len(trials) if trials is not None else 0
    print(f"Parsed {n_trials} Bpod trial(s)")

    # ---------------------------------------------------------------------
    # PHASE 3: Load TTL pulses and compute per-trial offsets
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 3: TTL Pulses + Per-Trial Offsets")
    print("=" * 80)

    print("\nStep 3.1: Load TTL pulses from disk")
    # Extract primitives from session model
    ttl_patterns = {ttl["id"]: ttl["paths"] for ttl in session_model.get("TTLs", [])}
    ttl_pulses = get_ttl_pulses(session_dir, ttl_patterns)

    print("\nTTL channels (absolute times):")
    for ttl_id, timestamps in ttl_pulses.items():
        if timestamps:
            print(f"  - {ttl_id}: {len(timestamps)} pulses, " f"range [{timestamps[0]:.3f} s .. {timestamps[-1]:.3f} s]")
        else:
            print(f"  - {ttl_id}: (no pulses)")

    print("\nStep 3.2: Compute per-trial offsets (Bpod → TTL)")
    print("  For each trial, align Bpod sync state to next TTL pulse.")
    # Get sync signal and TTL from config (first trial type as example)
    print(f"  - sync_signal '{config.bpod.sync.trial_types[0].sync_signal}' is a Bpod state that triggers a TTL output")
    print(f"  - sync_ttl '{config.bpod.sync.trial_types[0].sync_ttl}' is the TTL channel that records those pulses")
    print("  offset_trial = T_ttl_sync - (TrialStartTimestamp + sync_time_rel)")

    # Extract trial type configs from config
    trial_type_configs = config.bpod.sync.trial_types
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
    if len(offsets_array) > 0:
        print("\nOffset statistics:")
        print(f"  - Mean: {np.mean(offsets_array):.4f} s")
        print(f"  - Std:  {np.std(offsets_array):.4f} s")
        print(f"  - Min:  {np.min(offsets_array):.4f} s")
        print(f"  - Max:  {np.max(offsets_array):.4f} s")
    else:
        print("\nNo trials aligned (check sync configuration and Bpod data)")

    # -----------------------------------------------------------------
    # Generate TTL timeline visualization (always useful)
    # -----------------------------------------------------------------
    output_dir = settings.output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    cameras = session_model.get("cameras", [])
    example_cam_ttl = cameras[0]["ttl_id"] if cameras else None
    example_sync_ttl = config.bpod.sync.trial_types[0].sync_ttl if config.bpod.sync.trial_types else None
    ttl_order = [ch for ch in [example_cam_ttl, example_sync_ttl] if ch]

    print("\nGenerating TTL timeline plot...")
    plot_ttl_timeline(ttl_pulses, channel_order=ttl_order, out_path=output_dir / "ttl_timeline.png")
    print(f"  ✓ Saved: {output_dir / 'ttl_timeline.png'}")

    if trial_offsets:
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

        # Look up sync signal from config (first trial_type as example)
        # In a real session, this can differ per trial_type.
        sync_signal = config.bpod.sync.trial_types[0].sync_signal
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
        # PHASE 3b: Additional visualizations for aligned trials
        # -----------------------------------------------------------------
        print("\nGenerating alignment plots...")

        # Offsets trend across trials
        plot_trial_offsets(trial_offsets, out_path=output_dir / "trial_offsets.png")
        print(f"  ✓ Saved: {output_dir / 'trial_offsets.png'}")

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
        example_cam_ttl = cameras[0]["ttl_id"] if cameras else None
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
            out_path=output_dir / "alignment_example.png",
            extra_bpod_rel=extra_bpod_rel,
            extra_ttl_series=extra_ttl_series,
        )
    else:
        print("\nSkipping visualizations (no aligned trials)")

    # ---------------------------------------------------------------------
    # PHASE 4: Build NWB behavior tables (ndx-structured-behavior)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 4: Build NWB Behavior Tables (ndx-structured-behavior)")
    print("=" * 80)

    print("\nStep 4.1: Extract type tables (metadata)")
    state_types = extract_state_types(bpod_data_raw)
    event_types = extract_event_types(bpod_data_raw)
    action_types = extract_action_types(bpod_data_raw)

    print(f"  - State types:  {len(state_types)}")
    print(f"  - Event types:  {len(event_types)}")
    print(f"  - Action types: {len(action_types)}")

    print("\nStep 5.2: Extract data tables (temporal sequences with offsets)")
    states, state_indices = extract_states(bpod_data_raw, state_types, trial_offsets=trial_offsets)
    events, event_indices = extract_events(bpod_data_raw, event_types, trial_offsets=trial_offsets)
    actions, action_indices = extract_actions(bpod_data_raw, action_types, trial_offsets=trial_offsets)

    print(f"  - States:  {len(states)} entries")
    print(f"  - Events:  {len(events)} entries")
    print(f"  - Actions: {len(actions)} entries")

    print("\nStep 4.3: Build task recording")
    task_recording = build_task_recording(states, events, actions)

    print("\nStep 4.4: Build trials table")
    trials_table = build_trials_table(bpod_data_raw, task_recording, state_indices, event_indices, action_indices, trial_offsets=trial_offsets)

    print(f"  - Trials table: {len(trials_table)} trials")
    print(f"  - Task recording: {task_recording.name}")

    print("\nStep 4.4: Build Task container (optional metadata)")
    task_arguments = extract_task_arguments(bpod_data_raw)
    task = build_task(state_types, event_types, action_types, task_arguments=task_arguments)

    if task_arguments is not None:
        print(f"  - Task arguments: {len(task_arguments)} parameters")
    else:
        print(f"  - Task arguments: None (minimal synthetic data)")
    print(f"  - Task container: {task.name}")

    # Show example trial (first trial from trials table)
    if len(trials_table) > 0:
        print("\nExample Trial 1 (from trials_table):")
        print(f"  - Start time (abs): {trials_table['start_time'][0]:.3f} s")
        print(f"  - Stop time  (abs): {trials_table['stop_time'][0]:.3f} s")
        print(f"  - Duration:         {trials_table['stop_time'][0] - trials_table['start_time'][0]:.3f} s")

    # ---------------------------------------------------------------------
    # PHASE 5: Summary statistics + small report
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 5: Summary Statistics + Report")
    print("=" * 80)

    output_dir = settings.output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Compute summary statistics from trials table
    n_trials = len(trials_table)
    trial_durations = np.array(trials_table["stop_time"][:]) - np.array(trials_table["start_time"][:])
    mean_duration = float(np.mean(trial_durations))

    trial_summary = {
        "session_id": settings.session_id,
        "total_trials": n_trials,
        "mean_trial_duration": mean_duration,
        "n_states": len(states),
        "n_events": len(events),
        "n_actions": len(actions),
    }

    trial_summary_path = output_dir / "trial_summary.json"
    with open(trial_summary_path, "w") as f:
        json.dump(trial_summary, f, indent=2)

    print("\nTrial summary:")
    print(f"  - Session ID:          {trial_summary['session_id']}")
    print(f"  - Total trials:        {trial_summary['total_trials']}")
    print(f"  - Mean trial duration: {trial_summary['mean_trial_duration']:.3f} s")
    print(f"  - Total states:        {trial_summary['n_states']}")
    print(f"  - Total events:        {trial_summary['n_events']}")
    print(f"  - Total actions:       {trial_summary['n_actions']}")

    print("\nArtifacts written:")
    print(f"  - Trial summary JSON:    {trial_summary_path}")
    alignment_stats_path = output_dir / "alignment_stats.json"
    if trial_offsets:
        alignment_results = {
            "trial_offsets": {str(k): v for k, v in trial_offsets.items()},
            "statistics": {"n_trials_total": len(trials_table), "n_trials_aligned": len(trial_offsets)},
            "warnings": warnings,
        }
        with open(alignment_stats_path, "w") as f:
            json.dump(alignment_results, f, indent=2)
        print(f"  - Alignment results:     {alignment_stats_path}")
    # Figures (if matplotlib available)
    figures_written = [
        output_dir / "ttl_timeline.png",
        output_dir / "trial_offsets.png",
        output_dir / "alignment_example.png",
    ]
    # Add a small-multiples alignment panel across the first few trials
    grid_infos = []
    max_trials_grid = 6
    for tn in sorted(trial_offsets.keys())[:max_trials_grid]:
        ts = float(to_scalar(session_data_struct["TrialStartTimestamp"], tn - 1))
        te = float(to_scalar(session_data_struct["TrialEndTimestamp"], tn - 1))
        trial_raw_n = convert_matlab_struct(raw_events["Trial"][tn - 1])
        sync_rel_n = get_sync_time_from_bpod_trial(trial_raw_n, sync_signal)
        ttl_sync_n = ts + sync_rel_n + trial_offsets[tn]
        grid_infos.append({"trial_number": tn, "trial_start_ts": ts, "trial_end_ts": te, "sync_time_rel": float(sync_rel_n), "ttl_sync_time": float(ttl_sync_n)})
    grid_path = output_dir / "figures" / "alignment_grid.png"
    if grid_infos:
        plot_alignment_grid(grid_infos, out_path=grid_path, cols=3)
        figures_written.append(grid_path)

    for p in figures_written:
        if p.exists():
            print(f"  - Figure:                {p}")

    print("\nSummary:")
    print("  - TTL system defines absolute time (t = 0)")
    # Get camera TTL from session model (first camera as example)
    cameras = session_model.get("cameras", [])
    example_cam_ttl = cameras[0]["ttl_id"] if cameras else "cam_ttl"
    print(f"  - Camera frames start at {settings.camera_start_delay_s:.3f} s " f"and are aligned via {example_cam_ttl} (one pulse per frame)")
    print(f"  - Bpod trials start at {settings.bpod_start_delay_s:.3f} s")
    # Get sync signal and TTL from config (first trial type as example)
    example_sync_signal = config.bpod.sync.trial_types[0].sync_signal if config.bpod.sync.trial_types else "sync_signal"
    example_sync_ttl = config.bpod.sync.trial_types[0].sync_ttl if config.bpod.sync.trial_types else "sync_ttl"
    print(f"  - Bpod sync state '{example_sync_signal}' triggers TTL pulses on {example_sync_ttl} (one per trial)")
    print(f"  - align_bpod_trials_to_ttl() uses {example_sync_ttl} to compute per-trial offsets")
    print("  - behavior.extract_*(..., trial_offsets=...) yields NWB tables in TTL absolute time")
    print("  - Result: TaskRecording + TrialsTable ready for NWB integration")

    print("\nDone.")
