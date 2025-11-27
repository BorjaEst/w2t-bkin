# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings. It integrates synchronization, pose estimation (DeepLabCut/SLEAP), facial metrics, and behavioral events into standardized **NWB (Neurodata Without Borders)** datasets.

## Key Features

- **NWB-First Architecture**: Produces NWB-native data structures directly, eliminating intermediate conversion layers.
- **Bpod Integration**: Parses Bpod `.mat` files and converts them to `ndx-structured-behavior` format.
- **Pose Estimation**: Imports and harmonizes data from DeepLabCut and SLEAP into `ndx-pose`.
- **Synchronization**: Robust alignment of behavioral data and video frames to a common timebase using TTL pulses.
- **Modular Design**: Distinct modules for behavior, pose, sync, and session management.

## Installation

The project requires Python ~3.10.

1. **Install `ndx-structured-behavior`** (currently required from source):

   ```bash
   git clone https://github.com/rly/ndx-structured-behavior.git
   pip install -U ./ndx-structured-behavior
   ```

2. **Install `w2t-bkin`**:

   ```bash
   pip install w2t-bkin
   ```

## Configuration

The pipeline uses TOML for configuration. The main config file (e.g., `configs/standard.toml`) defines:

- **Paths**: `raw_root`, `intermediate_root`, `output_root` for data management.
- **Bpod Sync**: Maps trial types to specific sync signals and TTL channels (e.g., `W2T_Audio` -> `ttl_cue`).
- **Logging**: Sets logging levels and formats.

Session-specific metadata is handled via `metadata.toml` files located in each session directory.

## Quick Start

Here is a core pipeline example:

```python
from pathlib import Path
from w2t_bkin import behavior, bpod, config, session, sync, ttl

# 1. Load Configuration
settings = config.load_config("configs/standard.toml")
rawdata_dir = settings.paths.raw_root / "Session-000001"

# 2. Initialize NWB File
nwbfile = session.create_nwb_file(rawdata_dir / "metadata.toml")

# 3. Import TTL Signals
ttl_patterns = {
    "ttl_camera": "TTLs/*.xa_7_0*.txt",
    "ttl_cue": "TTLs/*.xia_3_0*.txt",
}
ttl_pulses = ttl.get_ttl_pulses(rawdata_dir, ttl_patterns)

# 4. Parse Bpod Data
bpod_data = bpod.parse_bpod(rawdata_dir, pattern="Bpod/*.mat", order="name_asc")

# 5. Synchronize Bpod to TTL
trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
    trial_type_configs=settings.bpod.sync.trial_types,
    bpod_data=bpod_data,
    ttl_pulses=ttl_pulses,
)

# 6. Extract Behavioral Data (NWB objects)
task, recording, trials = behavior.extract_behavioral_data(bpod_data, trial_offsets)

# 7. Create TTL Events Table
ttl_table = ttl.extract_ttl_table(ttl_pulses)

# 8. Assemble NWB
nwbfile.add_acquisition(ttl_table)
nwbfile.add_lab_meta_data(task)
nwbfile.add_acquisition(recording.states)
nwbfile.add_acquisition(recording.events)
nwbfile.add_acquisition(recording.actions)
nwbfile.trials = trials
```

## Module Overview

| Module              | Description                                                                                        |
| :------------------ | :------------------------------------------------------------------------------------------------- |
| `w2t_bkin.behavior` | Converts Bpod data into `ndx-structured-behavior` classes (StatesTable, EventsTable, TrialsTable). |
| `w2t_bkin.bpod`     | Low-level parsing and validation of Bpod `.mat` files.                                             |
| `w2t_bkin.pose`     | Imports pose estimation data (DLC/SLEAP) and builds `ndx-pose` objects (PoseEstimation, Skeleton). |
| `w2t_bkin.sync`     | Handles timebase alignment, jitter calculation, and synchronization of video/behavior to TTLs.     |
| `w2t_bkin.ttl`      | Loads hardware TTL pulse timestamps and creates `ndx-events` tables.                               |
| `w2t_bkin.session`  | Loads `pynwb` metadata and assembles the root `NWBFile`.                                           |
| `w2t_bkin.pipeline` | High-level orchestration of the entire workflow.                                                   |

## CLI Utilities

The `scripts/` directory contains useful utilities:

- `mat2json.py`: Converts MATLAB `.mat` files to JSON, handling nested structures and arrays.
- `pose2ttl.py`: Generates mock TTL signals from DeepLabCut pose data (useful for testing or when hardware sync fails).
- `trials2df.py`: Converts NWB `TrialsTable` and `TaskRecording` objects into a flat pandas DataFrame for analysis.

## License

See `LICENSE` file for details.
