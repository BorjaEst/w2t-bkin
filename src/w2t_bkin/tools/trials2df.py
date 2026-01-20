#!/usr/bin/env python
"""Convert TrialsTable and Task to analysis-ready DataFrame.

This script demonstrates how to convert ndx-structured-behavior objects into
a flat pandas DataFrame suitable for analysis.

The resulting DataFrame includes:
- trial_id: Trial number (index)
- trial_type: Integer enum (1=W2T_Audio, 2=A2L_Audio, 3=Microstim)
- cue_name: String name of the cue state
- cue_start_time: Timestamp when cue started (seconds)
- outcome: Integer enum (0=Miss, 1=Hit)
- outcome_time: Timestamp of outcome state (seconds)
- start_time: Trial start timestamp (seconds)
- stop_time: Trial stop timestamp (seconds)

Usage:
    python scripts/trials_to_dataframe.py

Example:
    python scripts/trials_to_dataframe.py
"""

from pathlib import Path
import warnings

from ndx_structured_behavior import Task, TrialsTable
import numpy as np
import pandas as pd

from w2t_bkin import config, sync
from w2t_bkin.ingest import behavior, bpod, events


def trials_to_dataframe(trials: TrialsTable, task: Task) -> pd.DataFrame:
    """Convert TrialsTable and Task to a consolidated pandas DataFrame.

    Creates a DataFrame with trial-level metrics including trial type, outcome
    classification, and key event timings. This provides a flat, analysis-ready
    representation of the structured behavioral data.

    Args:
        trials: TrialsTable from extract_trials_table()
        task: Task container with metadata (state_types, event_types, etc.)

    Returns:
        pd.DataFrame with columns:
            - trial_id (index): Trial number (0-based)
            - trial_type: Integer enum (1=W2T_Audio, 2=A2L_Audio, 3=Microstim)
            - cue_name: String name of the cue state
            - cue_start_time: Timestamp when cue started (seconds)
            - outcome: Integer enum (0=Miss, 1=Hit, NaN if neither)
            - outcome_time: Timestamp of outcome state (seconds, NaN if missing)
            - start_time: Trial start timestamp (seconds)
            - stop_time: Trial stop timestamp (seconds)

    Note:
        - Uses hardcoded mappings: W2T_Audio→1, A2L_Audio→2, Microstim→3
        - Outcome based on HIT → 1, Miss → 0
        - If multiple cue states exist in a trial, takes first occurrence with warning
        - Missing states result in NaN values
    """
    # Build state name to type index mapping
    state_types = task.state_types
    state_name_to_idx = {name: idx for idx, name in enumerate(state_types["state_name"].data)}

    # Hardcoded cue state mappings: state_name → trial_type
    CUE_STATE_TO_TYPE = {
        "W2T_Audio": 1,
        "A2L_Audio": 2,
        "Microstim": 3,
    }

    # Hardcoded outcome state names: state_name → outcome value
    OUTCOME_STATES = {
        "HIT": 1,
        "Miss": 0,
    }

    # Get states table for dereferencing
    states_table = trials.states.table
    # Access raw data arrays (not DataFrame which expands references)
    state_types_data = states_table.state_type.data  # Indices into StateTypesTable
    state_start_times = states_table.start_time.data

    # Result storage
    results = []

    # Get ragged array indices for states
    states_data = trials.states.data  # Flat list of all state indices
    states_index = trials.states_index.data  # Cumulative indices marking trial boundaries

    for trial_idx in range(len(trials)):
        # Get state indices for this trial using ragged array indexing
        start_idx = 0 if trial_idx == 0 else states_index[trial_idx - 1]
        end_idx = states_index[trial_idx]
        state_indices_list = states_data[start_idx:end_idx]

        # Get trial start/stop times
        trial_start = trials.start_time.data[trial_idx]
        trial_stop = trials.stop_time.data[trial_idx]

        if not state_indices_list:
            # Trial has no states - populate with NaNs
            results.append(
                {
                    "trial_id": trial_idx,
                    "trial_type": np.nan,
                    "cue_name": None,
                    "cue_start_time": np.nan,
                    "outcome": np.nan,
                    "outcome_time": np.nan,
                    "start_time": trial_start,
                    "stop_time": trial_stop,
                }
            )
            continue

        # Get state type indices and timings for this trial
        trial_state_types = [state_types_data[idx] for idx in state_indices_list]
        trial_state_start_times = [state_start_times[idx] for idx in state_indices_list]

        # Find cue state (first occurrence)
        cue_name = None
        cue_start_time = np.nan
        trial_type = np.nan

        for cue_state_name, cue_type in CUE_STATE_TO_TYPE.items():
            if cue_state_name in state_name_to_idx:
                cue_state_idx = state_name_to_idx[cue_state_name]
                # Find matching states in this trial
                matching_indices = [i for i, st in enumerate(trial_state_types) if st == cue_state_idx]

                if len(matching_indices) > 0:
                    if len(matching_indices) > 1:
                        warnings.warn(
                            f"Trial {trial_idx}: Multiple '{cue_state_name}' states found. Using first occurrence.",
                            UserWarning,
                        )

                    cue_name = cue_state_name
                    trial_type = cue_type
                    cue_start_time = trial_state_start_times[matching_indices[0]]
                    break  # Use first matching cue type found

        # Find outcome state (first occurrence)
        outcome = np.nan
        outcome_time = np.nan

        for outcome_state_name, outcome_value in OUTCOME_STATES.items():
            if outcome_state_name in state_name_to_idx:
                outcome_state_idx = state_name_to_idx[outcome_state_name]
                # Find matching states in this trial
                matching_indices = [i for i, st in enumerate(trial_state_types) if st == outcome_state_idx]

                if len(matching_indices) > 0:
                    if len(matching_indices) > 1:
                        warnings.warn(
                            f"Trial {trial_idx}: Multiple '{outcome_state_name}' states found. Using first occurrence.",
                            UserWarning,
                        )

                    outcome = outcome_value
                    outcome_time = trial_state_start_times[matching_indices[0]]
                    break  # Use first matching outcome found

        # Collect trial metrics
        results.append(
            {
                "trial_id": trial_idx,
                "trial_type": trial_type,
                "cue_name": cue_name,
                "cue_start_time": cue_start_time,
                "outcome": outcome,
                "outcome_time": outcome_time,
                "start_time": trial_start,
                "stop_time": trial_stop,
            }
        )

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df.set_index("trial_id", inplace=True)

    return df


