# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings. It integrates synchronization, pose estimation (DeepLabCut/SLEAP), facial metrics, and behavioral events into standardized **NWB (Neurodata Without Borders)** datasets.

## Key Features

- **NWB-First Architecture**: Produces NWB-native data structures directly, eliminating intermediate conversion layers.
- **Hierarchical Metadata**: Supports cascading configuration from global → subject → session levels for efficient metadata management.
- **Bpod Integration**: Parses Bpod `.mat` files and converts them to `ndx-structured-behavior` format.
- **Pose Estimation**: Imports and harmonizes data from DeepLabCut and SLEAP into `ndx-pose`.
- **Synchronization**: Robust alignment of behavioral data and video frames to a common timebase using TTL pulses.
- **Modular Design**: Distinct modules for behavior, pose, sync, and session management.
- **Built-in Profiling**: Automatic timing and diagnostic figures for each pipeline run (see [docs/profiling.md](docs/profiling.md)).

## Installation

The project requires Python ~3.10.

### Option 1: Container Deployment (Recommended) 🐳

The easiest way to get started is using containers. No manual dependency installation required!

```bash
# 1. Install container runtime (choose one):

# Option A: Podman (Recommended - 100% free, no licensing restrictions)
# Linux:
sudo apt-get install podman podman-compose  # Debian/Ubuntu
sudo dnf install podman podman-compose      # Fedora/RHEL
# Windows/macOS: Download from https://podman-desktop.io/

# Option B: Docker (requires paid license for large organizations)
# See: https://docs.docker.com/get-docker/
# Note: After installing Docker, add your user to docker group:
#   sudo usermod -aG docker $USER
#   newgrp docker  # or logout/login

# 2. Install CLI
pip install w2t-bkin[prefect]

# 3. Start server (CLI auto-detects Podman or Docker)
python -m w2t_bkin.cli container start-server

# 4. Start workers
python -m w2t_bkin.cli container start-worker --workers 4

# 5. Access web UI at http://localhost:4200
```

**Benefits**:

- ✅ No manual ffmpeg/system dependency installation
- ✅ Multi-platform: Windows, macOS, Linux, HPC clusters
- ✅ Free & open-source runtimes (Podman recommended)
- ✅ Web UI for monitoring pipeline runs
- ✅ Distributed execution across network

📚 **Container Guides**:

- [Quick Start](docs/containerization/deployment-guide.md)
- [HPC/Apptainer Deployment](docs/containerization/hpc-guide.md)
- [Architecture & Design](docs/containerization/design.md)

### Option 2: Native Python Installation

For users who prefer traditional installation:

1. **Install `ndx-structured-behavior`** (currently required from source):

   ```bash
   git clone https://github.com/rly/ndx-structured-behavior.git
   pip install -U ./ndx-structured-behavior
   ```

2. **Install system dependencies**:

   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

3. **Install `w2t-bkin`**:

   ```bash
   pip install w2t-bkin

   # Optional: Install Prefect for batch orchestration
   pip install w2t-bkin[prefect]
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

[synchronization]
strategy = "hardware_pulse"
reference_channel = "ttl_camera"

[synchronization.alignment]
method = "nearest"
tolerance_s = 0.001

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

# Camera configuration
[[cameras]]
id = "camera_0"             # Must match a device name in [[devices]]
paths = "Video/cam0_*.avi"  # Glob pattern for video files (supports multiple files per camera)
order = "name_asc"          # Sort order for multiple files: name_asc, name_desc, time_asc, time_desc
fps = 150.0                 # Acquisition frame rate (defaults to 30.0 if omitted)
ttl_id = "ttl_camera"       # Associated TTL stream for synchronization
```

**Note:** Cameras can produce multiple video files (e.g., due to recording size limits, experiment pauses, or multi-segment recordings). The `order` field specifies how these files should be sorted before processing. The pipeline will automatically handle frame counting and synchronization across all files for each camera.

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
from w2t_bkin import config, sync
from w2t_bkin.core import session
from w2t_bkin.ingest import behavior, bpod, ttl

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

