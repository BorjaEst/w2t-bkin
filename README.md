# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings. It integrates synchronization, pose estimation (DeepLabCut/SLEAP), facial metrics, and behavioral events into standardized **NWB (Neurodata Without Borders)** datasets.

## Key Features

- **NWB-First Architecture**: Produces NWB-native data structures directly, eliminating intermediate conversion layers.
- **Hierarchical Metadata**: Supports cascading configuration from global → subject → session levels for efficient metadata management.
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

## Project Structure

```text
project/
├── config.toml              # Pipeline configuration
├── data/
│   ├── raw/                 # Raw data organized by subject/session
│   │   ├── metadata.toml    # Optional: Global metadata (lab-wide defaults)
│   │   └── subject-001/
│   │       ├── subject.toml # Optional: Subject-specific metadata
│   │       └── session-001/
│   │           ├── session.toml  # Session-specific NWB metadata
│   │           ├── Video/        # Raw video files
│   │           ├── TTLs/         # TTL pulse timestamps
│   │           └── Bpod/         # Bpod behavior files
│   ├── interim/             # Processed data (pose estimation, etc.)
│   │   └── subject-001/
│   │       └── session-001/
│   │           └── Pose/
│   └── processed/           # Final NWB output files
└── models/                  # Pose estimation models (DLC/SLEAP)
```

## Configuration

The pipeline uses TOML for configuration:

### Pipeline Configuration (`config.toml`)

Defines paths, timebase, and synchronization settings:

```toml
[project]
name = "my-experiment"

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"
root_metadata = "data/raw/metadata.toml"  # Optional global metadata

[timebase]
source = "ttl"
ttl_id = "ttl_camera"
mapping = "nearest"
jitter_budget_s = 0.001

[[bpod.sync.trial_types]]
trial_type = 1
sync_signal = "W2T_Audio"
sync_ttl = "ttl_cue"
```

### Hierarchical Metadata

Metadata is loaded and merged from multiple levels (later files override earlier ones):

1. **`root_metadata`** (optional): Lab/project-wide defaults
2. **`raw_root/metadata.toml`** (optional): Experiment-wide settings
3. **`raw_root/subject_id/subject.toml`** (optional): Subject-specific metadata
4. **`raw_root/subject_id/session_id/session.toml`**: Session-specific NWB metadata

Example `session.toml`:

```toml
session_description = "Behavioral training with pose tracking"
identifier = "session-001"
session_start_time = "2025-11-21T14:30:00Z"
experimenter = ["Esteban, Borja"]
institution = "My Lab"
lab = "Neuroscience Lab"

[subject]
subject_id = "subject-001"
species = "Mus musculus"
sex = "M"
age = "P90D"
```

## Quick Start

### Using the High-Level Helper

```python
from pathlib import Path
from w2t_bkin.config import load_config
from w2t_bkin.utils import load_session_metadata_and_nwb

# Load configuration
config = load_config("config.toml")

# Load hierarchical metadata and create NWBFile in one step
metadata, nwbfile = load_session_metadata_and_nwb(
    config=config,
    subject_id="subject-001",
    session_id="session-001"
)

# Continue with your pipeline...
```

### Manual Approach

```python
from pathlib import Path
from w2t_bkin import behavior, bpod, config, session, sync, ttl

# 1. Load Configuration
settings = config.load_config("config.toml")

# 2. Build metadata paths and load hierarchically
metadata_paths = session.build_metadata_paths(
    raw_root=settings.paths.raw_root,
    subject_id="subject-001",
    session_id="session-001",
    root_metadata=settings.paths.root_metadata
)
metadata = session.load_metadata(metadata_paths)

# 3. Create NWBFile
nwbfile = session.create_nwb_file(metadata)

# 4. Get session directory
session_dir = settings.paths.raw_root / "subject-001" / "session-001"

# 5. Import TTL Signals
ttl_patterns = {
    "ttl_camera": "TTLs/*.xa_7_0*.txt",
    "ttl_cue": "TTLs/*.xia_3_0*.txt",
}
ttl_pulses = ttl.get_ttl_pulses(session_dir, ttl_patterns)

# 6. Parse Bpod Data
bpod_data = bpod.parse_bpod(
    session_dir=session_dir,
    pattern="Bpod/*.mat",
    order="name_asc"
)

# 7. Synchronize Bpod to TTL
trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
    trial_type_configs=settings.bpod.sync.trial_types,
    bpod_data=bpod_data,
    ttl_pulses=ttl_pulses,
)

# 8. Extract Behavioral Data (NWB objects)
task, recording, trials = behavior.extract_behavioral_data(
    bpod_data,
    trial_offsets
)

# 9. Add to NWB
nwbfile.add_lab_meta_data(task)
nwbfile.add_acquisition(recording.states)
nwbfile.add_acquisition(recording.events)
nwbfile.add_acquisition(recording.actions)
nwbfile.trials = trials
```

## Examples

The `examples/` directory contains complete working examples:

- **`bpod_camera_sync.py`**: Demonstrates Bpod-camera synchronization with TTL alignment
- **`pose_camera_nwb.py`**: Shows pose estimation data import and NWB file creation
- **`sync_recovery_demo.py`**: Robust sync recovery with missing TTL pulses

Run an example:

```bash
python examples/pose_camera_nwb.py
```

## Module Overview

| Module                 | Description                                                                                        |
| :--------------------- | :------------------------------------------------------------------------------------------------- |
| `w2t_bkin.behavior`    | Converts Bpod data into `ndx-structured-behavior` classes (StatesTable, EventsTable, TrialsTable). |
| `w2t_bkin.bpod`        | Low-level parsing and validation of Bpod `.mat` files.                                             |
| `w2t_bkin.ingest.pose` | Imports pose estimation data (DLC/SLEAP) and builds `ndx-pose` objects (PoseEstimation, Skeleton). |
| `w2t_bkin.sync`        | Handles timebase alignment, jitter calculation, and synchronization of video/behavior to TTLs.     |
| `w2t_bkin.ttl`         | Loads hardware TTL pulse timestamps and creates `ndx-events` tables.                               |
| `w2t_bkin.session`     | Loads metadata hierarchically and assembles the root `NWBFile`.                                    |
| `w2t_bkin.utils`       | Shared utilities including datetime parsing, dictionary merging, and helper functions.             |
| `w2t_bkin.pipeline`    | High-level orchestration of the entire workflow.                                                   |

## CLI Utilities

The `scripts/` directory contains useful utilities:

- `mat2json.py`: Converts MATLAB `.mat` files to JSON, handling nested structures and arrays.
- `pose2ttl.py`: Generates mock TTL signals from DeepLabCut pose data (useful for testing or when hardware sync fails).
- `trials2df.py`: Converts NWB `TrialsTable` and `TaskRecording` objects into a flat pandas DataFrame for analysis.

## Testing

The project includes synthetic data generation for testing:

```python
from synthetic import build_raw_folder, build_interim_pose

# Generate synthetic session
session = build_raw_folder(
    out_root=Path("output/test/raw"),
    project_name="test-project",
    subject_id="subject-001",
    session_id="session-001",
    camera_ids=["cam0", "cam1"],
    ttl_ids=["ttl_camera", "ttl_bpod"],
    n_frames=300,
    n_trials=10,
)
```

## License

See `LICENSE` file for details.
