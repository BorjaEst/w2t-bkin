# Frequently Asked Questions (FAQ)

## Installation and Setup

### Q: What's the difference between base install and worker install?

**A:** w2t-bkin uses a two-tier installation strategy to keep the core package lightweight:

| Install Type | Command                        | Size    | Use Case                               | Dependencies                                    |
| ------------ | ------------------------------ | ------- | -------------------------------------- | ----------------------------------------------- |
| **Base**     | `pip install w2t-bkin`         | ~30 MB  | Orchestration, data management, server | Prefect, Pydantic, PyNWB, Typer                 |
| **Worker**   | `pip install w2t-bkin[worker]` | ~630 MB | Pipeline execution, processing         | + DeepLabCut, Facemap, TensorFlow, nwbinspector |

**When to use which:**

- **Base only**: On your laptop/orchestrator to manage experiments and run Prefect server
- **Worker extras**: On compute nodes/workers that actually execute processing pipelines
- **Both**: In development mode when running flows locally

### Q: Do I need Docker?

**A:** It depends on your workflow:

- **Production mode**: Yes, recommended for running workers in isolated containers
- **Development mode** (`--dev` flag): No, flows run in server process (requires worker extras)
- **Data management only**: No, CLI commands for experiment setup don't need Docker

### Q: Which Python version do I need?

**A:** Python **3.10** exactly (`~=3.10.0` in pyproject.toml). This is due to DeepLabCut and TensorFlow compatibility constraints.

```bash
# Check your Python version
python --version  # Should show 3.10.x

# Create Python 3.10 environment
conda create -n w2t python=3.10
conda activate w2t
```

### Q: Can I install on Windows?

**A:** Yes, but with considerations:

- **Recommended**: WSL2 (Windows Subsystem for Linux) for best compatibility
- **Native Windows**: Works for base package, but DeepLabCut has limited support
- **Docker Desktop**: Required for production worker mode on Windows

## Workflow and Usage

### Q: Should I use CLI, Prefect UI, or Python API?

**A:** Choose based on your task:

**Use CLI (`w2t-bkin`) for:**

- Experiment setup (`data init`, `data add-subject`, `data add-session`)
- Session discovery (`discover`)
- NWB validation/inspection (`validate`, `inspect`)
- Server management (`server start/stop/status`)
- Quick operations that don't require heavy processing

**Use Prefect UI for:**

- Processing sessions (single or batch)
- Monitoring long-running jobs
- Viewing execution history and logs
- Team collaboration (shared server)
- Production deployments
- Automatic retries on failures

**Use Python API for:**

- Custom analysis pipelines
- Jupyter notebook workflows
- Integration with other tools
- Programmatic control
- Research and prototyping

### Q: Why can't I find `w2t-bkin run` or `w2t-bkin worker` commands?

**A:** These commands are intentionally not available in the CLI:

**`w2t-bkin run` and `w2t-bkin batch`:**

- Exist as Python functions in `w2t_bkin.cli.pipeline`
- Not registered in CLI because they require `[worker]` extras
- Use Prefect UI instead for session processing

**`w2t-bkin worker`:**

- Never implemented - this is a documentation gap that we're fixing
- Use `prefect worker start` or Docker commands instead
- See [Troubleshooting](TROUBLESHOOTING.md) for worker startup instructions

### Q: What's the difference between production mode and development mode?

**A:**

| Aspect           | Production Mode                             | Development Mode (`--dev`)      |
| ---------------- | ------------------------------------------- | ------------------------------- |
| **Command**      | `w2t-bkin server start`                     | `w2t-bkin server start --dev`   |
| **Workers**      | Separate Docker workers                     | Runs in server process (Runner) |
| **Dependencies** | Base only (server), Worker extras (workers) | Worker extras required          |
| **Use case**     | Production, team workflows                  | Local testing, debugging        |
| **Isolation**    | Full (containerized)                        | None (same process)             |
| **Performance**  | Better for production                       | Faster iteration                |

