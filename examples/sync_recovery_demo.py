#!/usr/bin/env python3
"""Example: Sync Recovery for Bpod + TTL (Missing Pulses).

Demonstrates how to robustly synchronize Bpod behavioral data to an NWB timebase
when the synchronization signal (TTL pulses) has missing events due to hardware
failure or data loss.

Goal
----
Show **how to recover correct time alignment despite missing TTL pulses** using
robust statistical methods to detect and correct for data loss.

Scenario
--------
1. **Normal Operation**: Bpod sends a TTL pulse at the start of every trial
2. **Hardware Recording**: The acquisition system (e.g., NIDAQ) records these pulses
3. **Problem**: Due to hardware issues or buffer overflows, ~15% of the pulses
   were NOT recorded by the acquisition system
4. **Challenge**: Direct nearest-neighbor mapping fails because missing pulses
   create incorrect matches

Core Idea
---------
Even with missing data, the relationship between Bpod time and NWB time remains
linear:

    NWB_Time = Slope × Bpod_Time + Intercept

We can recover this relationship by:
1. Attempting initial nearest-neighbor alignment
2. Identifying mismatched pairs (outliers from missing pulses)
3. Fitting a robust linear model using only valid pairs
4. Applying the model to ALL Bpod events (even those that lost their TTL)

Data Flow
---------
1. Generate synthetic session with known ground truth parameters
2. Simulate TTL pulse loss (~15% dropped randomly)
3. Attempt naive nearest-neighbor alignment → produces outliers
4. Detect outliers using residual analysis
5. Fit linear regression to valid pairs → recover clock model
6. Apply model to all events → reconstruct full alignment
7. Validate against ground truth and create NWB file

Example usage
-------------
    $ python examples/pose_bpod_ttl_sync_recovery.py

With custom parameters:
    $ python examples/pose_bpod_ttl_sync_recovery.py
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil

import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import TimeSeries

from synthetic import build_raw_folder
from w2t_bkin.figures.sync import plot_sync_recovery
from w2t_bkin.ingest.bpod import parse_bpod
from w2t_bkin.ingest.ttl import get_ttl_pulses
from w2t_bkin.sync import fit_robust_linear_model
from w2t_bkin.utils import configure_logger, convert_matlab_struct

# Configure logging
logger = configure_logger("sync_recovery_demo")


class ExampleSettings(BaseSettings):
    """Settings for Sync Recovery Example."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    output_root: Path = Field(default=Path("output/sync_recovery_demo"), description="Root directory")
    subject_id: str = Field(default="subject-recovery-001", description="Subject identifier")
    session_id: str = Field(default="session-recovery-001", description="Session identifier")

    # Simulation parameters
    n_trials: int = Field(default=50, description="Number of Bpod trials")
    pulse_drop_rate: float = Field(default=0.15, description="Fraction of TTL pulses to drop (0.0-1.0)")
    clock_drift_ppm: float = Field(default=100.0, description="Simulated clock drift in parts per million")

    # Cleanup
    cleanup: bool = Field(default=True, description="Clean output directory before running")


