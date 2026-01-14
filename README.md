# W2T Body Kinematics Pipeline (w2t-bkin)

A modular, reproducible Python pipeline for processing multi-camera rodent behavior recordings with synchronization, pose estimation, facial metrics, and behavioral events into standardized NWB datasets.

## Features

- 🧠 **NWB-Native**: Write NWB directly
- 🔄 **Prefect Orchestration**: UI + run tracking
- 🧰 **Experiment Workspace Tools**: Initialize data folders + metadata
- ✅ **Validation & Inspection**: `w2t-bkin validate` / `w2t-bkin inspect`
- 🧪 **Development Execution**: `w2t-bkin server start --dev` (runs flows locally)

## Status (What Works Today)

- [x] **Dev mode**: Prefect server + local execution via Runner (`--dev`)
- [x] **Config defaults**: `configuration.toml` provides default parameters; you can override them in Prefect UI before each run
- [ ] **Production mode (Docker workers)**: Work-in-progress (has bugs). Help welcome.
- [ ] **Pose estimation (DLC/SLEAP)**: Planned / partial
- [ ] **Facemap facial metrics**: Planned / partial

## Prerequisites

### For production (in progress)

- **Python**: 3.10 (Some package requirements do not support 3.11+ yet)
  - Install from [python.org](https://www.python.org/downloads/)
- **Docker runtime**: e.g. Rancher Desktop (Recommended for Windows users)
  - Download from [rancherdesktop.io](https://rancherdesktop.io/)
  - Installs Docker automatically
  - No Docker knowledge required

### For development / local execution

- **Python**: 3.10 (Some package requirements do not support 3.11+ yet)
  - Install from [python.org](https://www.python.org/downloads/)
- **Git**: For cloning the repository

and then:

```bash
# Recommended for now (dev mode + local execution)
git clone https://github.com/BorjaEst/w2t-bkin.git
git submodule update --init --recursive
pip install nwb-extensions ndx-events
pip install nwb-extensions ndx-pose
pip install nwb-extensions ndx-structured-behavior
```

## Installation

For production use with Docker workers (work in progress), use:

```bash
pip install w2t-bkin
```

For development, testing or local running (no docker), use:

```bash
# Recommended for now (dev mode + local execution)
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

# Development mode (currently the supported path)
w2t-bkin server start --dev

# This will:
# 1. Start Prefect server
# 2. Serve flows locally (Runner)
# 3. Open browser to <http://localhost:4200>
```

### 4. Run Workflows in Prefect UI

1. Open <http://localhost:4200> (opens automatically)
2. Navigate to **Deployments**
3. Select **process-session** or **batch-process**
4. Click **Run** and fill in parameters:
   - `subject_id`: mouse-001
   - `session_id`: session-001
5. Monitor progress in **Flow Runs** tab

### 5. Start Workers (Production Mode Only)

Production mode is currently work-in-progress.

Development mode runs flows in the server process (Runner) — no worker needed.

---

## Usage Examples

### Discover Available Sessions

```bash
# List all sessions (pass the experiment root)
w2t-bkin discover /data/my-experiment

# Filter by subject
w2t-bkin discover /data/my-experiment --subject mouse-001

# Output formats
w2t-bkin discover /data/my-experiment --format json
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

```text
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

#### Development Mode (Supported)

```bash
pip install w2t-bkin[worker]
cd /data/my-experiment
w2t-bkin server start --dev
```

#### Production Mode (Docker Workers) — WIP

- Goal: server/UI stays lightweight; workers run in Docker
- Current status: being stabilized (bugs exist). Contributions welcome.

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

- **Issues**: <https://github.com/BorjaEst/w2t-bkin/issues>
- **Discussions**: <https://github.com/BorjaEst/w2t-bkin/discussions>
- **Documentation**: <https://github.com/BorjaEst/w2t-bkin/tree/main/docs>