### Q: How do I process sessions after starting the server?

**A:**

1. Start server:

   ```bash
   w2t-bkin server start
   ```

2. Start workers (production) OR use `--dev` (development):

   ```bash
   # Production: Start workers separately
   prefect worker start --pool default-pool --type process

   # Development: Restart server with --dev (no workers needed)
   w2t-bkin server start --dev
   ```

3. Open Prefect UI at http://localhost:4200

4. Navigate to **Deployments** → **process-session** or **batch-process**

5. Click **Run** and fill parameters:

   - `subject_id`: e.g., "subject-001"
   - `session_id`: e.g., "session-001"
   - Optional: `skip_bpod`, `skip_pose`, `skip_ttl` flags

6. Monitor progress in **Flow Runs** tab

## Configuration

### Q: What configuration files do I need?

**A:** w2t-bkin uses two types of configuration:

**1. Pipeline Configuration (`config.toml` or `configs/standard.toml`)**

- Processing parameters (GPU settings, pose estimation config)
- NWB output settings
- Caching and reprocessing options
- Usually shared across all sessions in an experiment
- See [Configuration Parameters](reference/configuration-parameters.md)

**2. Session Metadata (`session.toml` or `metadata.toml`)**

- Experiment-specific data (experimenter, institution, lab)
- Session description and protocol
- Camera configurations (paths, FPS)
- Subject information
- Different for each session
- See [Metadata Parameters](reference/metadata-parameters.md)

### Q: How does configuration precedence work?

**A:** Configuration is loaded with this precedence (highest to lowest):

1. **Environment variables** (e.g., `W2T_RAW_ROOT`, `W2T_RUNTIME_CONFIG_JSON`)
2. **UI parameters** (when running flows through Prefect UI)
3. **Project config** (specified with `--config` flag)
4. **Base config** (package default: `configs/standard.toml`)

For metadata files specifically:

1. **Session-level** `session.toml`
2. **Subject-level** `subject.toml`
3. **Experiment-level** `metadata.toml` (in raw_root)

### Q: Where should I put my config file?

**A:** Common patterns:

```bash
# Option 1: In experiment directory (recommended)
/data/my-experiment/
├── configs/
│   └── standard.toml    # Custom config
├── data/
│   ├── raw/
│   └── processed/
└── ...

# Use with relative path
cd /data/my-experiment
w2t-bkin server start --config configs/standard.toml

# Option 2: Use package default
# Omit --config flag to use built-in configs/standard.toml

# Option 3: Absolute path from anywhere
w2t-bkin server start --config /full/path/to/config.toml
```

## Data Management

### Q: How do I structure my experiment data?

**A:** Use `w2t-bkin data init` to create the recommended structure:

```bash
w2t-bkin data init /data/my-experiment \
  --lab "Neuroscience Lab" \
  --institution "University" \
  --experimenters "Alice,Bob" \
  -y
```

This creates:

```
/data/my-experiment/
├── configs/
│   └── standard.toml     # Default config (copied from package)
├── data/
│   ├── raw/              # Raw data (metadata.toml here)
│   │   ├── subject-001/
│   │   │   ├── session-001/  # session.toml here
│   │   │   └── session-002/
│   │   └── subject-002/
│   ├── interim/          # Intermediate outputs (poses, etc.)
│   ├── processed/        # Final NWB files
│   └── docker/           # Docker staging area
├── models/               # DeepLabCut models
└── notebooks/            # Analysis notebooks
```

### Q: How do I import existing raw data?

**A:** Use `w2t-bkin data import-raw`:

```bash
# This creates safe symlinks, doesn't copy files
w2t-bkin data import-raw /data/my-experiment subject-001 session-001 \
  /source/videos/2024-01-15/
```

Symlinks are created from:

- `/data/my-experiment/data/raw/subject-001/session-001/`

To actual files in:

- `/source/videos/2024-01-15/`

### Q: What files are required in each session directory?

