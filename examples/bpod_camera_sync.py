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
     (e.g., Bpod outputs a TTL pulse on D1 when entering a sync state)

2. Camera system (starts at camera_start_delay_s)
   - Frames are triggered by TTL pulses
   - TTL log gives absolute time for each frame index
   - Recorded in TTL channel: cam0_ttl (one pulse per frame)

3. Bpod system (starts at bpod_start_delay_s)
   - Within each trial, Bpod times are **relative to trial start**
   - A chosen state/event (sync_signal, e.g., "bpod_d1") also triggers a TTL pulse
   - That TTL pulse is recorded in a SEPARATE TTL channel: bpod_d1_ttl (one pulse per trial)

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
    $ python examples/04_bpod_camera_sync.py

With different timing:
    $ CAMERA_START_DELAY_S=3.0 BPOD_START_DELAY_S=10.0 python examples/04_bpod_camera_sync.py
"""

import json
from pathlib import Path
import shutil

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Synthetic data imports
from synthetic.scenarios import happy_path

# W2T-BKIN imports
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest
from w2t_bkin.events import discover_bpod_files, extract_behavioral_events, extract_trials, parse_bpod_mat, parse_bpod_session
from w2t_bkin.events.helpers import to_scalar
from w2t_bkin.events.summary import create_event_summary
from w2t_bkin.sync import align_bpod_trials_to_ttl, create_timebase_provider, get_ttl_pulses
from w2t_bkin.sync.behavior import get_sync_time_from_bpod_trial
from w2t_bkin.utils import convert_matlab_struct


class ExampleSettings(BaseSettings):
    """Settings for Example 04: Bpod Camera Synchronization."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(default=Path("temp/examples/04_bpod_camera_sync"), description="Root directory for generated synthetic session and output files")
    n_frames: int = Field(default=300, description="Number of camera frames to generate (one TTL pulse per frame)")
    n_trials: int = Field(default=10, description="Number of Bpod trials to generate (one sync TTL pulse per trial)")
    seed: int = Field(default=42, description="Random seed for reproducible synthetic data generation")
    cleanup: bool = Field(default=False, description="Whether to remove existing output directory before running")

    # Timing offsets (in seconds)
    camera_start_delay_s: float = Field(default=2.0, description="Delay before camera starts recording (relative to TTL system start)")
    bpod_start_delay_s: float = Field(default=6.0, description="Delay before Bpod starts first trial (relative to TTL system start)")
    bpod_sync_delay_s: float = Field(default=0.0, description="Delay of sync signal within each Bpod trial (relative to trial start)")


