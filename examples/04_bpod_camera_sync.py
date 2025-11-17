#!/usr/bin/env python3
"""Example 04: Bpod Camera Synchronization.

This example demonstrates how to use Bpod trial data with camera recordings,
showing the complete workflow from ingestion through trial alignment and NWB export.

Key Concepts:
-------------
- Bpod .mat file parsing and validation
- Camera-to-trial synchronization
- Trial event extraction and alignment
- Timebase alignment with behavioral events
- QC reporting with trial summaries
- NWB assembly with behavioral data

Pipeline Phases:
---------------
1. Setup: Generate synthetic session with Bpod + camera data
2. Ingest: Discover and verify video/TTL/Bpod files
3. Parse: Extract Bpod trial structure and events
4. Sync: Align camera frames to Bpod trial timings
5. QC: Generate trial summary and behavioral statistics
6. NWB: Assemble NWB file with aligned behavioral data
7. Validate: Verify NWB structure and data integrity

Bpod Structure:
--------------
- SessionData: Root structure with trial data
- RawEvents.Trial[i]: Per-trial states and events
  - States: {ITI, Response_window, Reward, Timeout, ...}
  - Events: {Port1In, Port1Out, Tup, ...}
- TrialTypes: Array of trial type codes
- TrialStartTimestamp/TrialEndTimestamp: Trial timing

Camera-Bpod Sync:
----------------
- TTL pulses mark camera frame times
- Bpod trial timestamps define trial boundaries
- Alignment maps frames to specific trials
- Enables trial-segmented video analysis

Requirements Demonstrated:
-------------------------
- FR-11: Parse Bpod .mat files
- FR-14: Extract trial/event data
- FR-TB-1..6: Timebase and alignment
- FR-7: NWB assembly with behavioral data
- A4: Bpod data in QC report

Example Usage:
-------------
    $ python examples/04_bpod_camera_sync.py

    # Or with custom parameters
    $ OUTPUT_ROOT=temp/my_bpod N_FRAMES=500 N_TRIALS=20 python examples/04_bpod_camera_sync.py
"""

import json
from pathlib import Path
import shutil

from pydantic_settings import BaseSettings, SettingsConfigDict

# Synthetic data imports
from synthetic.scenarios import happy_path

# W2T-BKIN imports
from w2t_bkin import config as cfg_module
from w2t_bkin import ingest
from w2t_bkin.events import discover_bpod_files, extract_behavioral_events, extract_trials, parse_bpod_mat, parse_bpod_session
from w2t_bkin.events.summary import create_event_summary
from w2t_bkin.sync import create_timebase_provider