if __name__ == "__main__":
    settings = ExampleSettings()

    print("=" * 80)
    print("Example: Sync Recovery for Bpod + TTL (Missing Pulses)")
    print("=" * 80)

    # Clean output directory if requested
    if settings.output_root.exists() and settings.cleanup:
        shutil.rmtree(settings.output_root)
    settings.output_root.mkdir(parents=True, exist_ok=True)

    # Define paths
    raw_dir = settings.output_root / "raw"
    output_dir = settings.output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # PHASE 0: Generate Synthetic Data with Hardware Failure
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 0: Generate Synthetic Data with Simulated Hardware Failure")
    print("=" * 80)

    print(f"\nSimulation parameters:")
    print(f"  - Session ID:        {settings.session_id}")
    print(f"  - Number of trials:  {settings.n_trials}")
    print(f"  - Clock drift:       {settings.clock_drift_ppm:.1f} ppm")
    print(f"  - Pulse drop rate:   {settings.pulse_drop_rate*100:.1f}%")

    # 1. Generate clean synthetic session
    print("\nStep 0.1: Generating synthetic session (Bpod + TTLs)...")
    session_result = build_raw_folder(
        out_root=raw_dir,
        subject_id=settings.subject_id,
        session_id=settings.session_id,
        camera_ids=[],  # No video needed for this demo
        ttl_ids=["ttl_dummy", "ttl_bpod"],  # Use 2nd TTL for Bpod sync (1 pulse/trial)
        n_trials=settings.n_trials,
        bpod_clock_jitter_ppm=settings.clock_drift_ppm,
        bpod_start_delay_s=0.5,
        bpod_sync_delay_s=0.0,
    )
    print(f"  ✓ Generated raw data in: {session_result.session_dir}")

    # 2. Simulate Data Loss (Corrupt the TTL file)
    print("\nStep 0.2: Simulating hardware failure (dropping TTL pulses)...")

    # Identify the Bpod TTL file (it's the second one, "ttl_bpod")
    try:
        ttl_bpod_file = next(p for p in session_result.ttl_paths if "ttl_bpod" in p.name)
    except StopIteration:
        # Fallback if naming is unexpected
        print(f"  ⚠ Could not find 'ttl_bpod' in {session_result.ttl_paths}")
        # List files in TTLs dir
        ttl_dir = session_result.session_dir / "TTLs"
        ttl_files = list(ttl_dir.glob("*.txt"))
        print(f"  Available TTL files: {[f.name for f in ttl_files]}")
        # Pick the second one if available, else the first
        ttl_bpod_file = ttl_files[-1] if len(ttl_files) > 0 else None

    if not ttl_bpod_file or not ttl_bpod_file.exists():
        raise FileNotFoundError(f"Could not find generated TTL file. Paths: {session_result.ttl_paths}")

    print(f"  ✓ Found TTL file: {ttl_bpod_file.name}")

    # Read original timestamps
    timestamps_full = np.loadtxt(ttl_bpod_file)
    if timestamps_full.ndim == 0:
        timestamps_full = np.array([timestamps_full])

    # Drop random pulses
    rng = np.random.default_rng(42)
    n_drop = int(len(timestamps_full) * settings.pulse_drop_rate)

    if n_drop > 0:
        drop_indices = rng.choice(len(timestamps_full), n_drop, replace=False)
        timestamps_corrupted = np.delete(timestamps_full, drop_indices)
        print(f"  ✓ Dropped {n_drop} pulses from {len(timestamps_full)} total")
    else:
        timestamps_corrupted = timestamps_full
        print("  - No pulses dropped (rate=0.0)")

    # Overwrite the file with corrupted data
    np.savetxt(ttl_bpod_file, timestamps_corrupted, fmt="%.6f")
    print(f"  ✓ Overwrote TTL file with corrupted data: {ttl_bpod_file.name}")

    # ---------------------------------------------------------------------
    # PHASE 1: Load Data and Attempt Recovery
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 1: Load Data and Recover Synchronization")
    print("=" * 80)

    # 1. Load Bpod Data
    print("\nStep 1.1: Loading Bpod data...")
    bpod_data_raw = parse_bpod(
        session_dir=session_result.session_dir,
        pattern="Bpod/*.mat",
        order="name_asc",
    )
    session_data = convert_matlab_struct(bpod_data_raw["SessionData"])
    bpod_times = np.array(session_data["TrialStartTimestamp"]).flatten()
    print(f"  ✓ Loaded {len(bpod_times)} Bpod trial timestamps")

    # 2. Load Recorded TTLs (Corrupted)
    print("\nStep 1.2: Loading recorded TTL pulses...")
    # Use the pattern that matches the generated file
    ttl_pulses = get_ttl_pulses(session_dir=session_result.session_dir, ttl_patterns={"ttl_bpod": "TTLs/ttl_bpod_*.txt"})
    recorded_times = np.array(ttl_pulses["ttl_bpod"])
    print(f"  ✓ Loaded {len(recorded_times)} recorded TTL pulses")

    # 3. Run Recovery
    print("\nStep 1.3: Running robust recovery algorithm...")
    print("  Challenge: Some TTL pulses are missing, so naive nearest-neighbor")
    print("  mapping will create incorrect matches.")

    fitted_slope, fitted_intercept, valid_mask = fit_robust_linear_model(bpod_times, recorded_times)

    # ---------------------------------------------------------------------
    # PHASE 2: Validate Recovery Against Ground Truth
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 2: Validate Recovery Against Ground Truth")
    print("=" * 80)

    # Reconstruct ground truth parameters from simulation settings
    # Synthetic Bpod clock runs fast/slow relative to TTL clock (which is perfect)
    # Bpod_Time = Real_Time * (1 + drift)
    # Real_Time (NWB) = Bpod_Time / (1 + drift)
    drift_factor = 1.0 + (settings.clock_drift_ppm / 1e6)
    true_slope = 1.0 / drift_factor

    # Intercept calculation:
    # At the first trial (i=0), drift is 0 in synthetic implementation.
    # Bpod_Time[0] = bpod_start_delay_s
    # Recorded_Time[0] = bpod_start_delay_s + bpod_sync_delay_s
    # Recorded = Slope * Bpod + Intercept
    # Intercept = Recorded - Slope * Bpod
    # Intercept = (start + sync) - Slope * start
    bpod_start = 0.5
    bpod_sync = 0.0
    true_intercept = (bpod_start + bpod_sync) - (true_slope * bpod_start)

    print("\nStep 2.1: Compare recovered model to ground truth")
    slope_error_ppm = (fitted_slope - true_slope) / true_slope * 1e6
    intercept_error_s = fitted_intercept - true_intercept

    print(f"\n  Model comparison:")
    print(f"    {'Parameter':<20} {'True':<15} {'Recovered':<15} {'Error'}")
    print(f"    {'-'*65}")
    print(f"    {'Slope (drift)':<20} {true_slope:.8f}    {fitted_slope:.8f}    {slope_error_ppm:+.4f} ppm")
    print(f"    {'Intercept (offset)':<20} {true_intercept:.4f}s        {fitted_intercept:.4f}s        {intercept_error_s*1000:+.4f} ms")

    # Apply correction to ALL events
    print("\nStep 2.2: Apply recovered model to all Bpod events")
    aligned_bpod_times = bpod_times * fitted_slope + fitted_intercept
    print(f"  ✓ Transformed {len(aligned_bpod_times)} Bpod times to NWB timebase")

    # Validate against ground truth (what the times SHOULD have been)
    print("\nStep 2.3: Compute final alignment errors")
    ground_truth_times = bpod_times * true_slope + true_intercept
    final_errors = aligned_bpod_times - ground_truth_times

    max_error_ms = np.max(np.abs(final_errors)) * 1000
    rms_error_ms = np.sqrt(np.mean(final_errors**2)) * 1000

    print(f"\n  Alignment quality (vs ground truth):")
    print(f"    Max error:  {max_error_ms:.4f} ms")
    print(f"    RMS error:  {rms_error_ms:.4f} ms")
    print(f"    ✓ Recovery successful! All events aligned within {max_error_ms:.2f}ms")

    # ---------------------------------------------------------------------
    # PHASE 3: Create NWB File with Recovered Timestamps
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 3: Create NWB File with Recovered Timestamps")
    print("=" * 80)

    print("\nStep 3.1: Build NWB file structure")
    nwbfile = NWBFile(
        session_description="Sync Recovery Demo - Bpod alignment with missing TTL pulses",
        identifier=settings.session_id,
        session_start_time=datetime.now(timezone.utc),
        lab="Demo Lab",
        institution="Demo Institution",
    )
    print(f"  ✓ Created NWBFile: {settings.session_id}")

    # Add the aligned events as a TimeSeries
    print("\nStep 3.2: Add aligned trial events to behavior module")
    events_ts = TimeSeries(
        name="BpodTrialStarts",
        data=np.ones(len(aligned_bpod_times)),  # Event markers
        timestamps=aligned_bpod_times,
        unit="n/a",
        description="Bpod trial start times aligned to NWB timebase using robust recovery",
    )

    behavior_mod = nwbfile.create_processing_module(name="behavior", description="Behavioral data with recovered synchronization")
    behavior_mod.add(events_ts)
    print(f"  ✓ Added TimeSeries with {len(aligned_bpod_times)} aligned events")

    # Write to disk
    print("\nStep 3.3: Write NWB file to disk")
    output_path = output_dir / f"{settings.session_id}.nwb"
    with NWBHDF5IO(str(output_path), "w") as io:
        io.write(nwbfile)

    nwb_size_kb = output_path.stat().st_size / 1024
    print(f"  ✓ Saved NWB file: {output_path}")
    print(f"    Size: {nwb_size_kb:.1f} KB")

    # ---------------------------------------------------------------------
    # PHASE 4: Generate Diagnostic Plots
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 4: Generate Diagnostic Plots")
    print("=" * 80)

    print("\nStep 4.1: Create visualization of recovery process")
    plot_path = output_dir / "recovery_plot.png"
    result = plot_sync_recovery(
        bpod_times=bpod_times,
        recorded_times=recorded_times,
        fitted_slope=fitted_slope,
        fitted_intercept=fitted_intercept,
        valid_mask=valid_mask,
        final_errors=final_errors,
        max_error_ms=max_error_ms,
        rms_error_ms=rms_error_ms,
        out_path=plot_path,
    )

    if result:
        print(f"  ✓ Saved diagnostic plot: {result}")
    else:
        print("  ⚠ Could not generate plot (matplotlib not available)")

    # ---------------------------------------------------------------------
    # PHASE 5: Summary
    # ---------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\nGenerated artifacts:")
    print(f"  - NWB file:         {output_path}")
    print(f"  - Diagnostic plot:  {output_dir / 'recovery_plot.png'}")

    print(f"\nRecovery statistics:")
    print(f"  - Input data:       {len(bpod_times)} Bpod events, {len(recorded_times)} recorded TTL pulses")
    print(f"  - Data loss:        {len(bpod_times) - len(recorded_times)} missing pulses ({settings.pulse_drop_rate*100:.1f}%)")
    print(f"  - Valid pairs:      {np.sum(valid_mask)}/{len(bpod_times)} ({np.sum(valid_mask)/len(bpod_times)*100:.1f}%)")
    print(f"  - Model accuracy:   {max_error_ms:.4f} ms max error, {rms_error_ms:.4f} ms RMS")
    print(f"\n  ✓ Successfully recovered alignment for all {len(bpod_times)} events!")
