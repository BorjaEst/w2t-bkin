# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings with synchronization, pose estimation, facial metrics, and behavioral events into standardized NWB datasets.

## Features

- 🧠 **NWB-Native**: Direct NWB file creation, no intermediate formats
- 🔄 **Prefect Orchestration**: Workflow management with monitoring UI
- 📹 **Multi-Camera Support**: Synchronized video processing with pose estimation
- 🐭 **Behavior Analysis**: Bpod task recording and TTL synchronization
- 🎯 **Pose Estimation**: DeepLabCut and SLEAP integration
- 📊 **Facial Metrics**: Facemap-based facial movement analysis
- ✅ **Validation**: Automated NWB file validation and inspection
- 🐳 **Flexible Execution**: Local Python or Docker workers

## Prerequisites

- **Python**: 3.10
- **Prefect**: 3.6+ (included in base installation)
- **Rancher Desktop**: Recommended for Windows users (provides Docker runtime)
  - Download from [rancherdesktop.io](https://rancherdesktop.io/)
  - Installs Docker automatically
  - No Docker knowledge required

## Installation

```bash
# Base installation (CLI + Prefect server/UI + data management)
pip install w2t-bkin

# OR full installation with worker capabilities (includes ML/video processing)
pip install w2t-bkin[worker]
```

**Installation guide:**

- **Base**: `pip install w2t-bkin` (~MB, no ML dependencies)
  - Run Prefect UI and orchestration
  - Use Docker containers for processing (recommended)
  - Best for most users
- **Worker extras**: `pip install w2t-bkin[worker]` (~Gb, includes DeepLabCut, etc.)
  - Run processing tasks directly without Docker
  - Good for development or machines without Docker
  - All-in-one installation for single-user workstations

## Quick Start

### 1. Initialize Workspace

```bash
# Create experiment directory structure
w2t-bkin data init /data/my-experiment
cd /data/my-experiment
```

### 2. Add Metadata

```bash
# Add subject
w2t-bkin data add-subject /data/my-experiment mouse-001 \
  --species "Mus musculus" --sex F --age P90D -y

# Add session
w2t-bkin data add-session /data/my-experiment mouse-001 session-001 \
  --description "Baseline recording" -y

# Copy your raw data files
cp /path/to/videos/* /data/my-experiment/data/raw/mouse-001/session-001/Video/
cp /path/to/ttls/* /data/my-experiment/data/raw/mouse-001/session-001/TTLs/
cp /path/to/bpod/* /data/my-experiment/data/raw/mouse-001/session-001/Bpod/
cp /path/to/dlc-model /data/my-experiment/models/
```

### 3. Start Prefect Server

```bash
cd /data/my-experiment

# Production mode (uses Docker workers)
w2t-bkin server start --config configs/standard.toml

# Development mode (runs flows locally with Runner - requires worker extras)
w2t-bkin server start --config configs/standard.toml --dev

# This will:
# 1. Start Prefect server
# 2. Create flow deployments (prod) or serve flows (dev)
# 3. Open browser to http://localhost:4200
```

### 4. Run Workflows in Prefect UI

1. Open **http://localhost:4200** (opens automatically)
2. Navigate to **Deployments**
3. Select **process-session** or **batch-process**
4. Click **Run** and fill in parameters:
   - `subject_id`: mouse-001
   - `session_id`: session-001
5. Monitor progress in **Flow Runs** tab

### 5. Start Workers (Production Mode Only)

> **⚠️ Important:** The `w2t-bkin worker` command does not exist. Use Prefect CLI or Docker directly.

**Production mode** requires workers to execute flows. Choose one method:

**Method 1: Prefect CLI (requires `pip install w2t-bkin[worker]`)**

```bash
# Start a process worker with concurrency limit
prefect worker start --pool default-pool --type process --limit 4
```

**Method 2: Docker (recommended for production)**

```bash
# Source the worker environment and start Docker worker
source .workers/.env
prefect worker start --pool docker-pool --type docker
```

**Development mode** runs flows in the server process - no worker needed!

---

## Usage Examples

### Discover Available Sessions

```bash
# List all sessions
w2t-bkin discover configs/standard.toml

# Filter by subject
w2t-bkin discover configs/standard.toml --subject mouse-001

# Output formats
w2t-bkin discover configs/standard.toml --format json
```

### Validate NWB Output

```bash
w2t-bkin validate /data/my-experiment/data/processed/mouse-001/session-001/*.nwb
```

### Inspect NWB File

```bash
w2t-bkin inspect /data/my-experiment/data/processed/mouse-001/session-001/*.nwb
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│  User                                   │
│  1. w2t-bkin server start [--dev]       │
│  2. Open http://localhost:4200          │
│  3. Trigger workflows in UI             │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Prefect Server (localhost:4200)        │
│  - Flow Deployments (production)        │
│  - Flow Services via Runner (dev mode)  │
│  - Work Pool (docker-pool, type: docker)│
│  - UI Monitoring                        │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Workers (Production Only)              │
│  - Docker containers execute flows      │
│  - Managed via docker-pool              │
│                                         │
│  Dev Mode (No Worker Needed)            │
│  - Flows run in server via Runner       │
│  - No work pool required                │
└─────────────────────────────────────────┘
```

---

## Documentation

### User Guides

- **[Templates](templates/README.md)** - Example configuration and metadata files
- **[Cheat Sheet](CHEATSHEET.md)** - Quick reference for common tasks
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - Migrate from old workflow
- **[FAQ](docs/FAQ.md)** - Frequently asked questions
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[CLI Reference](docs/cli/README.md)** - Complete command-line documentation

### Technical References

- **[Configuration Parameters](docs/reference/configuration-parameters.md)** - Pipeline behavior (HOW to process)
- **[Metadata Parameters](docs/reference/metadata-parameters.md)** - Data description (WHAT data exists)
- **[Architecture Diagram](docs/reference/architecture_diagram.mmd)** - System design
- **[Prefect UI Guide](docs/reference/prefect-ui-configuration.md)** - Orchestration setup

### Developer Documentation

- **[Requirements](docs/development/requirements.md)** - Project requirements
- **[Design](docs/development/design.md)** - Technical design document
- **[Tasks](docs/development/tasks.md)** - Development task tracking

---

## Architecture & Dependencies

### Deployment Options

**Option 1: Server + Docker Workers (Recommended)**

```bash
# Server machine
pip install w2t-bkin                # ~30 MB (Prefect, CLI, config)
w2t-bkin server start              # Starts UI at localhost:4200

# Docker workers (pre-built images from GitHub Container Registry)
docker pull ghcr.io/borjaest/w2t-bkin:latest
docker run ... ghcr.io/borjaest/w2t-bkin:latest  # Contains all ML/video dependencies
```

**Benefits:**

- Clean separation: Server handles UI, workers handle processing
- No dependency conflicts on server machine
- Easy scaling: Run multiple Docker workers

**Option 2: Development Mode (Local)**

```bash
# Single machine with worker extras installed
pip install w2t-bkin[worker]       # ~630 MB (everything)
w2t-bkin server start --dev        # Flows run in server process via Runner
```

**Benefits:**

- Fastest iteration (no container overhead)
- Simplest setup for development and debugging
- Live code changes without rebuild

### Dependency Breakdown

| Component      | Base Install       | Worker Extras          |
| -------------- | ------------------ | ---------------------- |
| **CLI**        | ✅ Typer, Rich     | ✅                     |
| **Prefect**    | ✅ Server + Client | ✅                     |
| **NWB**        | ✅ PyNWB, HDMF     | ✅                     |
| **Config**     | ✅ Pydantic, TOML  | ✅                     |
| **Processing** | ❌                 | ✅ DeepLabCut, Facemap |
| **Video**      | ❌                 | ✅ FFmpeg, scipy       |
| **Validation** | ❌                 | ✅ nwbinspector        |
| **Total Size** | ~30 MB             | ~630 MB                |

---

## Advanced Configuration

### Custom Work Pools

```bash
# Start server with local work pool (requires [worker] extras)
w2t-bkin server start --work-pool local

# Start server with custom port
w2t-bkin server start --port 5000
```

### Python API (Advanced Users)

For scripting and automation:

```python
from w2t_bkin.api import SessionFlowConfig
from w2t_bkin.flows import process_session_flow

# Create configuration
config = SessionFlowConfig(
    config_path="configs/standard.toml",
    subject_id="mouse-001",
    session_id="session-001",
    skip_pose=True  # Optional: skip specific steps
)

# Direct execution (no Prefect needed)
result = process_session_flow(config=config)

if result.success:
    print(f"✓ NWB written to: {result.nwb_path}")
```

---

## Development

For contributors and developers:

```bash
# Clone repository
git clone https://github.com/BorjaEst/w2t-bkin.git
cd w2t-bkin

# Install in editable mode with dev dependencies
pip install -e .[dev,worker]

# Run tests
pytest

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Build Docker image locally
docker build -f docker/Dockerfile -t w2t-bkin:dev .
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache-2.0 - See [LICENSE](LICENSE) for details.

## Citation

If you use this pipeline in your research, please cite:

```bibtex
@software{w2t_bkin,
  title={W2T Body Kinematics Pipeline},
  author={Larkum Lab},
  year={2024},
  url={https://github.com/BorjaEst/w2t-bkin}
}
```

---

## Support

- **Issues**: https://github.com/BorjaEst/w2t-bkin/issues
- **Discussions**: https://github.com/BorjaEst/w2t-bkin/discussions
- **Documentation**: https://github.com/BorjaEst/w2t-bkin/tree/main/docs
