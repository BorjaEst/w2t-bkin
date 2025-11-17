"""Synthetic Bpod data generation for testing.

This module generates synthetic Bpod .mat files matching the structure expected
by the W2T-BKIN events parsing pipeline. It creates minimal but valid SessionData
structures using scipy.io.savemat.

Features:
---------
- Generate valid Bpod .mat files with SessionData structure
- Configurable number of trials and trial types
- Realistic state machine timings
- Port entry/exit events
- Deterministic generation with random seed

Requirements Coverage:
----------------------
- FR-11: Bpod .mat file generation for testing
- FR-14: Trial/event data for QC testing
"""

from pathlib import Path
import random
from typing import List, Optional

import numpy as np


def create_bpod_mat_file(
    output_path: Path,
    n_trials: int = 10,
    seed: int = 42,
    trial_types: Optional[List[int]] = None,
) -> tuple[Path, list[float]]:
    """Create a synthetic Bpod .mat file with realistic SessionData structure.

    Args:
        output_path: Path where .mat file should be written
        n_trials: Number of trials to generate
        seed: Random seed for reproducibility
        trial_types: List of trial type codes (defaults to all type 1)

    Returns:
        Tuple of (Path to created .mat file, list of sync pulse timestamps)

    Raises:
        ImportError: If scipy is not installed

    Example:
        >>> from pathlib import Path
        >>> from synthetic.bpod_synth import create_bpod_mat_file
        >>> mat_path, sync_times = create_bpod_mat_file(
        ...     Path("test_session.mat"),
        ...     n_trials=20,
        ...     seed=42
        ... )
    """
    try:
        from scipy.io import savemat
    except ImportError:
        raise ImportError("scipy is required for Bpod .mat generation. " "Install with: pip install scipy")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Set random seed
    np.random.seed(seed)
    random.seed(seed)

    # Default trial types: alternating 1 and 2
    if trial_types is None:
        trial_types = [1] * n_trials  # Use all type 1 for simplicity in synthetic sessions

    # Generate trial data
    trials = []
    trial_start_timestamps = []
    trial_end_timestamps = []
    sync_pulse_timestamps = []  # Track absolute sync pulse times for TTL generation
    current_time = 0.0

    for trial_idx in range(n_trials):
        trial_start = current_time

        # Generate realistic state timings (in seconds)
        iti_duration = np.random.uniform(1.0, 2.0)
        response_duration = np.random.uniform(3.0, 5.0)
        reward_duration = np.random.uniform(0.5, 1.0) if trial_types[trial_idx] == 1 else 0.0

        # State entry/exit times (2-element arrays: [start, end])
        iti_times = np.array([current_time, current_time + iti_duration])
        current_time += iti_duration

        # Add Bpod sync state (e.g., D1 output pulse)
        # This is a brief digital output that triggers a TTL pulse for alignment
        sync_pulse_start = current_time
        sync_pulse_duration = 0.01  # 10ms pulse
        sync_pulse_times = np.array([sync_pulse_start, sync_pulse_start + sync_pulse_duration])
        sync_pulse_timestamps.append(sync_pulse_start)  # Record absolute time for TTL
        current_time += sync_pulse_duration

        response_times = np.array([current_time, current_time + response_duration])
        current_time += response_duration

        # States dict with realistic behavioral states
        states = {
            "ITI": iti_times,
            "bpod_d1": sync_pulse_times,  # Sync signal state for TTL alignment
            "Response_window": response_times,
        }

        # Add reward state for successful trials
        if reward_duration > 0:
            reward_times = np.array([current_time, current_time + reward_duration])
            states["Reward"] = reward_times
            current_time += reward_duration
        else:
            states["Timeout"] = np.array([current_time, current_time + 1.0])
            current_time += 1.0

        # Generate port events (random port entries during response window)
        n_port_events = np.random.randint(1, 4)
        port_in_times = response_times[0] + np.sort(np.random.uniform(0, response_duration, n_port_events))
        port_out_times = port_in_times + np.random.uniform(0.05, 0.3, n_port_events)

        # Events dict
        events = {
            "Port1In": port_in_times,
            "Port1Out": port_out_times,
        }

        # Occasionally add Tup events (timer)
        if np.random.rand() > 0.5:
            events["Tup"] = np.array([response_times[0] + response_duration * 0.5])

        # Build trial structure
        trial = {
            "States": states,
            "Events": events,
        }

        trials.append(trial)
        trial_start_timestamps.append(trial_start)
        trial_end_timestamps.append(current_time)

    # Build complete SessionData structure
    session_data = {
        # Session info
        "Info": {
            "SessionDate": "2025-01-15",
            "SessionStartTime_UTC": "2025-01-15 10:00:00",
            "BpodSoftwareVersion": "2.3.0",
            "MaxStates": 256,
            "MaxSerialEvents": 15,
            "StateMachineType": "Bpod 2.0",
            "CycleFrequency": 10000,
            "SessionDateTime": "2025-01-15 10:00:00",
            "FirmwareInfo": {
                "StateMachine": 23,
                "StateMachine_Minor": 0,
            },
            "CircuitRevision": {
                "StateMachine": 2,
            },
            "Modules": {
                "nModules": 0,
                "RelayActive": np.array([], dtype=np.uint8),
                "Connected": np.array([], dtype=np.uint8),
                "Name": np.array([], dtype=object),
                "Module2SM_BaudRate": np.array([], dtype=np.uint32),
                "FirmwareVersion": np.array([], dtype=np.uint32),
                "nSerialEvents": np.array([], dtype=np.uint8),
                "EventNames": np.array([], dtype=object),
                "USBport": np.array([], dtype=object),
                "HWVersion_Major": np.array([], dtype=np.float64),
                "HWVersion_Minor": np.array([], dtype=np.float64),
            },
            "PCSetup": {
                "Manufacturer": "Test System",
                "Model": "Synthetic",
                "ProcessorName": "TestProc",
                "TotalMemory_GB": 32.0,
            },
        },
        # Analog data (minimal placeholder)
        "Analog": {
            "info": {
                "FileName": "Description: Complete path and filename of the binary file",
                "nChannels": "Description: Number of Flex I/O channels configured as analog input",
                "channelNumbers": "Description: Indexes of Flex I/O channels configured as analog input",
                "SamplingRate": "Description: Sampling rate of analog data (Hz)",
                "nSamples": "Description: Total number of analog samples captured during the session",
                "Samples": "Description: Analog measurements captured (Volts)",
                "Timestamps": "Description: Time of each sample relative to the first TTL pulse from the state machine (seconds)",
                "TrialNumber": "Description: Experimental trial for each corresponding sample",
                "Trial": "Description: Cell array with one cell per trial. Each cell contains analog samples captured during that trial.",
            },
            "FileName": "",
            "nChannels": 0,
            "channelNumbers": np.array([], dtype=np.uint8),
            "SamplingRate": 0,
            "nSamples": 0,
        },
        # Settings file (minimal)
        "SettingsFile": {
            "GUI": {
                "RewardAmount": 5.0,
                "TimeoutDuration": 1.0,
                "ITIMin": 1.0,
                "ITIMax": 2.0,
            },
            "protocol": "SyntheticProtocol",
        },
        # Trial counts and types
        "nTrials": n_trials,
        "TrialTypes": np.array(trial_types, dtype=np.uint8),
        # Trial timestamps
        "TrialStartTimestamp": np.array(trial_start_timestamps, dtype=np.float64),
        "TrialEndTimestamp": np.array(trial_end_timestamps, dtype=np.float64),
        # Trial settings (one per trial)
        "TrialSettings": [{"RewardAmount": 5.0, "TimeoutDuration": 1.0} for _ in range(n_trials)],
        # Raw events (list of trials)
        "RawEvents": {
            "Trial": trials,
        },
        # Raw data (state names)
        "RawData": {
            "OriginalStateNamesByNumber": np.array([[[""] * 256 for _ in range(n_trials)]], dtype=object),  # Empty state names for each trial
        },
    }

    # Wrap in top-level structure with MATLAB metadata
    mat_data = {
        "__header__": b"MATLAB 5.0 MAT-file, Created by synthetic.bpod_synth",
        "__version__": "1.0",
        "__globals__": [],
        "SessionData": session_data,
    }

    # Save to .mat file
    savemat(
        output_path,
        mat_data,
        do_compression=True,
        oned_as="row",
    )

    return output_path, sync_pulse_timestamps


def create_simple_bpod_file(
    output_path: Path,
    n_trials: int = 5,
    seed: int = 42,
) -> tuple[Path, list[float]]:
    """Create a minimal Bpod .mat file for quick tests.

    This creates a simplified version with fewer states and events,
    suitable for unit tests that don't need full complexity.

    Args:
        output_path: Path where .mat file should be written
        n_trials: Number of trials (default: 5 for fast tests)
        seed: Random seed

    Returns:
        Tuple of (Path to created .mat file, list of sync pulse timestamps)
    """
    return create_bpod_mat_file(
        output_path,
        n_trials=n_trials,
        seed=seed,
        trial_types=[1] * n_trials,  # All same type
    )