def main():
    """Convert behavioral data to analysis DataFrame."""
    # Ensure we're in the project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Load configuration
    settings = config.load_config(project_root / "configs/standard.toml")
    session_dir = project_root / "data/raw/Session-000001"

    # Load TTL pulses (use corrected 3-trial file for this example)
    ttl_patterns = {
        "ttl_camera": "TTLs/*.xa_7_0*.txt",
        "ttl_cue": "TTLs/corrected_3_trials_TTLs.txt",  # Limited to 3 trials
    }
    ttl_pulses = events.get_ttl_pulses(session_dir, ttl_patterns)

    # Parse Bpod data
    bpod_data = bpod.parse_bpod(session_dir=session_dir, pattern="Bpod/*.mat", order="name_asc", continuous_time=False)

    # Compute trial offsets (sync to TTL)
    trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
        trial_type_configs=settings.bpod.sync.trial_types,
        bpod_data=bpod_data,
        ttl_pulses=ttl_pulses,
    )

    # Extract NWB objects
    task = behavior.extract_task(bpod_data)
    trials = behavior.extract_trials_table(bpod_data, trial_offsets)

    # Convert to analysis-ready DataFrame
    df = trials_to_dataframe(trials, task)

    # Display results
    print("=" * 80)
    print("TRIALS DATAFRAME")
    print("=" * 80)
    print(df)
    print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print("\nTrial counts by type:")
    print(df.groupby("trial_type")["cue_name"].value_counts())
    print("\nOutcome summary (by trial type and outcome):")
    print(df.groupby(["trial_type", "outcome"]).size())
    print("\nTrial duration statistics:")
    trial_durations = df["stop_time"] - df["start_time"]
    print(trial_durations.describe())

    # Save to CSV
    output_path = project_root / "output/trials_dataframe.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    print(f"\n✓ Saved DataFrame to: {output_path}")


if __name__ == "__main__":
    main()