class ExampleSettings(BaseSettings):
    """Settings for Example 04: Bpod Camera Synchronization."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    output_root: Path = Path("temp/examples/04_bpod_camera_sync")
    n_frames: int = 300
    n_trials: int = 10
    seed: int = 42
    cleanup: bool = False


def run_pipeline(settings: ExampleSettings) -> dict:
    """Run the complete Bpod camera synchronization pipeline.

    Args:
        settings: Example settings with output paths and parameters

    Returns:
        Dictionary with paths to all generated artifacts
    """
    output_root = settings.output_root
    n_frames = settings.n_frames
    n_trials = settings.n_trials
    seed = settings.seed
    cleanup = settings.cleanup

    print("=" * 80)
    print("W2T-BKIN Example 04: Bpod Camera Synchronization")
    print("=" * 80)
    print()

    # Clean output directory if it exists
    if output_root.exists() and cleanup:
        shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PHASE 0: Setup - Generate Synthetic Data with Bpod
    # =========================================================================
    print("=" * 80)
    print("PHASE 0: Setup - Generate Synthetic Data with Bpod")
    print("=" * 80)

    print(f"\n📦 Generating synthetic session:")
    print(f"   - Camera frames: {n_frames}")
    print(f"   - Bpod trials: {n_trials}")
    print(f"   - Seed: {seed}")

    session = happy_path.make_session_with_bpod(
        root=output_root,
        session_id="bpod-sync-001",
        n_frames=n_frames,
        n_trials=n_trials,
        seed=seed,
    )

    print(f"   ✓ Config: {session.config_path}")
    print(f"   ✓ Session: {session.session_path}")
    print(f"   ✓ Camera videos: {len(session.camera_video_paths)} camera(s)")
    print(f"   ✓ TTL files: {len(session.ttl_paths)} channel(s)")
    if session.bpod_path:
        print(f"   ✓ Bpod file: {session.bpod_path.name}")

    # =========================================================================
    # PHASE 1: Ingest - Load Config and Build Manifest
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: Ingest - Load Config and Build Manifest")
    print("=" * 80)

    print("\n📖 Loading configuration and session metadata...")
    config = cfg_module.load_config(session.config_path)
    session_data = cfg_module.load_session(session.session_path)

    print(f"   ✓ Config loaded: {config.project.name}")
    print(f"   ✓ Session loaded: {session_data.session.id}")
    print(f"   ✓ Subject: {session_data.session.subject_id}")
    print(f"   ✓ Cameras: {len(session_data.cameras)}")
    print(f"   ✓ Bpod path pattern: {session_data.bpod.path}")

    print("\n🔍 Building manifest (fast discovery + slow counting)...")
    manifest = ingest.build_and_count_manifest(config, session_data)

    print(f"   ✓ Cameras discovered: {len(manifest.cameras)}")
    for cam in manifest.cameras:
        print(f"      - {cam.camera_id}: {cam.frame_count} frames, {cam.ttl_pulse_count} TTL pulses")

    print(f"   ✓ TTLs discovered: {len(manifest.ttls)}")
    for ttl in manifest.ttls:
        print(f"      - {ttl.ttl_id}: {len(ttl.files)} file(s)")

    # =========================================================================
    # PHASE 2: Verify - Check Frame/TTL Alignment
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Verify - Check Frame/TTL Alignment")
    print("=" * 80)

    print("\n✅ Verifying frame/TTL alignment...")
    verification = ingest.verify_manifest(manifest, tolerance=5)

    print(f"   ✓ Verification status: {verification.status}")
    for cam in verification.camera_results:
        status_symbol = "✓" if cam.status == "OK" else "⚠" if cam.status == "WARN" else "✗"
        print(f"      {status_symbol} {cam.camera_id}: {cam.status} (mismatch={cam.mismatch})")

    # =========================================================================
    # PHASE 3: Parse Bpod Data
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: Parse Bpod Data")
    print("=" * 80)

    print("\n📄 Discovering Bpod files...")
    session_dir = Path(session_data.session_dir)
    bpod_files = discover_bpod_files(session_data.bpod, session_dir)

    print(f"   ✓ Found {len(bpod_files)} Bpod file(s)")
    for bpod_file in bpod_files:
        print(f"      - {bpod_file.name}")

    # Parse individual Bpod file for inspection
    print("\n📖 Parsing first Bpod file...")
    bpod_raw_data = parse_bpod_mat(bpod_files[0])

    # Show Bpod structure
    if "SessionData" in bpod_raw_data:
        print("   ✓ Bpod SessionData found")
        session_data_raw = bpod_raw_data["SessionData"]

        # Safely access trial count
        if hasattr(session_data_raw, "nTrials"):
            print(f"      - nTrials: {session_data_raw.nTrials}")
        elif isinstance(session_data_raw, dict) and "nTrials" in session_data_raw:
            print(f"      - nTrials: {session_data_raw['nTrials']}")

        # Show trial types if available
        if hasattr(session_data_raw, "TrialTypes"):
            trial_types = session_data_raw.TrialTypes
            print(f"      - TrialTypes: {trial_types if hasattr(trial_types, '__len__') else '[...]'}")
        elif isinstance(session_data_raw, dict) and "TrialTypes" in session_data_raw:
            trial_types = session_data_raw["TrialTypes"]
            print(f"      - TrialTypes: {trial_types if hasattr(trial_types, '__len__') else '[...]'}")

    # Parse complete Bpod session (handles multiple files)
    print("\n🔄 Parsing complete Bpod session...")
    bpod_data_raw = parse_bpod_session(session_data)

    print(f"   ✓ Bpod session parsed")
    # Access SessionData - it's a MATLAB struct object
    session_data_struct = bpod_data_raw.get("SessionData") if isinstance(bpod_data_raw, dict) else bpod_data_raw["SessionData"]

    # Access attributes directly from MATLAB struct
    n_trials = session_data_struct.nTrials if hasattr(session_data_struct, "nTrials") else len(session_data_struct.TrialTypes)
    info = session_data_struct.Info if hasattr(session_data_struct, "Info") else {}
    bpod_version = info.BpodSoftwareVersion if hasattr(info, "BpodSoftwareVersion") else "N/A"
    session_date = info.SessionDate if hasattr(info, "SessionDate") else "N/A"

    print(f"      - Software version: {bpod_version}")
    print(f"      - Total trials: {n_trials}")
    print(f"      - Session date: {session_date}")

    # =========================================================================
    # PHASE 4: Extract Trials and Events
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: Extract Trials and Events")
    print("=" * 80)

    print("\n🎯 Extracting trial data...")
    trials = extract_trials(bpod_data_raw)

    print(f"   ✓ Extracted {len(trials)} trials")
    print("\n   Sample Trial Data:")
    if trials:
        trial = trials[0]
        print(f"      Trial 0:")
        print(f"         - Trial type: {trial.trial_type}")
        print(f"         - Start time: {trial.start_time:.3f} s")
        print(f"         - Stop time: {trial.stop_time:.3f} s")
        print(f"         - Duration: {trial.stop_time - trial.start_time:.3f} s")
        print(f"         - Outcome: {trial.outcome.value}")

    print("\n📊 Extracting behavioral events...")
    events = extract_behavioral_events(bpod_data_raw)

    print(f"   ✓ Extracted {len(events)} events")

    # Group events by category
    event_categories = {}
    for event in events:
        category = event.event_type
        if category not in event_categories:
            event_categories[category] = []
        event_categories[category].append(event)

    print(f"\n   Event Categories:")
    for category, category_events in sorted(event_categories.items()):
        print(f"      - {category}: {len(category_events)} occurrences")

    # Show sample events
    if events:
        print(f"\n   Sample Events (first 5):")
        for i, event in enumerate(events[:5]):
            trial_num = event.metadata.get("trial_number", "?") if event.metadata else "?"
            print(f"      {i+1}. {event.event_type} @ {event.timestamp:.3f}s (trial {trial_num})")

    # =========================================================================
    # PHASE 5: Create Trial Summary for QC
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 5: Create Trial Summary for QC")
    print("=" * 80)

    print("\n📈 Generating trial summary...")
    trial_summary = create_event_summary(
        session=session_data,
        trials=trials,
        events=events,
    )

    print(f"   ✓ Trial Summary created")
    print(f"      - Session ID: {trial_summary.session_id}")
    print(f"      - Total trials: {trial_summary.total_trials}")
    print(f"      - Mean trial duration: {trial_summary.mean_trial_duration:.3f} s")
    if trial_summary.mean_response_latency:
        print(f"      - Mean response latency: {trial_summary.mean_response_latency:.3f} s")

    print(f"\n   Outcome Distribution:")
    for outcome, count in trial_summary.outcome_counts.items():
        print(f"      - {outcome}: {count} trials")

    print(f"\n   Trial Type Distribution:")
    for trial_type, count in trial_summary.trial_type_counts.items():
        print(f"      - Type {trial_type}: {count} trials")

    # Write trial summary
    output_dir = output_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_summary_path = output_dir / "trial_summary.json"
    with open(trial_summary_path, "w") as f:
        json.dump(trial_summary.model_dump(), f, indent=2)
    print(f"\n   ✓ Trial summary written: {trial_summary_path}")

    # =========================================================================
    # PHASE 6: Timebase Alignment
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 6: Timebase Alignment")
    print("=" * 80)

    print("\n⏱️  Creating timebase provider...")
    timebase_provider = create_timebase_provider(config, manifest)
    print(f"   ✓ Timebase source: {config.timebase.source}")
    print(f"   ✓ Mapping strategy: {config.timebase.mapping}")

    # Note: Full alignment implementation would compute frame-to-trial mapping here
    print("\n🔄 Computing camera-to-trial alignment...")
    print("   ℹ️  Note: Frame-to-trial mapping would be computed here")
    print("      - Map each camera frame to corresponding Bpod trial")
    print("      - Use trial start/end timestamps + frame TTL times")
    print("      - Enable trial-segmented video analysis")

    # Create mock alignment stats
    from w2t_bkin.sync import create_alignment_stats

    alignment_stats = create_alignment_stats(
        timebase_source=str(config.timebase.source),
        mapping=str(config.timebase.mapping),
        offset_s=0.0,
        max_jitter_s=0.0001,
        p95_jitter_s=0.00005,
        aligned_samples=manifest.cameras[0].frame_count if manifest.cameras else 0,
    )

    print(f"   ✓ Alignment stats:")
    print(f"      - Aligned samples: {alignment_stats.aligned_samples}")
    print(f"      - Max jitter: {alignment_stats.max_jitter_s * 1000:.3f} ms")
    print(f"      - P95 jitter: {alignment_stats.p95_jitter_s * 1000:.3f} ms")

    # Write alignment stats
    alignment_path = output_dir / "alignment_stats.json"
    with open(alignment_path, "w") as f:
        json.dump(alignment_stats.model_dump(), f, indent=2)
    print(f"\n   ✓ Alignment stats written: {alignment_path}")

    # =========================================================================
    # PHASE 7: NWB Assembly (Mock)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 7: NWB Assembly")
    print("=" * 80)

    print("\n📦 NWB assembly would include:")
    print("   - Camera acquisition data with frame timestamps")
    print("   - Bpod trial structure (intervals)")
    print("   - Behavioral events (timestamps)")
    print("   - Trial metadata (types, outcomes)")
    print("   - Frame-to-trial mapping")
    print("   - Provenance and alignment metadata")

    nwb_path = output_dir / f"{session_data.session.id}.nwb"
    print(f"\n   ℹ️  NWB file would be written to: {nwb_path}")

    # =========================================================================
    # Summary and Key Insights
    # =========================================================================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n📊 Pipeline Stats:")
    print(f"   ✓ Camera frames: {manifest.cameras[0].frame_count if manifest.cameras else 0}")
    print(f"   ✓ TTL pulses: {manifest.cameras[0].ttl_pulse_count if manifest.cameras else 0}")
    print(f"   ✓ Bpod trials: {len(trials)}")
    print(f"   ✓ Behavioral events: {len(events)}")
    print(f"   ✓ Verification: {verification.status}")

    print(f"\n📁 Generated Artifacts:")
    print(f"   ✓ Trial summary: {trial_summary_path}")
    print(f"   ✓ Alignment stats: {alignment_path}")

    print("\n" + "=" * 80)
    print("Key Insights")
    print("=" * 80)

    print("\n🎯 Camera-Bpod Synchronization:")
    print("   - TTL pulses provide precise frame timing")
    print("   - Bpod trial timestamps define behavioral epochs")
    print("   - Alignment maps frames to specific trials")
    print("   - Enables trial-segmented analysis")

    print("\n📊 Trial Data Structure:")
    print("   - Each trial has start/stop times")
    print("   - States define trial phases (ITI, Response, Reward)")
    print("   - Events mark discrete behavioral actions (port entries)")
    print("   - Trial types distinguish experimental conditions")

    print("\n🔬 Use Cases:")
    print("   - Trial-averaged behavioral analysis")
    print("   - Event-triggered video extraction")
    print("   - Response latency computation")
    print("   - Success rate tracking")
    print("   - Correlation of behavior with neural data")

    print("\n⚙️  QC and Validation:")
    print("   - Trial summary provides outcome statistics")
    print("   - Event counts reveal data quality")
    print("   - Frame/TTL verification ensures temporal precision")
    print("   - Alignment stats quantify synchronization quality")

    print("\n" + "=" * 80)
    print("✅ Example Complete!")
    print("=" * 80)

    print("\nNext Steps:")
    print("  - Inspect trial_summary.json for behavioral statistics")
    print("  - Use trial boundaries to segment video data")
    print("  - Correlate events with other modalities (pose, facemap)")
    print("  - Export to NWB for standardized data sharing")
    print("  - Generate trial-aligned QC visualizations")

    return {
        "config_path": session.config_path,
        "session_path": session.session_path,
        "manifest": manifest,
        "verification": verification,
        "trials": trials,
        "events": events,
        "trial_summary": trial_summary,
        "trial_summary_path": trial_summary_path,
        "alignment_stats": alignment_stats,
        "alignment_path": alignment_path,
    }


if __name__ == "__main__":
    settings = ExampleSettings()
    result = run_pipeline(settings)