| Module                     | Description                                                                                        |
| :------------------------- | :------------------------------------------------------------------------------------------------- |
| `w2t_bkin.ingest.behavior` | Converts Bpod data into `ndx-structured-behavior` classes (StatesTable, EventsTable, TrialsTable). |
| `w2t_bkin.ingest.bpod`     | Low-level parsing and validation of Bpod `.mat` files.                                             |
| `w2t_bkin.ingest.pose`     | Imports pose estimation data (DLC/SLEAP) and builds `ndx-pose` objects (PoseEstimation, Skeleton). |
| `w2t_bkin.ingest.ttl`      | Loads hardware TTL pulse timestamps and creates `ndx-events` tables.                               |
| `w2t_bkin.sync`            | Handles timebase alignment, jitter calculation, and synchronization of video/behavior to TTLs.     |
| `w2t_bkin.core.session`    | Loads metadata hierarchically and assembles the root `NWBFile`.                                    |
| `w2t_bkin.core.pipeline`   | High-level orchestration of the entire workflow.                                                   |
| `w2t_bkin.utils`           | Shared utilities including datetime parsing, dictionary merging, and helper functions.             |

## CLI Utilities

### Data Management Commands

The pipeline includes comprehensive data management commands to help you organize experiments safely and efficiently.

```bash
# Initialize new experiment structure
python -m w2t_bkin.cli data init /data/my-experiment \
  --lab "Larkum Lab" \
  --institution "Humboldt University" \
  --experimenters "Alice,Bob"

# Add subject
python -m w2t_bkin.cli data add-subject /data/my-experiment subject-001 \
  --species "Mus musculus" \
  --sex M \
  --age P90D

# Add session
python -m w2t_bkin.cli data add-session /data/my-experiment subject-001 session-001 \
  --date 2024-01-15 \
  --description "Baseline recording" \
  --experimenter "Alice"

# Import existing raw data (SAFE - uses symbolic links)
python -m w2t_bkin.cli data import-raw /raw-storage/2024-01-15 \
  --experiment /data/my-experiment \
  --subject subject-001 \
  --session session-001 \
  --confirm

# Validate experiment structure
python -m w2t_bkin.cli data validate /data/my-experiment
```

📚 **See**: [Data Management CLI Guide](docs/data-management-cli.md) for complete documentation

### Basic Commands

```bash
# Run pipeline for a specific subject/session
python -m w2t_bkin.cli run config.toml subject-001 session-001

# Validate NWB file integrity
python -m w2t_bkin.cli validate output.nwb

# Inspect NWB file contents
python -m w2t_bkin.cli inspect output.nwb

# Check version
python -m w2t_bkin.cli version
```

### Container Commands

The CLI automatically detects available container runtime (Podman → Docker → Apptainer, in priority order).

```bash
# Start orchestration server (uses Podman/Docker automatically)
python -m w2t_bkin.cli container start-server

# Start worker containers
python -m w2t_bkin.cli container start-worker --workers 4

# View container status
python -m w2t_bkin.cli container status

# View logs
python -m w2t_bkin.cli container logs server --follow

# Stop all containers
python -m w2t_bkin.cli container stop
```

**Alternative: Direct compose commands** (if you prefer manual control):

```bash
# Using Podman
podman compose up -d                    # Start all services
podman compose ps                       # Check status
podman compose logs -f server          # View logs
podman compose down                     # Stop all

# Using Docker
docker compose up -d                    # Start all services
docker compose ps                       # Check status
docker compose logs -f server          # View logs
docker compose down                     # Stop all
```

### Batch Processing

The pipeline includes a discovery command for batch processing multiple subjects/sessions:

```bash
# Discover all available sessions
python -m w2t_bkin.cli discover config.toml --format plain

# Process all sessions in parallel with GNU Parallel
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --bar --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
```

See [docs/batch-processing.md](docs/batch-processing.md) for comprehensive batch processing guides including:

- Discovery command usage and filtering
- Parallel processing with GNU Parallel
- Shell scripting examples
- Python programmatic APIs
- Future orchestration (Prefect, Kubernetes)

### Script Utilities

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
