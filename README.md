# W2T Body Kinematics Pipeline (w2t-bkin)

`w2t-bkin` is a Prefect-orchestrated, NWB-native processing pipeline for multi-camera rodent behavior experiments.
The core goal is reproducibility: given an experiment workspace (raw data + metadata + configuration), the pipeline produces standardized NWB files in a predictable output layout, with run history and parameters tracked in Prefect.

This repository contains both:

- A lightweight orchestration layer (CLI, Prefect deployments, configuration parsing).
- The processing/assembly logic that reads experiment artifacts (videos, TTLs, Bpod logs, pose outputs) and writes NWB datasets using PyNWB and NWB extensions.

## What Has Been Implemented

The project is organized around a clear separation of concerns:

- **Experiment workspace tools**: create a standard folder layout and generate starter metadata files.
- **Configuration-driven runtime policy**: a single `configuration.toml` describes how to process (sync strategy, verification, video behavior, QC, etc.).
- **Metadata-driven data description**: session/subject metadata and pipeline inputs (cameras, TTLs, Bpod, pose sources) are defined in TOML metadata files loaded and merged at runtime.
- **Prefect-native execution**: processing is run through Prefect deployments so every run is parameterized, traceable, and repeatable.

Practically, the “happy path” today is:

1. Initialize an experiment workspace.
2. Add subject/session metadata.
3. Put raw assets into the expected `data/raw/...` folders.
4. Start the Prefect server and serve/deploy the flows.
5. Trigger workflows in the Prefect UI.
6. Validate and inspect the resulting NWB output.

## Status and Roadmap

- Development mode (local serve via Prefect Runner) works and is the recommended path for iterative use.
- Production mode (Docker work pool + external workers) exists but is still being stabilized.
- Pose ingestion/assembly is implemented at the metadata and IO levels; ML pose generation (DLC/SLEAP execution inside the pipeline) is partially implemented and is being extended.
- Facial metrics (Facemap) is planned / partial.

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

The NWB extensions live in this repository under `nwb-extensions/` and are installed as Python packages.
When working from source, initialize git submodules and install the local extensions:

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

For development, testing, or local execution (no Docker), use:

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

The pipeline assumes a “workspace-first” workflow: you operate from the experiment root directory, and the CLI uses the current working directory to resolve defaults (config, `.workers/` environment files, and standard data layouts).

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
3. Select **process-session** or **batch-process-sessions**
4. Click **Run** and fill in parameters:
   - `subject_id`: mouse-001
   - `session_id`: session-001
5. Monitor progress in **Flow Runs** tab

### 5. Start Workers (Production Mode Only)

Production mode is currently work-in-progress.

Development mode runs flows in the server process (Prefect Runner) — no worker needed.

Note: `server` is a command group; the correct invocation is `w2t-bkin server start ...` (not `w2t-bkin server ...`).

---

## Usage Examples

The CLI is intentionally a thin layer: it bootstraps the workspace, starts/stops Prefect, and provides a few utility commands for discovery and validation. The “main work” happens as Prefect flow runs (submitted via the UI).

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

## Workflows (Session and Batch)

The pipeline exposes two primary workflows as Prefect flows. Both are designed to be started from the Prefect UI so every run has explicit parameters, reproducible configuration, and a complete execution record.

The session workflow is the “unit of work” that produces one NWB file for one `(subject_id, session_id)` pair. The batch workflow is a convenience wrapper that discovers many sessions under `data/raw/` and runs the session workflow repeatedly in parallel.

### Session Workflow: `process-session`

The `process-session` flow is responsible for turning one session’s raw inputs into a validated NWB output.
Internally it is structured into phases so that failures are easier to diagnose and outputs are easier to interpret.

1. **Phase 0 — Configuration**
   The session flow is implemented in `src/w2t_bkin/flows/session.py` and is parameterized by `SessionConfig` (defined in `src/w2t_bkin/config.py`).
   The flow resolves all runtime paths from environment variables, loads and merges metadata files for the selected subject/session, and initializes the NWB file header.
   At this stage the flow also sets up per-run logging into an output `pipeline.log` file.

2. **Phase 1 — Discovery**
   File discovery is handled through tasks under `src/w2t_bkin/tasks/` backed by pure “operations” utilities under `src/w2t_bkin/operations/`.
   The flow scans the session’s raw folder structure to locate camera video files, TTL channel files, and Bpod logs according to the configured patterns.
   The discovery results become the input contract for the rest of the pipeline: if a required category is missing, the run should fail early with a clear error.

3. **Phase 1.5 — Verification (fail-fast)**
   Verification logic lives in the same `tasks/` + `operations/` split: tasks expose Prefect-friendly units of work, while operations contain the core pure functions.
   Optional verification checks run before expensive processing.
   Typical checks include validating frame counts and ensuring synchronization inputs are internally consistent, so a run fails early rather than producing partially-assembled NWB output.

4. **Phase 2 — Artifact generation (pose outputs)**
   Pose-related configuration is split between runtime policy (`configuration.toml` → `src/w2t_bkin/config.py`) and per-session metadata (`metadata.toml` → `src/w2t_bkin/models.py`).
   If enabled, the pipeline can generate pose artifacts (DLC/SLEAP) on a per-camera basis.
   This phase is designed to be parallelizable across cameras, and it produces intermediate pose files that are later ingested and assembled into NWB.

