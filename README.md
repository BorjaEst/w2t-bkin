# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings. It integrates synchronization, pose estimation (DeepLabCut/SLEAP), facial metrics, and behavioral events into standardized **NWB (Neurodata Without Borders)** datasets.

## Key Features

- **NWB-First Architecture**: Produces NWB-native data structures directly, eliminating intermediate conversion layers
- **Hierarchical Metadata**: Supports cascading configuration from global → subject → session levels
- **Bpod Integration**: Parses Bpod `.mat` files and converts them to `ndx-structured-behavior` format
- **Pose Estimation**: Imports and harmonizes data from DeepLabCut and SLEAP into `ndx-pose`
- **Synchronization**: Robust alignment of behavioral data and video frames using TTL pulses
- **Container Orchestration**: Prefect-based workflow engine with web UI for monitoring
- **User-Friendly CLI**: Comprehensive command-line tools for experiment management

---

## Quick Start Guide

### Step 1: Install the CLI Tools

```bash
# Install w2t-bkin CLI tools
pip install w2t-bkin
```

> 💡 **Note**: The CLI tools work immediately for data management (creating folders, organizing experiments). Pipeline processing requires the additional manual installation below and container setup (see Step 3).

**Required Manual Installation** (not yet on PyPI):

The `ndx-structured-behavior` extension must be installed manually:

```bash
git clone https://github.com/rly/ndx-structured-behavior.git
pip install -U ./ndx-structured-behavior
```

After this, install the full pipeline dependencies:

```bash
pip install w2t-bkin[full,prefect]
```

### Step 2: Create Your Experiment Structure

Use the CLI to set up your experiment folder structure:

```bash
# Initialize experiment
w2t-bkin data init /data/my-experiment \
  --lab "Your Lab Name" \
  --institution "Your Institution" \
  --experimenters "Alice,Bob" \
  -y

# Add a subject
w2t-bkin data add-subject /data/my-experiment mouse-001 \
  --species "Mus musculus" \
  --sex F \
  --age P90D \
  -y

# Add a session
w2t-bkin data add-session /data/my-experiment mouse-001 session-001 \
  --description "Baseline recording" \
  --experimenter Alice \
  -y
```

This creates the following structure:

```
/data/my-experiment/
├── configuration.toml       # Pipeline configuration
├── data/
│   ├── raw/
│   │   ├── metadata.toml   # Experiment metadata
│   │   └── mouse-001/
│   │       ├── subject.toml
│   │       └── session-001/
│   │           ├── session.toml
│   │           ├── Video/   # Place your videos here
│   │           ├── TTLs/    # Place TTL files here
│   │           └── Bpod/    # Place Bpod .mat files here
│   ├── interim/            # Intermediate processing files
│   ├── processed/          # Final NWB outputs
│   └── external/           # External data
├── models/                 # Pose estimation models (DLC/SLEAP)
└── docker/                 # Docker configuration
    └── .env               # Auto-generated for containers
```

**Next**: Copy your raw data files (videos, TTL files, Bpod files) into the appropriate session folders, or use `w2t-bkin data import-raw` to safely import existing data using symbolic links.

> 💡 **Manual Folder Creation**: You can also create the folder structure manually without the CLI if you prefer. The CLI tools are provided to prevent mistakes and ensure consistency. Just follow the structure shown above and create the required `.toml` metadata files.

**Understanding Hierarchical Metadata**:

Metadata files cascade and override from top to bottom:

1. **Experiment Level** (`data/raw/metadata.toml`) - Lab-wide defaults (experimenter names, institution, lab name)
2. **Subject Level** (`data/raw/mouse-001/subject.toml`) - Subject-specific information (species, sex, age, genotype)
3. **Session Level** (`data/raw/mouse-001/session-001/session.toml`) - Session details (date, description, camera settings)

Each level **extends and overrides** the previous level. For example:

- Set default `experimenter = ["Alice", "Bob"]` at experiment level
- Override with `experimenter = ["Alice"]` at session level when Bob wasn't present
- Subject metadata like `species` and `sex` only needs to be set once at subject level

This hierarchical approach reduces repetition and keeps metadata organized.

📚 **CLI Documentation**: See [docs/cli/data-management.md](docs/cli/data-management.md) for complete data management guide.

### Step 3: Set Up Processing Pipeline (Container-Based)

The processing pipeline runs in Docker containers using Prefect for orchestration. This approach is recommended as it handles all dependencies automatically.

#### 3.1 Install Container Runtime

**For Windows Users** - Use Rancher Desktop for easy GUI management:

<details>
<summary><b>📦 Windows: Rancher Desktop Installation</b></summary>