**A:** Minimum requirements for a valid session:

1. **Required:** `session.toml` OR `metadata.toml`
2. **Optional but needed for processing:**
   - Video files (`.mp4`, `.avi`) for pose estimation
   - Bpod data files (`.mat`) for behavior
   - TTL files (`.csv`, `.h5`) for synchronization
   - Existing pose files (`.h5`, `.csv`) if skipping pose estimation

### Q: Can I process sessions without video files?

**A:** Yes, use the `skip_pose` parameter:

```bash
# In Prefect UI, set parameter:
skip_pose = true

# This will:
# ✓ Process Bpod data (if available)
# ✓ Process TTL data (if available)
# ✗ Skip pose estimation
```

## Processing and Pipeline

### Q: How do I process a single session?

**A:**

1. Ensure session is discoverable:

   ```bash
   w2t-bkin discover configs/standard.toml | grep "session-001"
   ```

2. Start server and workers (or use `--dev`)

3. In Prefect UI:
   - Go to Deployments → process-session
   - Click Run
   - Enter `subject_id` and `session_id`
   - Submit

### Q: How do I process multiple sessions in parallel?

**A:** Use the `batch-process` deployment:

1. In Prefect UI:

   - Go to Deployments → batch-process
   - Click Run
   - Set parameters:
     - `subject_filter`: e.g., "subject-001" (optional)
     - `session_filter`: e.g., "session-00[1-3]" (optional)
     - `max_parallel`: e.g., 4
   - Submit

2. Monitor in Flow Runs - each session gets its own flow run

### Q: What happens if a session fails?

**A:** Prefect provides automatic retry logic:

- Failed tasks retry according to retry configuration
- You can manually retry failed runs in Prefect UI
- Batch processing continues with other sessions (partial failures OK)
- View detailed error logs in Flow Runs → Failed run → Logs

### Q: How do I skip certain processing steps?

**A:** Use skip flags in the UI when submitting:

- `skip_bpod`: Skip Bpod behavior data processing
- `skip_pose`: Skip pose estimation (use if poses already exist)
- `skip_ttl`: Skip TTL synchronization processing
- `skip_nwb_validation`: Skip NWB Inspector validation (faster but not recommended)

## NWB Files

### Q: Where are NWB files saved?

**A:** Default location: `{processed_root}/{subject_id}/{session_id}.nwb`

Example: `/data/my-experiment/data/processed/subject-001/session-001.nwb`

Configure in `config.toml`:

```toml
[nwb]
processed_root = "/data/my-experiment/data/processed"
```

### Q: How do I validate an NWB file?

**A:**

```bash
# Validate with NWB Inspector
w2t-bkin validate /data/processed/subject-001/session-001.nwb

# Inspect contents
w2t-bkin inspect /data/processed/subject-001/session-001.nwb
```

### Q: Can I read NWB files in Python?

**A:** Yes, using PyNWB:

```python
from pynwb import NWBHDF5IO

# Read NWB file
with NWBHDF5IO('session-001.nwb', 'r') as io:
    nwbfile = io.read()

    # Access behavior data
    trials = nwbfile.trials.to_dataframe()

    # Access pose data
    pose = nwbfile.processing['behavior']['pose_estimation']

    # Access timestamps
    timestamps = nwbfile.processing['behavior']['timestamps']
```

## Troubleshooting

### Q: Worker isn't picking up flows - what should I check?

**A:** Systematic checklist:

1. **Is worker running?**

   ```bash
   # Check Prefect UI: Work Pools → docker-pool → Workers
   # Should show online worker with heartbeat
   ```

2. **Is API URL correct?**

   ```bash
   # Linux
   PREFECT_API_URL=http://127.0.0.1:4200/api

   # Windows/WSL
   PREFECT_API_URL=http://host.docker.internal:4200/api
   ```

3. **Does work pool match deployment?**

   - Deployment uses: `docker-pool` or `default-pool`
   - Worker started with: `--pool docker-pool` or `--pool default-pool`
   - Must match exactly