def run_pipeline(settings: ExampleSettings) -> dict:
    """Run the Bpod–camera synchronization demo."""

    output_root = settings.output_root
    n_frames = settings.n_frames
    n_trials = settings.n_trials
    seed = settings.seed
    cleanup = settings.cleanup
    camera_start_delay_s = settings.camera_start_delay_s
    bpod_start_delay_s = settings.bpod_start_delay_s
    bpod_sync_delay_s = settings.bpod_sync_delay_s

    print("=" * 80)
    print("Example 04: Bpod Camera Synchronization (simplified)")
    print("=" * 80)

    # Clean output directory if requested
    if output_root.exists() and cleanup:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate synthetic session with known delays
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 0: Synthetic Session with Known Delays")
    print("=" * 80)

    print(f"\nGenerating synthetic session:")
    print(f"  - Camera frames:        {n_frames}")
    print(f"  - Bpod trials:          {n_trials}")
    print(f"  - Seed:                 {seed}")
    print("\nSystem start times (TTL timeline):")
    print(f"  - TTL system:           t = 0.0 s")
    print(f"  - Camera system:        t = {camera_start_delay_s:.3f} s")
    print(f"  - Bpod system:          t = {bpod_start_delay_s:.3f} s")
    print(f"  - Bpod sync delay:      {bpod_sync_delay_s:.3f} s within each trial")

    session = happy_path.make_session_with_bpod(
        root=output_root,
        session_id="bpod-sync-001",
        n_frames=n_frames,
        n_trials=n_trials,
        seed=seed,
    )

    print("\nSynthetic artifacts:")
    print(f"  - Config:               {session.config_path}")
    print(f"  - Session:              {session.session_path}")
    print(f"  - Camera video files:   {len(session.camera_video_paths)}")
    print(f"  - TTL files:            {len(session.ttl_paths)}")
    if session.bpod_path:
        print(f"  - Bpod .mat file:       {session.bpod_path.name}")

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
        status_symbol = "✓" if cam.status == "OK" else "⚠" if cam.status == "WARN" else "✗"
        print(f"  {status_symbol} {cam.camera_id}: status={cam.status}, mismatch={cam.mismatch}")

    # ---------------------------------------------------------------------
    # PHASE 3: Parse Bpod data (but don't extract trials yet)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 3: Parse Bpod Data")
    print("=" * 80)

    session_dir = Path(session_cfg.session_dir)
    bpod_files = discover_bpod_files(session_cfg.bpod, session_dir)
    print(f"\nFound {len(bpod_files)} Bpod file(s):")
    for bf in bpod_files:
        print(f"  - {bf.name}")

    # Peek into first Bpod file to show structure
    bpod_raw_example = parse_bpod_mat(bpod_files[0])
    if "SessionData" in bpod_raw_example:
        session_data_raw = bpod_raw_example["SessionData"]
        if hasattr(session_data_raw, "nTrials"):
            print(f"\nExample Bpod file:")
            print(f"  - nTrials:   {session_data_raw.nTrials}")
        elif isinstance(session_data_raw, dict) and "nTrials" in session_data_raw:
            print(f"\nExample Bpod file:")
            print(f"  - nTrials:   {session_data_raw['nTrials']}")

    # Parse complete Bpod session
    print("\nParsing complete Bpod session (all Bpod files)...")
    bpod_data_raw = parse_bpod_session(session_cfg)

    # ---------------------------------------------------------------------
    # PHASE 4: Load TTL pulses and compute per-trial offsets
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 4: TTL Pulses + Per-Trial Offsets")
    print("=" * 80)

    print("\nStep 4.1: Load TTL pulses from disk")
    ttl_pulses = get_ttl_pulses(session_cfg, session_dir=session_dir)

    print("\nTTL channels (absolute times):")
    for ttl_id, timestamps in ttl_pulses.items():
        if timestamps:
            print(f"  - {ttl_id}: {len(timestamps)} pulses, " f"range [{timestamps[0]:.3f} s .. {timestamps[-1]:.3f} s]")
        else:
            print(f"  - {ttl_id}: (no pulses)")

    print("\nStep 4.2: Compute per-trial offsets (Bpod → TTL)")
    print("  For each trial, align Bpod sync state to next TTL pulse.")
    print("  - sync_signal 'bpod_d1' is a Bpod state that triggers a TTL output")
    print("  - sync_ttl 'bpod_d1_ttl' is the TTL channel that records those pulses")
    print("  offset_trial = T_ttl_sync - (TrialStartTimestamp + sync_time_rel)")

    trial_offsets, warnings = align_bpod_trials_to_ttl(
        session=session_cfg,
        bpod_data=bpod_data_raw,
        ttl_pulses=ttl_pulses,
    )

    if warnings:
        print(f"\nAlignment warnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"  - {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")

    print(f"\nComputed offsets for {len(trial_offsets)} trial(s).")

    if trial_offsets:
        offsets_array = np.array(list(trial_offsets.values()))
        print("\nOffset statistics:")
        print(f"  - Mean: {np.mean(offsets_array):.4f} s")
        print(f"  - Std:  {np.std(offsets_array):.4f} s")
        print(f"  - Min:  {np.min(offsets_array):.4f} s")
        print(f"  - Max:  {np.max(offsets_array):.4f} s")

        print("\nFirst 10 per-trial offsets:")
        for trial_num in sorted(trial_offsets.keys())[:10]:
            print(f"  - Trial {trial_num:2d}: offset = {trial_offsets[trial_num]:.4f} s")

    # Optional: demonstrate the math explicitly for trial 1
    if trial_offsets:
        example_trial = sorted(trial_offsets.keys())[0]
        offset = trial_offsets[example_trial]

        print(f"\nExample alignment math for Trial {example_trial}:")
        session_data_struct = bpod_data_raw["SessionData"] if isinstance(bpod_data_raw, dict) else bpod_data_raw.SessionData
        session_data_struct = convert_matlab_struct(session_data_struct)
        raw_events = convert_matlab_struct(session_data_struct["RawEvents"])
        trial_raw = convert_matlab_struct(raw_events["Trial"][example_trial - 1])

        trial_start_ts = float(to_scalar(session_data_struct["TrialStartTimestamp"], example_trial - 1))

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

    output_dir = output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_summary = create_event_summary(
        session=session_cfg,
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
            "statistics": {
                "n_trials_total": len(trials),
                "n_trials_aligned": len(trial_offsets),
            },
            "warnings": warnings,
        }
        with open(alignment_stats_path, "w") as f:
            json.dump(alignment_results, f, indent=2)
        print(f"  - Alignment results:     {alignment_stats_path}")

    print("\nSummary:")
    print("  - TTL system defines absolute time (t = 0)")
    print(f"  - Camera frames start at {camera_start_delay_s:.3f} s " "and are aligned via cam0_ttl (one pulse per frame)")
    print(f"  - Bpod trials start at {bpod_start_delay_s:.3f} s")
    print("  - Bpod sync state 'bpod_d1' triggers TTL pulses on bpod_d1_ttl (one per trial)")
    print("  - align_bpod_trials_to_ttl() uses bpod_d1_ttl to compute per-trial offsets")
    print("  - extract_trials(..., trial_offsets=...) yields trials in TTL absolute time")

    print("\nDone.")

    return {
        "config_path": session.config_path,
        "session_path": session.session_path,
        "manifest": manifest,
        "verification": verification,
        "trials": trials,
        "events": events,
        "trial_summary": trial_summary,
        "trial_summary_path": trial_summary_path,
        "trial_offsets": trial_offsets,
        "alignment_stats_path": alignment_stats_path if trial_offsets else None,
    }


if __name__ == "__main__":
    settings = ExampleSettings()
    run_pipeline(settings)