5. **Phase 3 — Ingestion**
   Ingestion is implemented as Prefect tasks in `src/w2t_bkin/tasks/` that call IO/parsing utilities in `src/w2t_bkin/operations/`.
   The flow loads and normalizes:

- Bpod behavioral data (trials and events)
- TTL pulses (one or more channels)
- Pose data (DLC/SLEAP outputs)
  Ingestion converts file-level artifacts into structured in-memory representations used by synchronization and NWB assembly.

6. **Phase 4 — Synchronization**
   Synchronization and alignment are implemented as task/operation pairs under `src/w2t_bkin/tasks/` and `src/w2t_bkin/operations/`.
   The flow computes alignment statistics and trial offsets, using TTL pulses as a common time base.
   This phase produces the “glue” that allows behavioral events and pose samples to be expressed on a consistent timeline.

7. **Phase 5 — Assembly**
   NWB assembly code is primarily in `src/w2t_bkin/operations/` with NWB creation helpers in `src/w2t_bkin/core/`.
   The flow writes the ingested data into NWB structures:

- behavioral tables (trials/events)
- pose estimations and related processing modules
  The output is a complete NWB file object in memory.

8. **Phase 6 — Finalization**
   Finalization (writing, validation, and report sidecars) is implemented in `src/w2t_bkin/tasks/` and `src/w2t_bkin/operations/`, with `w2t-bkin validate` and `w2t-bkin inspect` implemented under `src/w2t_bkin/cli/validation.py`.
   The flow writes the NWB file to disk, runs validation, and generates run sidecars and diagnostic figures when enabled.
   The final output directory also contains a run log (`pipeline.log`) to make “what happened” auditable without relying exclusively on the Prefect UI.

**How you run it**

- In Prefect UI, select the `process-session` deployment.
- Provide `subject_id` and `session_id`.
- Provide `config` (a baked `SessionConfig`, typically derived from `configuration.toml` when deployments are created).

### Batch Workflow: `batch-process-sessions`

The `batch-process-sessions` flow automates “run the session workflow for everything that matches a filter”.
It is designed for reprocessing entire experiments or running large backfills after changing configuration.

1. **Discover sessions**
   The batch flow is implemented in `src/w2t_bkin/flows/batch.py` and uses the shared discovery utilities in `src/w2t_bkin/utils.py`.
   The flow reads `W2T_RAW_ROOT` and scans for `(subject, session)` pairs.
   It applies `subject_filter` and `session_filter` glob-style filtering so you can target subsets (for example, a single subject or a date range encoded in session ids).

2. **Run sessions in parallel**
   For each discovered session, the batch flow submits a task wrapper that calls the session flow (`process_single_session_task` → `process_session_flow`).
   Runs are independent: one failing session does not automatically cancel the entire batch.
   Each session produces its own output folder and NWB output if successful.

3. **Aggregate results**
   When all sessions finish, the batch flow summarizes totals (successful/failed) and surfaces per-session errors.
   This makes the Prefect flow run act like a “batch report” for a large processing campaign.

**How you run it**

- In Prefect UI, select the `batch-process-sessions` deployment.
- Provide a `config` (`BatchFlowConfig`) that includes:
  - `subject_filter` and `session_filter`
  - `max_parallel`
  - `configuration` (the `SessionConfig` applied to each session)

For the full list of configuration and metadata parameters referenced by these workflows, see:

- `docs/reference/configuration-parameters.md`
- `docs/reference/metadata-parameters.md`

## Architecture (How the Pieces Fit Together)

At runtime there are two distinct roles:

- **Orchestrator** (Prefect server + UI): owns deployments, parameters, and run history.
- **Executor** (dev runner or production workers): runs tasks that read experiment data and write NWB.

Development mode collapses both roles into a single process to optimize iteration speed. Production mode separates them so the UI stays light while workers run in isolated environments.

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

## Data Model and Workspace Layout

The pipeline operates on an experiment directory with predictable subfolders (created by `w2t-bkin data init`). The key convention is a strict split between:

- `data/raw/`: immutable inputs copied from acquisition systems.
- `data/interim/`: derived intermediate artifacts (e.g., pose files, sync products).
- `data/processed/` (or `output/` depending on run mode): final NWB outputs and run artifacts.

Metadata is stored as TOML and loaded hierarchically (e.g., root metadata + subject + session), then merged into a single runtime view that drives NWB writing and pipeline assembly.

Two files are central:

- `configuration.toml`: processing policy (how to run).
- `metadata.toml` / `session.toml` / `subject.toml`: experiment description and inputs (what exists).

---

## Documentation

### User Guides

- **[Templates](templates/README.md)** - Example configuration and metadata files
- **[Cheat Sheet](CHEATSHEET.md)** - Quick reference for common tasks
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - Migrate from old workflow
- **[FAQ](docs/FAQ.md)** - Frequently asked questions
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[CLI Reference](docs/cli/README.md)** - Command-line documentation

### Technical References

- **[Configuration Parameters](docs/reference/configuration-parameters.md)** - Pipeline behavior (HOW to process)
- **[Metadata Parameters](docs/reference/metadata-parameters.md)** - Data description (WHAT data exists)
- **[Architecture Diagram](docs/reference/architecture_diagram.mmd)** - System design
- **[Prefect UI Guide](docs/reference/prefect-ui-configuration.md)** - Orchestration setup

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