4. **Check worker logs:**
   ```bash
   docker logs w2t-worker
   # or check terminal where prefect worker is running
   ```

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more details.

### Q: How do I enable debug logging?

**A:**

```bash
# For server
w2t-bkin server start --log-level DEBUG

# For workers, set environment variable
export PREFECT_LOGGING_LEVEL=DEBUG
prefect worker start --pool default-pool --type process
```

### Q: Where can I find logs?

**A:**

- **Server logs**: `.prefect/server.log` in current directory
- **Worker logs (Docker)**: `docker logs w2t-worker`
- **Worker logs (process)**: Terminal output where `prefect worker start` runs
- **Flow run logs**: Prefect UI → Flow Runs → Select run → Logs tab

## Advanced

### Q: Can I customize the pipeline?

**A:** Yes, through multiple approaches:

**1. Configuration (easiest)**

```toml
# Edit config.toml
[preprocessing.pose.dlc]
model_path = "/path/to/custom/model"
gpu_index = 0
```

**2. Python API (more flexible)**

```python
from w2t_bkin.flows import process_session_flow, SessionFlowConfig

config = SessionFlowConfig(
    subject_id="subject-001",
    session_id="session-001",
    skip_pose=True,  # Custom logic
    # ... other parameters
)

result = process_session_flow(config)
```

**3. Fork and modify (full control)**

- Clone repository
- Modify flows in `src/w2t_bkin/flows/`
- Install in development mode: `pip install -e .`

### Q: Can I use SLEAP instead of DeepLabCut?

**A:** Not currently supported out-of-the-box, but possible:

1. Generate SLEAP poses separately
2. Save in compatible format (`.h5` or `.csv`)
3. Place in expected location
4. Run pipeline with `skip_pose=true`
5. Pipeline will use existing pose files

Alternatively, contribute SLEAP support - see `src/w2t_bkin/operations/pose.py`

### Q: How do I process data on a remote cluster?

**A:**

**Setup:**

1. **Orchestrator** (your laptop): Install base package
2. **Compute nodes**: Install worker package + Docker

**Workflow:**

```bash
# On orchestrator
w2t-bkin server start --port 4200

# On each compute node
export PREFECT_API_URL=http://orchestrator-ip:4200/api
prefect worker start --pool default-pool --type process --limit 2
```

**Shared storage:**

- Ensure `raw_root`, `processed_root` are on shared filesystem (NFS, etc.)
- All workers must have access to same paths

### Q: Can I run multiple experiments simultaneously?

**A:** Yes, with separate Prefect servers:

```bash
# Experiment 1 (port 4200)
cd /data/experiment-1
w2t-bkin server start --port 4200

# Experiment 2 (port 4201)
cd /data/experiment-2
w2t-bkin server start --port 4201

# Workers connect to specific servers via PREFECT_API_URL
```

## Getting Help

### Q: Where can I get more help?

**A:**

1. **Documentation**:

   - [CLI Reference](cli/README.md)
   - [Configuration Guide](reference/configuration-parameters.md)
   - [Troubleshooting](TROUBLESHOOTING.md)

2. **GitHub Issues**:

   - Search existing issues: https://github.com/BorjaEst/w2t-bkin/issues
   - Open new issue with [bug report template]

3. **Contact**:
   - Larkum Lab team
   - GitHub discussions (if enabled)

### Q: How do I report a bug?

**A:** Open a GitHub issue with:

1. **Environment**:

   ```bash
   w2t-bkin version
   python --version
   pip list | grep -E "(w2t-bkin|prefect|pynwb)"
   ```

2. **Steps to reproduce**:

   - Exact commands
   - Configuration files (anonymized)
   - Expected vs actual behavior

3. **Logs**:

   - Error messages
   - Server/worker logs
   - Flow run logs from UI

4. **Data** (if possible):
   - Sample session that reproduces issue
   - Or synthetic data demonstrating bug
