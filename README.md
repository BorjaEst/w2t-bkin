# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings into standardized **NWB (Neurodata Without Borders)** datasets.

## 🚀 Quick Links

- **❓ [FAQ](docs/FAQ.md)** - Common questions and answers
- **🔧 [Troubleshooting](docs/TROUBLESHOOTING.md)** - Solutions to common issues
- **📚 [Full Documentation](docs/README.md)** - Complete documentation index
- **💻 [CLI Reference](docs/cli/README.md)** - Command-line tools guide
- **🐳 [Docker Deployment](docs/containerization/README.md)** - Container setup

## ✨ Key Features

- **NWB-First Architecture** - Direct NWB output, no intermediate conversions
- **Hierarchical Metadata** - Cascading config (experiment → subject → session)
- **Bpod Integration** - Converts Bpod `.mat` to `ndx-structured-behavior`
- **Pose Estimation** - Imports DeepLabCut/SLEAP into `ndx-pose`
- **Synchronization** - TTL-based alignment of video/behavior/hardware
- **Container Orchestration** - Prefect web UI for monitoring
- **User-Friendly CLI** - Complete command-line interface

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Usage Examples](#usage-examples)
5. [Documentation](#documentation)
6. [Module Overview](#module-overview)
7. [Contributing & License](#contributing)

---

## Prerequisites

### Required

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Git** (for manual dependency installation)
- **Raw data files**: Videos (`.mp4`, `.avi`), TTL pulses (`.csv`, `.mat`), Bpod data (`.mat`), pose models (DLC/SLEAP)

### Optional (for Docker)

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **8GB+ RAM** (16GB+ recommended for parallel processing)
- **10GB+ free disk space**

---

## Installation

### Option A: Docker (Recommended)

**For running the complete processing pipeline with web UI.**

1. **Install Docker**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
2. **Install CLI tools**: `pip install w2t-bkin`

✅ **Done!** All pipeline dependencies are included in the Docker image. Continue to [Quick Start](#quick-start).

---

### Option B: Python Development

**Only for developers using w2t-bkin modules (Bpod parsing, sync utilities, etc.) in custom Python applications.**

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install manual dependency (not yet on PyPI)
git clone https://github.com/rly/ndx-structured-behavior.git
pip install ./ndx-structured-behavior

# Install w2t-bkin with all features
pip install w2t-bkin[full,prefect]
```

**Note**: `ndx-structured-behavior` must be installed manually as it's not yet on PyPI.

This is **not needed** for pipeline processing - use Option A instead.

---

## Quick Start

### 1. Initialize Experiment

```bash
# Create experiment structure
w2t-bkin data init /data/my-experiment \
  --lab "Your Lab Name" \
  --institution "Your Institution" \
  --experimenters "Alice,Bob" \
  -y
```

This creates the complete folder structure with Docker configuration and startup scripts.

### 2. Start Pipeline

```bash
cd /data/my-experiment

# Windows: Double-click start-server.bat
# Linux/Mac:
./start-server.sh
```

### 3. Open Web UI

Browser → <http://localhost:4200>

### 4. Add Your Data

```bash
# Add subject and session
w2t-bkin data add-subject /data/my-experiment mouse-001 \
  --species "Mus musculus" --sex F --age P90D -y

w2t-bkin data add-session /data/my-experiment mouse-001 session-001 \
  --description "Baseline recording" -y

# Copy your raw data files
cp /path/to/videos/* data/raw/mouse-001/session-001/Video/
cp /path/to/ttls/* data/raw/mouse-001/session-001/TTLs/
cp /path/to/bpod/* data/raw/mouse-001/session-001/Bpod/
cp /path/to/dlc-model models/
```

### 5. Configure & Run

Edit `configuration.toml` to match your setup, then in Prefect UI:

1. Navigate to **Deployments**
2. Select **process-session**
3. Click **Run** and fill in parameters
4. Monitor progress in **Flow Runs**

📚 **Complete guides**: [CLI Reference](docs/cli/data-management.md) | [Configuration](docs/reference/configuration-parameters.md) | [Docker Deployment](docs/containerization/README.md)

---

## Usage Examples

### Process Single Session

**Via Prefect UI** (Recommended):

1. Open <http://localhost:4200>
2. Deployments → **process-session** → Run
3. Fill parameters and monitor in Flow Runs

**Via CLI** (Alternative):

```bash
prefect deployment run process-session/default \
  --param config_path="/configs/standard.toml" \
  --param subject_id="mouse-001" \
  --param session_id="session-001"
```

### Batch Processing

```bash
# Process multiple sessions via Prefect UI
# Deployments → batch-processing → Run

# Or use CLI batch command
w2t-bkin batch configuration.toml --max-workers 4
```

### Validate NWB Output

```bash
w2t-bkin validate data/processed/mouse-001/session-001/*.nwb
```

---

## Documentation

### User Guides

- **[FAQ](docs/FAQ.md)** - Frequently asked questions (50+ answers)
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[CLI Reference](docs/cli/README.md)** - Complete command-line documentation

### Technical References

- **[Configuration Parameters](docs/reference/configuration-parameters.md)** - Complete config reference
- **[Architecture Diagram](docs/reference/architecture_diagram.mmd)** - System design
- **[Prefect UI Guide](docs/reference/prefect-ui-configuration.md)** - Orchestration setup

### Deployment

- **[Docker Deployment](docs/containerization/README.md)** - Container setup
- **[Deployment Guide](docs/containerization/deployment-guide.md)** - Detailed instructions

### Developer

- **[Technical Design](docs/development/design.md)** - System architecture
- **[Requirements](docs/development/requirements.md)** - Project requirements
- **[Development Tasks](docs/development/tasks.md)** - Roadmap

---

## Module Overview

| Module                     | Description                                               |
| -------------------------- | --------------------------------------------------------- |
| `w2t_bkin.ingest.behavior` | Bpod → `ndx-structured-behavior` (States, Events, Trials) |
| `w2t_bkin.ingest.pose`     | DLC/SLEAP → `ndx-pose` format                             |
| `w2t_bkin.ingest.ttl`      | Hardware TTL pulses → `ndx-events`                        |
| `w2t_bkin.sync`            | Timebase alignment (video/behavior/TTLs)                  |
| `w2t_bkin.core.session`    | Hierarchical metadata + NWB assembly                      |
| `w2t_bkin.flows`           | Prefect orchestration (single/batch)                      |
| `w2t_bkin.cli`             | Command-line interface                                    |
| `w2t_bkin.data`            | Experiment structure + validation                         |

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon).

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

---

## Citation

```bibtex
@software{w2t_bkin,
  author = {Larkum Lab},
  title = {W2T Body Kinematics Pipeline},
  year = {2025},
  url = {https://github.com/BorjaEst/w2t-bkin}
}
```

---

**Need Help?** Check [FAQ](docs/FAQ.md), [Troubleshooting](docs/TROUBLESHOOTING.md), or open a [GitHub issue](https://github.com/BorjaEst/w2t-bkin/issues).

---

## Advanced Topics

<details>
<summary><b>📦 Complete Native Installation (No Containers)</b></summary>

For development or advanced usage without containers:

```bash
# 1. Install ndx-structured-behavior from source (not on PyPI)
git clone https://github.com/rly/ndx-structured-behavior.git
pip install ./ndx-structured-behavior

# 2. Install system dependencies
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html

# 3. Install w2t-bkin with all dependencies
pip install w2t-bkin[full,prefect]

# 4. Start local Prefect server (optional)
prefect server start --host 0.0.0.0
```

After installation, you can run pipelines directly without containers:

```bash
# Process session locally
w2t-bkin run configuration.toml mouse-001 session-001

# Or use Python API directly
python your_script.py
```

</details>

<details>
<summary><b>🐍 Python API Usage (Programmatic)</b></summary>

For custom scripts and integration:

**Using Flows (Recommended)**:

```python
from pathlib import Path
from w2t_bkin.flows.session import process_session_flow

# Process session via Prefect flow
result = process_session_flow(
    config_path=Path("configuration.toml"),
    subject_id="mouse-001",
    session_id="session-001",
)

# Check results
if result.success:
    print(f"✅ NWB file: {result.nwb_file}")
    print(f"⏱ Duration: {result.duration_seconds}s")
else:
    print(f"❌ Error: {result.error}")
```

**Using Low-Level API**:

```python
from pathlib import Path
from w2t_bkin.config import load_config
from w2t_bkin.utils import load_session_metadata_and_nwb
from w2t_bkin.ingest import bpod, ttl, pose
from w2t_bkin.sync import align_bpod_trials_to_ttl

# Load configuration
config = load_config("configuration.toml")

# Load metadata and create NWB file
metadata, nwbfile = load_session_metadata_and_nwb(
    config=config,
    subject_id="mouse-001",
    session_id="session-001"
)

# Process behavioral data
session_dir = config.paths.raw_root / "mouse-001" / "session-001"
bpod_data = bpod.parse_bpod(session_dir, pattern="Bpod/*.mat")
ttl_pulses = ttl.get_ttl_pulses(session_dir, {"ttl_camera": "TTLs/*.txt"})

# Continue processing...
```

See [examples/](examples/) directory for complete working examples:

- `bpod_camera_sync.py` - Bpod-camera synchronization
- `pose_camera_nwb.py` - Pose estimation NWB creation
- `sync_recovery_demo.py` - TTL sync recovery

</details>

<details>
<summary><b>🐳 Alternative Container Runtimes</b></summary>

**Using Docker CLI directly** (without Rancher Desktop):

```bash
cd /data/my-experiment

# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f server

# Stop services
docker compose down
```

**Using Podman** (Docker alternative):

```bash
cd /data/my-experiment

# Start services
podman-compose up -d

# Check status
podman-compose ps

# Stop services
podman-compose down
```

**Using Kubernetes/HPC Clusters**:

For deployment on high-performance computing clusters, see [docs/containerization/deployment-guide.md](docs/containerization/deployment-guide.md)

</details>

<details>
<summary><b>⚙️ Configuration Guide</b></summary>

The pipeline uses TOML configuration files for all settings.

**Pipeline Configuration** (`configuration.toml`):

```toml
[project]
name = "my-experiment"

[paths]
raw_root = "data/raw"
intermediate_root = "data/interim"
output_root = "data/processed"
models_root = "models"

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

**Hierarchical Metadata**:

Metadata cascades through multiple levels:

1. `data/raw/metadata.toml` - Lab/experiment defaults
2. `data/raw/subject-001/subject.toml` - Subject metadata
3. `data/raw/subject-001/session-001/session.toml` - Session metadata

Example `session.toml`:

```toml
session_description = "Behavioral training with pose tracking"
identifier = "session-001"
session_start_time = "2025-01-15T14:30:00Z"
experimenter = ["Alice"]

[subject]
subject_id = "mouse-001"
species = "Mus musculus"
sex = "F"
age = "P90D"

[[cameras]]
id = "camera_0"
paths = "Video/cam0_*.avi"
fps = 150.0
ttl_id = "ttl_camera"
```

See [docs/reference/configuration-parameters.md](docs/reference/configuration-parameters.md) for complete reference.

</details>

<details>
<summary><b>🧪 Testing & Development</b></summary>

The project includes comprehensive testing infrastructure:

**Run tests**:

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests
pytest tests/ -v
```

**Synthetic data generation**:

```python
from synthetic import build_raw_folder

# Generate test session
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

</details>