1. Download **Rancher Desktop** from [rancherdesktop.io](https://rancherdesktop.io/)
2. Run the installer (`Rancher.Desktop.Setup.X.X.X.exe`)
3. During setup:
   - Choose **dockerd (moby)** as the container runtime
   - Kubernetes is optional (not required for this pipeline)
4. Launch Rancher Desktop
5. Wait for initialization (green status indicator in system tray)

**First-time setup**:

- Click the Rancher Desktop icon in system tray
- Verify status shows "Running"
- Go to **Settings** → **Container Engine** → Ensure "dockerd (moby)" is selected

</details>

**For Linux Users** - Use Docker directly (recommended):

<details>
<summary><b>🐧 Linux: Docker Installation</b></summary>

Most Linux users are familiar with Docker. Install using your distribution's package manager:

**Ubuntu/Debian:**

```bash
# Install Docker
sudo apt-get update
sudo apt-get install docker.io docker-compose-plugin

# Add your user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker compose version
```

**Fedora/RHEL:**

```bash
sudo dnf install docker docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

**Arch Linux:**

```bash
sudo pacman -S docker docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

After installation, logout and login for group changes to take effect.

</details>

> 💡 **Alternative for Linux**: If you prefer a GUI, you can use [Podman Desktop](https://podman-desktop.io/) or [Docker Desktop](https://docs.docker.com/desktop/install/linux-install/), but the command-line Docker is simpler and more common on Linux.

#### 3.2 Start the Pipeline Services

**Method 1: Command Line** (Recommended - Works on all platforms):

```bash
cd /data/my-experiment

# Pull the latest images
docker pull ghcr.io/borjaest/w2t-bkin:latest-server
docker pull ghcr.io/borjaest/w2t-bkin:latest-worker

# Start services
docker compose up -d

# Check status (all should show "Up")
docker compose ps

# View logs (optional)
docker compose logs -f
```

**Method 2: Rancher Desktop GUI** (Windows users):

> ⚠️ **Note**: Rancher Desktop primarily supports Kubernetes deployments. For Docker Compose files, using the command line (Method 1) is more reliable. The Rancher GUI "Compose" feature may not work as expected.

**For Docker Compose with Rancher Desktop**:

1. Open Rancher Desktop
2. Ensure dockerd is running (check status indicator)
3. Open a terminal/command prompt (PowerShell or CMD)
4. Use the docker commands from Method 1 above

**Alternative - Using Rancher Desktop with Kubernetes** (Advanced):

If you prefer Rancher's GUI and want to use Kubernetes instead of Docker Compose, you can convert the compose file to Kubernetes manifests using [kompose](https://kompose.io/). However, for most users, the command-line Docker Compose approach (Method 1) is simpler.

**For most users, we recommend using Method 1 (command line) as it's simpler and more reliable.**

The services will start:

- **PostgreSQL**: Database for Prefect (internal use)
- **Prefect Server**: Orchestration engine and API on port 4200
- **Prefect Worker**: Executes pipeline tasks

**Verify Services**:

```bash
docker compose ps

# Expected output:
# NAME                        STATUS              PORTS
# my-experiment-postgres-1    Up                  5432/tcp
# my-experiment-server-1      Up                  0.0.0.0:4200->4200/tcp
# my-experiment-worker-1      Up
```

#### 3.3 Access the Prefect Web Interface

Once services are running:

1. **Open your web browser**
2. Navigate to: **http://localhost:4200**
3. You'll see the Prefect UI dashboard

**Understanding the Prefect UI** (Basics for Beginners):

The Prefect interface has several main sections:

- **📊 Dashboard** (Home page)

  - Overview of your pipeline runs
  - Shows recent activity and system health
  - Green = everything working, Red = errors

- **🔄 Flows**

  - Lists available processing pipelines
  - Think of these as "recipes" for data processing
  - You don't usually interact here directly

- **🚀 Deployments** (Most Important!)

  - This is where you run your pipelines
  - Pre-configured pipelines ready to execute
  - Click here to process your data

- **💼 Work Pools**

  - Shows worker computers executing tasks
  - Should show your worker as "Online"

- **📝 Runs**
  - History of all pipeline executions
  - Click any run to see detailed logs
  - Shows success/failure status

**Running Your First Pipeline**:

1. Click **Deployments** in the left sidebar
2. Find `process-session-deployment` in the list
3. Click the deployment name to open details
4. Click **Run** button (▶ icon in top right)
5. A form appears - fill in the parameters:
   - **config_path**: `/data/my-experiment/configuration.toml`
   - **subject_id**: `mouse-001`
   - **session_id**: `session-001`
6. Click **Run** at the bottom
7. You'll be redirected to the run details page
8. Watch real-time progress with logs and status updates
9. When complete, check `/data/my-experiment/data/processed/` for your NWB file

**Running Batch Processing** (Multiple Sessions):

1. Click **Deployments** → `batch-process-deployment`
2. Click **Run**
3. Fill in parameters:
   - **config_path**: `/data/my-experiment/configuration.toml`
   - **max_workers**: `4` (number of parallel processes)
4. Pipeline will automatically discover and process all sessions
5. Monitor progress in the **Runs** tab

**Deployment Note**: The first time you start services, deployments are automatically created by the server startup script. If deployments don't appear after 1-2 minutes:

```bash
# Manually trigger deployment (from command line)
docker compose exec worker python /app/docker/deploy_flows.py

# Or restart services
docker compose restart server worker
```

📚 **More Details**: See [Prefect Documentation](https://docs.prefect.io/) for advanced features like scheduling, notifications, and distributed execution.

---

## Usage Examples

### Data Management

```bash
# Initialize experiment
w2t-bkin data init /data/experiment --lab "Lab Name" -y

# Add subject and session
w2t-bkin data add-subject /data/experiment subj-001 -y
w2t-bkin data add-session /data/experiment subj-001 sess-001 -y

# Import existing raw data (safe - uses symbolic links)
w2t-bkin data import-raw /storage/raw/2024-01-15 \
  -e /data/experiment \
  -s subj-001 \
  --session sess-001 \
  --confirm

# Validate structure
w2t-bkin data validate /data/experiment
```

### Pipeline Processing (Alternative: Local CLI)

Once containers are running, you can also trigger pipelines from the command line instead of the web UI:

```bash
# Process single session
w2t-bkin run configuration.toml subj-001 sess-001

# Batch process all sessions
w2t-bkin batch configuration.toml --workers 4

# Discover available sessions
w2t-bkin discover configuration.toml
```

### NWB Validation

After processing completes, validate your output files:

```bash
# Validate NWB file
w2t-bkin validate data/processed/subj-001_sess-001.nwb

# Inspect NWB contents
w2t-bkin inspect data/processed/subj-001_sess-001.nwb
```

📚 **Complete CLI Reference**:

- [Pipeline Commands](docs/cli/pipeline-commands.md)
- [Validation Commands](docs/cli/validation.md)
- [Data Management](docs/cli/data-management.md)

---

## Advanced Topics

<details>
<summary><b>📦 Complete Native Installation (No Containers)</b></summary>

For development or advanced usage without containers:

```bash
# 1. Install ndx-structured-behavior from source
git clone https://github.com/rly/ndx-structured-behavior.git
pip install -U ./ndx-structured-behavior

# 2. Install system dependencies
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html

# 3. Install w2t-bkin with all dependencies
pip install w2t-bkin[prefect,dev]

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

For deployment on high-performance computing clusters, see [docs/containerization/hpc-guide.md](docs/containerization/hpc-guide.md)

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

See [docs/configuration-parameters.md](docs/configuration-parameters.md) for complete reference.

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

---

## Module Overview

| Module                     | Description                                                              |
| :------------------------- | :----------------------------------------------------------------------- |
| `w2t_bkin.ingest.behavior` | Converts Bpod data to `ndx-structured-behavior` (States, Events, Trials) |
| `w2t_bkin.ingest.bpod`     | Low-level Bpod `.mat` file parsing and validation                        |
| `w2t_bkin.ingest.pose`     | Imports DLC/SLEAP pose data into `ndx-pose` format                       |
| `w2t_bkin.ingest.ttl`      | Loads hardware TTL pulses as `ndx-events` tables                         |
| `w2t_bkin.sync`            | Timebase alignment and synchronization of video/behavior/TTLs            |
| `w2t_bkin.core.session`    | Hierarchical metadata loading and NWB file assembly                      |
| `w2t_bkin.flows`           | Prefect orchestration flows for single and batch processing              |
| `w2t_bkin.operations`      | Core business logic for discovery, ingestion, and artifact generation    |
| `w2t_bkin.cli`             | Command-line interface for all user interactions                         |
| `w2t_bkin.data_manager`    | Experiment structure creation and validation                             |

---

## Container Documentation

For detailed information about containerized deployment:

- **[Quick Start](docs/containerization/README.md)** - Container deployment overview
- **[Deployment Guide](docs/containerization/deployment-guide.md)** - Detailed setup
- **[Configuration](docs/containerization/CONFIGURATION.md)** - Customize settings
- **[HPC/Apptainer](docs/containerization/hpc-guide.md)** - Cluster deployment
- **[Architecture & Design](docs/containerization/design.md)** - System design

---

## Contributing

Contributions are welcome! Please see our contributing guidelines (coming soon).

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

---

## Citation

If you use this pipeline in your research, please cite:

```bibtex
@software{w2t_bkin,
  author = {Larkum Lab},
  title = {W2T Body Kinematics Pipeline},
  year = {2025},
  url = {https://github.com/BorjaEst/w2t-bkin}
}
```
